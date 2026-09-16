import os
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from dotenv import load_dotenv

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

import db
from security import (
    verify_payload,
    is_admin,
    is_approved_member,
    check_rate_limit,
    check_auth_abuse,
    record_failed_auth,
)
from translator import (
    UnifiedTranslationService,
    detect_source_language,
    get_translation_targets,
)

# S8: 로그 마스킹 및 최소 로깅 설정
logging.basicConfig(
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("AppLogger")

# S1: 환경변수 로드
current_dir = Path(__file__).parent
load_dotenv(current_dir / ".env")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
DEEPL_API_KEY = os.getenv("DEEPL_API_KEY", "").strip()
# S4: 추측 불가능한 비밀 입장 payload
INVITE_PAYLOAD = os.getenv("INVITE_PAYLOAD", "").strip()

# S4: 원자적 SQLite 데이터베이스 초기화
db.init_db()

# 번역 서비스 인스턴스
translation_service = UnifiedTranslationService(DEEPL_API_KEY)


async def safe_reply(message, text: str, **kwargs):
    """
    안전한 메시지 전송:
    1. 인용 답장(reply_text) 시도
    2. 원본 메시지가 삭제되었거나 대상을 찾을 수 없는 경우(Message to be replied not found),
       인용 파라미터를 제거하고 일반 메시지(send_message)로 자동 전환하여 100% 안전하게 전송
    """
    if not message:
        return None
    try:
        return await message.reply_text(text, **kwargs)
    except Exception as e:
        err_str = str(e).lower()
        if "not found" in err_str or "reply" in err_str:
            kwargs.pop("reply_to_message_id", None)
            kwargs.pop("quote", None)
            try:
                bot = message.get_bot() if hasattr(message, "get_bot") else message._bot
                return await bot.send_message(
                    chat_id=message.chat_id,
                    text=text,
                    **kwargs
                )
            except Exception as e2:
                logger.error(f"Fallback send failed: {type(e2).__name__}")
        else:
            logger.error(f"Reply failed: {type(e).__name__}")
        return None


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    S4, S5: Deep Link (/start <payload>) 진입 게이트
    """
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    if not message or not user:
        return

    # S11: 인증 및 관리 흐름은 반드시 1:1(DM)에서만 수행
    if chat.type != "private":
        return

    # S10: 인증 무차별 대입 차단 검사
    if check_auth_abuse(user.id):
        return

    args = context.args
    input_payload = args[0].strip() if args else ""

    # S4: payload 대조 (hmac 타이밍 공격 방지)
    # payload가 없거나 틀리면 일절 무반응 (명령어/기능 미노출)
    if not verify_payload(input_payload, INVITE_PAYLOAD):
        record_failed_auth(user.id)
        return

    # S5: 첫 관리자 등록 (1회성 부트스트랩 - 재기동 시 재발 방지)
    if not db.is_bootstrap_done():
        db.set_user_role(user.id, "admin", user.username or "")
        db.complete_bootstrap()
        logger.info("S5: Initial bootstrap completed.")
        await safe_reply(
            message,
            "✅ 초기 관리자로 등록되었습니다.\n"
            "이제 관리 명령을 사용하실 수 있습니다.\n\n"
            "• `/status` : 상태 확인\n"
            "• `/help` : 명령어 안내\n"
            "• `/myid` : 본인 식별자 확인 (비상 관리자 설정용)"
        )
        return

    # 이미 승인된 사용자인지 확인
    current_role = db.get_user_role(user.id)
    if current_role in ["admin", "member"]:
        await safe_reply(message, "✅ 이미 승인된 사용자입니다. 봇을 정상적으로 이용하실 수 있습니다.")
        return

    # S5: 새 사용자 승인 요청 대기 등록 및 관리자 알림
    db.set_user_role(user.id, "pending", user.username or "")
    await safe_reply(message, "입장 확인이 접수되었습니다. 관리자 승인을 기다려 주세요.")

    # 관리자들에게 승인/거절 버튼 전송
    admin_ids = db.get_admin_ids()
    keyboard = [
        [
            InlineKeyboardButton("승인", callback_data=f"approve:{user.id}"),
            InlineKeyboardButton("거절", callback_data=f"reject:{user.id}"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    for a_id in admin_ids:
        try:
            name_display = f"@{user.username}" if user.username else f"User {user.id}"
            await context.bot.send_message(
                chat_id=a_id,
                text=f"🔔 신규 사용자 입장 요청:\n• 대상: {name_display}\n• 식별 번호: `{user.id}`\n\n승인하시겠습니까?",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        except Exception:
            pass


async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    S5: 관리자 승인/거절 버튼 클릭 처리
    """
    query = update.callback_query
    await query.answer()

    admin_user = update.effective_user
    if not is_admin(admin_user.id):
        return

    data = query.data or ""
    if ":" not in data:
        return

    action, target_user_id_str = data.split(":", 1)
    target_user_id = int(target_user_id_str)

    if action == "approve":
        db.set_user_role(target_user_id, "member")
        try:
            await query.edit_message_text(f"✅ 사용자(ID: {target_user_id}) 승인이 완료되었습니다.")
        except Exception:
            pass
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text="🎉 봇 사용이 승인되었습니다. 이제 그룹방 및 1:1 대화에서 번역 기능을 이용하실 수 있습니다."
            )
        except Exception:
            pass
    elif action == "reject":
        db.set_user_role(target_user_id, "rejected")
        try:
            await query.edit_message_text(f"❌ 사용자(ID: {target_user_id}) 입장을 거절했습니다.")
        except Exception:
            pass


async def cmd_myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """S5: 비상 관리자 설정을 위해 본인 ID 확인"""
    user = update.effective_user
    message = update.effective_message
    if user and message:
        await safe_reply(message, f"본인의 식별자(ID)입니다:\n`{user.id}`", parse_mode="Markdown")


async def cmd_allow_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """S5, S11: 관리자 전용 - 현재 그룹을 승인된 그룹으로 등록"""
    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message

    if not message:
        return

    if chat.type == "private":
        await safe_reply(message, "이 명령은 승인하려는 그룹 대화방 안에서 실행해야 합니다.")
        return

    if not is_admin(user.id):
        return

    db.set_group_allowed(chat.id, True, chat.title or "")
    await safe_reply(message, "✅ 이 그룹 대화방이 정상 승인되었습니다. 이제 번역이 동작합니다.")


async def cmd_disallow_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """S5, S11: 관리자 전용 - 현재 그룹 승인 취소"""
    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message

    if not message or chat.type == "private":
        return

    if not is_admin(user.id):
        return

    db.set_group_allowed(chat.id, False, chat.title or "")
    await safe_reply(message, "🔒 이 그룹 대화방의 승인이 해제되었습니다.")


async def cmd_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """언어 모드 설정 (그룹에서는 관리자만 변경 가능, S11)"""
    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message

    if not message:
        return

    if chat.type != "private" and not is_admin(user.id):
        await safe_reply(message, "안내: 설정 변경은 관리자만 가능합니다.")
        return

    args = context.args
    if not args or args[0].lower() not in ["all", "ko-vi", "ko-en"]:
        conf = db.get_group_config(chat.id)
        current = conf.get("lang_mode", "all")
        await safe_reply(
            message,
            f"현재 언어 모드: **`{current}`**\n\n"
            "변경 명령어:\n"
            "• `/lang all` : 3개국어 통합 모드 (한국어 입력 시 영+베 동시 출력)\n"
            "• `/lang ko-vi` : 한-베 전용 모드 (한국어 ↔ 베트남어)\n"
            "• `/lang ko-en` : 한-영 전용 모드 (한국어 ↔ 영어)",
            parse_mode="Markdown"
        )
        return

    new_mode = args[0].lower()
    db.update_group_config(chat.id, lang_mode=new_mode)
    await safe_reply(message, f"✅ 언어 모드가 `{new_mode}`로 변경되었습니다.")


async def cmd_translate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """번역 켜기/끄기 (그룹에서는 관리자만 제어 가능)"""
    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message

    if not message:
        return

    if chat.type != "private" and not is_admin(user.id):
        await safe_reply(message, "안내: 설정 변경은 관리자만 가능합니다.")
        return

    args = context.args
    if not args or args[0].lower() not in ["on", "off"]:
        conf = db.get_group_config(chat.id)
        status_str = "ON" if conf.get("is_enabled", True) else "OFF"
        await safe_reply(message, f"현재 번역 상태: **{status_str}** (`/translate on/off`)")
        return

    enabled = (args[0].lower() == "on")
    db.update_group_config(chat.id, is_enabled=enabled)
    await safe_reply(message, f"✅ 번역 기능이 **{'켜짐(ON)' if enabled else '꺼짐(OFF)'}** 처리되었습니다.")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """S11: 상태 확인"""
    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message

    if not message or not is_approved_member(user.id):
        return

    conf = db.get_group_config(chat.id)
    is_group = (chat.type != "private")
    group_auth = conf.get("is_allowed", False) if is_group else True
    enabled = conf.get("is_enabled", True)
    mode = conf.get("lang_mode", "all")

    status_text = (
        "📊 **현재 상태**\n\n"
        f"• 사용자 권한: {'관리자' if is_admin(user.id) else '승인 멤버'}\n"
        f"• 대화방 유형: {'그룹 대화방' if is_group else '개인 1:1 대화'}\n"
        f"• 대화방 승인: {'✅ 승인됨' if group_auth else '🔒 미승인'}\n"
        f"• 번역 기능: {'✅ 켜짐(ON)' if enabled else '❌ 꺼짐(OFF)'}\n"
        f"• 언어 모드: `{mode}`\n"
        f"• 엔진: `{translation_service.get_engine_name()}`\n"
    )
    await safe_reply(message, status_text, parse_mode="Markdown")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """S11: 기본 도움말 안내"""
    user = update.effective_user
    message = update.effective_message

    if not message or not is_approved_member(user.id):
        return

    text = (
        "📖 **사용 안내**\n\n"
        "• 한국어 ↔ 영어 ↔ 베트남어 자동 감지 번역\n"
        "• 단답형 리액션/단문 감탄사는 자동 필터링\n\n"
        "📌 **주요 명령어**\n"
        "• `/status` : 현재 설정 및 권한 상태 확인\n"
        "• `/lang all | ko-vi | ko-en` : 언어 모드 설정\n"
        "• `/translate on | off` : 번역 켜기/끄기\n"
        "• `/allow_group` : (관리자) 그룹 대화방 승인\n"
        "• `/myid` : 본인 식별 번호 확인\n"
    )
    await safe_reply(message, text, parse_mode="Markdown")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """메시지 번역 핸들러 (S6, S10, S11 준수)"""
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    if not message or not message.text or not user:
        return
    if user.is_bot or message.text.startswith('/'):
        return

    # S10: 레이트 리밋 검사
    if not check_rate_limit(user.id):
        return

    # S11: 그룹인 경우 그룹 승인 여부 검사 (미인증 그룹은 완전 무반응)
    if chat.type != "private":
        if not db.is_group_allowed(chat.id):
            return
        conf = db.get_group_config(chat.id)
        if not conf.get("is_enabled", True):
            return
        mode = conf.get("lang_mode", "all")
    else:
        # 1:1 대화인 경우 사용자 승인 여부 검사
        if not is_approved_member(user.id):
            return
        mode = "all"

    text = message.text

    # 언어 감지 및 단순 리액션 필터링
    source_lang = detect_source_language(text)
    if not source_lang:
        return

    # 번역 대상 언어 추출
    targets = get_translation_targets(source_lang, mode=mode)
    if not targets:
        return

    # 번역 수행
    results = []
    for target_code, flag in targets:
        translated = translation_service.translate(text, target_lang=target_code)
        if translated:
            results.append(f"{flag} {translated}")

    if not results:
        return

    reply_content = "\n".join(results)

    # 원본 메시지 인용 답장 (원본 삭제 시 자동 일반 전송으로 폴백)
    await safe_reply(
        message,
        reply_content,
        reply_to_message_id=message.message_id,
    )


async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """S8: 전역 예외 처리기 - 메시지 삭제 등 무해한 오류로 인한 로그 오염 및 중단 방지"""
    err = context.error
    if err and "Message to be replied not found" in str(err):
        logger.warning("Notice: Target message was deleted before reply was sent.")
        return
    logger.error(f"Handled exception: {type(err).__name__}")


class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Service active.")

    def log_message(self, format, *args):
        pass


def start_health_check_server(port: int):
    try:
        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        logger.info(f"Health check server listening on {port}.")
    except Exception as e:
        logger.warning(f"Health server error: {type(e).__name__}")


def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN missing.")
        return

    port = int(os.getenv("PORT", "8080"))
    start_health_check_server(port)

    logger.info("Starting Telegram Bot application...")
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # 핸들러 등록
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("myid", cmd_myid))
    app.add_handler(CommandHandler("allow_group", cmd_allow_group))
    app.add_handler(CommandHandler("disallow_group", cmd_disallow_group))
    app.add_handler(CommandHandler("lang", cmd_lang))
    app.add_handler(CommandHandler("translate", cmd_translate))
    app.add_handler(CallbackQueryHandler(handle_callback_query))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # S8: 전역 예외 핸들러 등록
    app.add_error_handler(global_error_handler)

    app.run_polling()


if __name__ == "__main__":
    main()
