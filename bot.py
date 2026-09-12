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

from translator import UnifiedTranslationService, detect_target_language

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

# 통합 번역 서비스 인스턴스 생성 (DeepL 키가 없으면 자동으로 무료 엔진 작동)
translation_service = UnifiedTranslationService(DEEPL_API_KEY)

# 채팅방별 번역 활성화 여부 저장 파일
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


# 전역 설정 메모리 캐시 (chat_id: bool)
# True: 번역 켜짐 (기본값), False: 번역 꺼짐
chat_settings = load_chat_settings()


def is_translation_enabled(chat_id: int) -> bool:
    """채팅방의 번역 활성화 여부 반환 (기본값: True)"""
    return chat_settings.get(str(chat_id), True)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """봇 시작 및 안내 메시지"""
    engine_name = translation_service.get_engine_name()
    text = (
        "👋 안녕하세요! **한-영 / 영-한 실시간 자동 번역 봇**입니다.\n\n"
        "대화방에 한국어를 입력하면 **영어(🇺🇸)**로,\n"
        "영어를 입력하면 **한국어(🇰🇷)**로 자동으로 번역하여 답장해 드립니다.\n\n"
        f"⚙️ **현재 번역 엔진**: `{engine_name}`\n\n"
        "📌 **주요 명령어**\n"
        "• `/translate on` : 이 대화방의 자동 번역 켜기\n"
        "• `/translate off` : 이 대화방의 자동 번역 끄기\n"
        "• `/status` : 현재 대화방 번역 설정 및 봇 상태 확인\n"
        "• `/help` : 사용 안내 보기\n\n"
        "⚠️ **그룹방 적용 시 주의사항**\n"
        "그룹방에서 모든 메시지를 감지하려면 `@BotFather`에서 **Group Privacy**를 꺼주시거나 (`/setprivacy` -> `Disable`), "
        "봇을 그룹 관리자(Admin)로 지정해 주셔야 합니다."
    )
    await update.effective_message.reply_text(text, parse_mode="Markdown")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """도움말 메시지"""
    text = (
        "📖 **자동 번역 봇 도움말**\n\n"
        "1. **작동 방식**\n"
        "   - 한국어 입력 ➡️ 영어 번역 (🇺🇸)\n"
        "   - 영어 입력 ➡️ 한국어 번역 (🇰🇷)\n"
        "   - 짧은 감탄사(`ㅋㅋ`, `ok`), 이모티콘, 링크는 자동 필터링됩니다.\n\n"
        "2. **명령어 안내**\n"
        "   - `/translate on` : 자동 번역 활성화\n"
        "   - `/translate off` : 자동 번역 일시 중지\n"
        "   - `/status` : 봇 상태 및 현재 사용 중인 번역 엔진 점검\n"
    )
    await update.effective_message.reply_text(text, parse_mode="Markdown")


async def cmd_translate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """번역 ON/OFF 제어"""
    chat_id = update.effective_chat.id
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
    chat_settings[str(chat_id)] = enabled
    save_chat_settings(chat_settings)

    status_msg = "활성화되었습니다. (자동 번역 시작)" if enabled else "비활성화되었습니다. (자동 번역 중지)"
    await update.effective_message.reply_text(f"✅ 이 대화방의 자동 번역이 **{status_msg}**", parse_mode="Markdown")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """현재 봇 상태 및 설정 점검"""
    chat_id = update.effective_chat.id
    enabled = is_translation_enabled(chat_id)
    engine_name = translation_service.get_engine_name()

    status_text = (
        "📊 **현재 봇 상태**\n\n"
        f"• 이 대화방 번역 활성화: {'✅ 켜짐 (ON)' if enabled else '❌ 꺼짐 (OFF)'}\n"
        f"• 현재 번역 엔진: `{engine_name}`\n"
        f"• 대화방 ID: `{chat_id}`\n"
    )
    await update.effective_message.reply_text(status_text, parse_mode="Markdown")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """채팅 메시지를 감지하여 언어 판별 후 번역 답장"""
    message = update.effective_message
    if not message or not message.text:
        return

    # 1. 봇이 작성한 메시지이거나 명령어인 경우 무시 (무한 루프 방지)
    if message.from_user and message.from_user.is_bot:
        return
    if message.text.startswith('/'):
        return

    # 2. 해당 채팅방의 번역 기능이 꺼져 있으면 무시
    chat_id = update.effective_chat.id
    if not is_translation_enabled(chat_id):
        return

    text = message.text

    # 3. 언어 판별 및 번역 대상 확인
    target_lang, flag = detect_target_language(text)
    if not target_lang:
        return

    # 4. 번역 수행 (무료 엔진 또는 DeepL)
    translated_text = translation_service.translate(text, target_lang=target_lang)
    if not translated_text:
        return

    # 5. 원본 메시지에 인용 답장 (Quote Reply)
    reply_content = f"{flag} {translated_text}"
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
        # 헬스체크 ping 로그로 터미널이 도배되지 않도록 음소거
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

    # Render 환경의 포트 감지 (기본 8080)
    port = int(os.getenv("PORT", "8080"))
    start_health_check_server(port)

    logger.info(f"텔레그램 번역 봇 초기화 (엔진: {translation_service.get_engine_name()})")
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # 명령어 핸들러 등록
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("translate", cmd_translate))
    app.add_handler(CommandHandler("status", cmd_status))

    # 일반 텍스트 메시지 핸들러 등록
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("텔레그램 번역 봇이 성공적으로 실행되었습니다. 메시지 수신 대기 중...")
    app.run_polling()


if __name__ == "__main__":
    main()
