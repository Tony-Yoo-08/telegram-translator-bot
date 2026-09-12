import json
import logging
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from translator import (
    UnifiedTranslationService,
    detect_source_language,
    get_translation_targets,
)

# 로깅 설정
logging.basicConfig(
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("TranslatorBot")

# 환경변수 로드 (.env 파일 우선)
current_dir = Path(__file__).parent
load_dotenv(current_dir / ".env")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
DEEPL_API_KEY = os.getenv("DEEPL_API_KEY", "").strip()
ACCESS_PASSWORD = os.getenv("ACCESS_PASSWORD", "").strip()

# 통합 번역 서비스 인스턴스 생성
translation_service = UnifiedTranslationService(DEEPL_API_KEY)

# 채팅방별 설정 저장 파일
SETTINGS_FILE = current_dir / "chat_settings.json"


def load_chat_settings() -> dict:
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"설정 파일 로드 실패: {e}")
    return {}


def save_chat_settings(settings: dict):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"설정 파일 저장 실패: {e}")


# 전역 설정 메모리 캐시:
# { "chat_id": {"enabled": bool, "authenticated": bool, "lang_mode": "all"|"ko-en"|"ko-vi"} }
chat_settings = load_chat_settings()


def is_chat_authenticated(chat_id: int) -> bool:
    """비밀번호가 설정되어 있지 않으면 모두 허용, 설정되어 있으면 인증 여부 확인"""
    if not ACCESS_PASSWORD:
        return True
    conf = chat_settings.get(str(chat_id), {})
    if isinstance(conf, dict):
        return conf.get("authenticated", False)
    return False


def set_chat_authenticated(chat_id: int, authenticated: bool):
    str_id = str(chat_id)
    if str_id not in chat_settings or not isinstance(chat_settings[str_id], dict):
        chat_settings[str_id] = {"enabled": True, "authenticated": authenticated, "lang_mode": "all"}
    else:
        chat_settings[str_id]["authenticated"] = authenticated
    save_chat_settings(chat_settings)


def is_translation_enabled(chat_id: int) -> bool:
    """채팅방의 번역 켜짐/꺼짐 여부 (기본값: True)"""
    conf = chat_settings.get(str(chat_id), {})
    if isinstance(conf, dict):
        return conf.get("enabled", True)
    if isinstance(conf, bool):
        return conf
    return True


def set_translation_enabled(chat_id: int, enabled: bool):
    str_id = str(chat_id)
    if str_id not in chat_settings or not isinstance(chat_settings[str_id], dict):
        chat_settings[str_id] = {"enabled": enabled, "authenticated": True, "lang_mode": "all"}
    else:
        chat_settings[str_id]["enabled"] = enabled
    save_chat_settings(chat_settings)


def get_chat_lang_mode(chat_id: int) -> str:
    """채팅방 언어 모드 반환 (기본값: 'all')"""
    conf = chat_settings.get(str(chat_id), {})
    if isinstance(conf, dict):
        return conf.get("lang_mode", "all")
    return "all"


def set_chat_lang_mode(chat_id: int, mode: str):
    str_id = str(chat_id)
    if str_id not in chat_settings or not isinstance(chat_settings[str_id], dict):
        chat_settings[str_id] = {"enabled": True, "authenticated": True, "lang_mode": mode}
    else:
        chat_settings[str_id]["lang_mode"] = mode
    save_chat_settings(chat_settings)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """봇 시작 및 안내 메시지"""
    chat_id = update.effective_chat.id

    if ACCESS_PASSWORD and not is_chat_authenticated(chat_id):
        await update.effective_message.reply_text(
            "🔒 **보안 잠금 상태입니다.**\n\n"
            "이 봇은 비인가 사용을 방지하기 위해 비밀번호 인증이 필요합니다.\n"
            "관리자가 설정한 비밀번호를 입력해 잠금을 해제해 주세요.\n\n"
            "👉 **명령어**: `/auth [비밀번호]`",
            parse_mode="Markdown"
        )
        return

    mode = get_chat_lang_mode(chat_id)
    mode_desc = "한-영-베 3개국어 통합 모드" if mode == "all" else ("한-베 전용 모드" if mode == "ko-vi" else "한-영 전용 모드")

    text = (
        "👋 안녕하세요! **한·영·베 실시간 자동 번역 봇**입니다.\n\n"
        "🇰🇷 한국어 ↔ 🇺🇸 영어 ↔ 🇻🇳 베트남어를 자동으로 감지하여 번역해 드립니다.\n\n"
        f"🌐 **현재 언어 모드**: `{mode_desc}`\n\n"
        "📌 **주요 명령어**\n"
        "• `/lang all` : 한·영·베 3개국어 동시 번역 모드 (기본)\n"
        "• `/lang ko-vi` : 한-베 전용 모드 (한국어 ↔ 베트남어)\n"
        "• `/lang ko-en` : 한-영 전용 모드 (한국어 ↔ 영어)\n"
        "• `/translate on/off` : 자동 번역 켜기/끄기\n"
        "• `/status` : 대화방 인증 및 설정 상태 확인\n"
        "• `/help` : 도움말 보기"
    )
    await update.effective_message.reply_text(text, parse_mode="Markdown")


async def cmd_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """언어 모드 변경 (/lang all | ko-vi | ko-en)"""
    chat_id = update.effective_chat.id

    if ACCESS_PASSWORD and not is_chat_authenticated(chat_id):
        await update.effective_message.reply_text("🔒 비밀번호 인증이 필요합니다. `/auth [비밀번호]`를 먼저 입력해 주세요.", parse_mode="Markdown")
        return

    args = context.args
    if not args or args[0].lower() not in ["all", "ko-vi", "ko-en"]:
        current = get_chat_lang_mode(chat_id)
        await update.effective_message.reply_text(
            f"현재 이 대화방의 언어 모드는 **`{current}`** 입니다.\n\n"
            "변경하시려면 아래 명령어 중 하나를 입력하세요:\n"
            "• `/lang all` : 한·영·베 통합 모드 (한국어 입력 시 영+베 동시 출력)\n"
            "• `/lang ko-vi` : 한-베 전용 모드 (한국어 ↔ 베트남어)\n"
            "• `/lang ko-en` : 한-영 전용 모드 (한국어 ↔ 영어)",
            parse_mode="Markdown"
        )
        return

    new_mode = args[0].lower()
    set_chat_lang_mode(chat_id, new_mode)

    mode_names = {
        "all": "한·영·베 3개국어 통합 모드 🇰🇷🇺🇸🇻🇳",
        "ko-vi": "한-베 전용 모드 🇰🇷🇻🇳",
        "ko-en": "한-영 전용 모드 🇰🇷🇺🇸",
    }
    await update.effective_message.reply_text(f"✅ 언어 모드가 **{mode_names.get(new_mode)}**로 변경되었습니다.", parse_mode="Markdown")


async def cmd_auth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """비밀번호 인증 명령어 (/auth [비밀번호])"""
    chat_id = update.effective_chat.id
    message = update.effective_message

    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message.message_id)
    except Exception:
        pass

    if not ACCESS_PASSWORD:
        await message.reply_text("ℹ️ 현재 봇에 설정된 비밀번호가 없습니다. 모든 대화방에서 자유롭게 사용 가능합니다.")
        return

    args = context.args
    if not args:
        await message.reply_text("🔒 비밀번호를 함께 입력해 주세요.\n형식: `/auth [비밀번호]`", parse_mode="Markdown")
        return

    input_pwd = args[0].strip()
    if input_pwd == ACCESS_PASSWORD:
        set_chat_authenticated(chat_id, True)
        await message.reply_text(
            "🔓 **인증에 성공했습니다!**\n\n"
            "이 대화방에서 번역 기능이 정상적으로 활성화되었습니다.\n"
            "*(보안을 위해 입력하신 비밀번호 메시지는 자동 삭제되었습니다.)*",
            parse_mode="Markdown"
        )
    else:
        await message.reply_text("❌ **비밀번호가 올바르지 않습니다.** 다시 확인해 주세요.", parse_mode="Markdown")


async def cmd_deauth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """대화방 인증 해제 (/deauth)"""
    chat_id = update.effective_chat.id
    set_chat_authenticated(chat_id, False)
    await update.effective_message.reply_text(
        "🔒 이 대화방의 인증이 해제되어 **보안 잠금 상태**로 변경되었습니다.\n"
        "다시 사용하려면 `/auth [비밀번호]`를 입력하세요.",
        parse_mode="Markdown"
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """도움말 메시지"""
    text = (
        "📖 **자동 번역 봇 도움말**\n\n"
        "1. **지원 언어 및 동작 방식**\n"
        "   - 🇰🇷 한국어 ↔ 🇺🇸 영어 ↔ 🇻🇳 베트남어 자동 감지 번역\n"
        "   - 사소한 리액션(`아멘`, `Amen`, `ok`, `ㅋㅋ`), 이모티콘은 자동 필터링됩니다.\n\n"
        "2. **주요 명령어**\n"
        "   - `/lang all` : 한·영·베 통합 모드 (기본값)\n"
        "   - `/lang ko-vi` : 한-베 전용 모드 (한국어 ↔ 베트남어)\n"
        "   - `/lang ko-en` : 한-영 전용 모드 (한국어 ↔ 영어)\n"
        "   - `/auth [비밀번호]` : 대화방 인증\n"
        "   - `/translate on/off` : 번역 켜기/끄기\n"
        "   - `/status` : 현재 상태 확인"
    )
    await update.effective_message.reply_text(text, parse_mode="Markdown")


async def cmd_translate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """번역 ON/OFF 제어"""
    chat_id = update.effective_chat.id

    if ACCESS_PASSWORD and not is_chat_authenticated(chat_id):
        await update.effective_message.reply_text("🔒 비밀번호 인증이 필요합니다. `/auth [비밀번호]`를 먼저 입력해 주세요.", parse_mode="Markdown")
        return

    args = context.args
    if not args or args[0].lower() not in ["on", "off"]:
        current = "켜짐(ON)" if is_translation_enabled(chat_id) else "꺼짐(OFF)"
        await update.effective_message.reply_text(
            f"현재 이 대화방의 자동 번역 상태는 **{current}** 입니다.\n"
            "설정을 변경하려면 `/translate on` 또는 `/translate off` 를 입력하세요.",
            parse_mode="Markdown"
        )
        return

    action = args[0].lower()
    enabled = (action == "on")
    set_translation_enabled(chat_id, enabled)

    status_msg = "활성화되었습니다. (자동 번역 시작)" if enabled else "비활성화되었습니다. (자동 번역 중지)"
    await update.effective_message.reply_text(f"✅ 이 대화방의 자동 번역이 **{status_msg}**", parse_mode="Markdown")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """현재 봇 상태 및 설정 점검"""
    chat_id = update.effective_chat.id
    authenticated = is_chat_authenticated(chat_id)
    enabled = is_translation_enabled(chat_id)
    mode = get_chat_lang_mode(chat_id)
    engine_name = translation_service.get_engine_name()

    security_status = "🔓 인증 완료" if authenticated else "🔒 미인증 (잠김)"
    if not ACCESS_PASSWORD:
        security_status = "공개 모드 (비밀번호 없음)"

    status_text = (
        "📊 **현재 봇 상태**\n\n"
        f"• 보안 인증 상태: {security_status}\n"
        f"• 언어 모드: `{mode}`\n"
        f"• 이 대화방 번역 활성화: {'✅ 켜짐 (ON)' if enabled else '❌ 꺼짐 (OFF)'}\n"
        f"• 현재 번역 엔진: `{engine_name}`\n"
        f"• 대화방 ID: `{chat_id}`\n"
    )
    await update.effective_message.reply_text(status_text, parse_mode="Markdown")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """채팅 메시지를 감지하여 다국어 판별 후 번역 답장"""
    message = update.effective_message
    if not message or not message.text:
        return

    if message.from_user and message.from_user.is_bot:
        return
    if message.text.startswith('/'):
        return

    chat_id = update.effective_chat.id

    # 1. 비밀번호 인증 확인
    if ACCESS_PASSWORD and not is_chat_authenticated(chat_id):
        if update.effective_chat.type == "private":
            await message.reply_text(
                "🔒 비밀번호 인증이 필요합니다.\n"
                "`/auth [비밀번호]` 를 입력해 잠금을 해제해 주세요.",
                parse_mode="Markdown"
            )
        return

    # 2. 해당 채팅방의 번역 기능이 꺼져 있으면 무시
    if not is_translation_enabled(chat_id):
        return

    text = message.text

    # 3. 언어 감지 및 사소한 리액션 필터링
    source_lang = detect_source_language(text)
    if not source_lang:
        return

    # 4. 방 설정 언어 모드 확인
    mode = get_chat_lang_mode(chat_id)
    targets = get_translation_targets(source_lang, mode=mode)
    if not targets:
        return

    # 5. 번역 수행 및 결과 조합
    results = []
    for target_code, flag in targets:
        translated = translation_service.translate(text, target_lang=target_code)
        if translated:
            results.append(f"{flag} {translated}")

    if not results:
        return

    reply_content = "\n".join(results)

    # 6. 원본 메시지에 인용 답장 (Quote Reply)
    try:
        await message.reply_text(
            reply_content,
            reply_to_message_id=message.message_id,
        )
    except Exception as e:
        logger.error(f"메시지 답장 실패: {e}")


class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Telegram Translator Bot is active and running!")

    def log_message(self, format, *args):
        pass


def start_health_check_server(port: int):
    """Render 무료 웹 서비스 절전 방지 및 상태 확인을 위한 백그라운드 HTTP 서버"""
    try:
        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        logger.info(f"Render 헬스체크 웹 서버가 포트 {port}에서 구동되었습니다.")
    except Exception as e:
        logger.warning(f"헬스체크 웹 서버 구동 실패: {e}")


def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN이 .env 파일에 설정되어 있지 않습니다!")
        print("\n[오류] TELEGRAM_BOT_TOKEN이 누락되었습니다. .env 파일을 확인해 주세요.\n")
        return

    port = int(os.getenv("PORT", "8080"))
    start_health_check_server(port)

    logger.info(f"텔레그램 번역 봇 초기화 (엔진: {translation_service.get_engine_name()})")
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # 명령어 핸들러 등록
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("lang", cmd_lang))
    app.add_handler(CommandHandler("auth", cmd_auth))
    app.add_handler(CommandHandler("deauth", cmd_deauth))
    app.add_handler(CommandHandler("translate", cmd_translate))
    app.add_handler(CommandHandler("status", cmd_status))

    # 일반 텍스트 메시지 핸들러 등록
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("텔레그램 번역 봇이 성공적으로 실행되었습니다. 메시지 수신 대기 중...")
    app.run_polling()


if __name__ == "__main__":
    main()
