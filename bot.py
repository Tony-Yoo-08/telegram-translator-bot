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
    ChatMemberHandler,
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
    1. 포럼 주제(Topic) 스레드 ID 보존
    2. 인용 답장(reply_text) 시도
    3. 원본 메시지가 삭제된 경우 일반 메시지(send_message)로 자동 폴백
    """
    if not message:
        return None

    if getattr(message, "is_topic_message", False) and message.message_thread_id:
        kwargs.setdefault("message_thread_id", message.message_thread_id)

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


async def is_group_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    권한 확인: 봇 총괄 관리자이거나, 해당 텔레그램 그룹의 실제 방장(Owner)/관리자(Admin)인지 확인
    """
    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat or chat.type == "private":
        return False

    # 1. 봇 총괄 관리자인 경우
    if is_admin(user.id):
        return True

    # 2. 텔레그램 자체 그룹 방장(creator) 또는 관리자(administrator)인 경우
    try:
        member = await context.bot.get_chat_member(chat_id=chat.id, user_id=user.id)
        return member.status in ["creator", "administrator"]
    except Exception:
        return False


async def notify_admins_new_group(chat, inviter, context: ContextTypes.DEFAULT_TYPE):
    """새 그룹방 연결 시 총괄 관리자들에게 1:1 원격 승인/거절 버튼 전송"""
    admin_ids = db.get_admin_ids()
    if not admin_ids:
        return

    inviter_name = f"@{inviter.username}" if inviter and inviter.username else (f"ID: {inviter.id}" if inviter else "알 수 없음")
    is_forum = bool(getattr(chat, "is_forum", False))

    text = (
        f"🔔 **신규 그룹 대화방 초대 감지**\n\n"
        f"• 그룹명: **{chat.title or '이름 없음'}**\n"
        f"• 그룹 ID: `{chat.id}`\n"
        f"• 포럼(주제) 여부: {'예' if is_forum else '아니오'}\n"
        f"• 초대한 사람: {inviter_name}\n\n"
        f"이 대화방에서 번역 봇 작동을 승인하시겠습니까?"
    )

    keyboard = [
        [
            InlineKeyboardButton("✅ 그룹 승인", callback_data=f"allow_grp:{chat.id}"),
            InlineKeyboardButton("❌ 거절 및 퇴장", callback_data=f"ban_grp:{chat.id}"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    for a_id in admin_ids:
        try:
            await context.bot.send_message(
                chat_id=a_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        except Exception:
            pass


async def track_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """S11: 봇이 그룹에 추가되거나 퇴장당할 때의 이벤트 감지"""
    result = update.my_chat_member
    if not result:
        return
    chat = result.chat
    new_status = result.new_chat_member.status
    inviter = result.from_user

    if chat.type in ["group", "supergroup"]:
        if new_status in ["member", "administrator"]:
            is_forum = bool(getattr(chat, "is_forum", False))
            db.register_group_pending(chat.id, chat.title or "", is_forum)
            await notify_admins_new_group(chat, inviter, context)
        elif new_status in ["left", "kicked"]:
            db.delete_group(chat.id)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """S4, S5: 딥링크 입장 게이트"""
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    if not message or not user or chat.type != "private":
        return

    if check_auth_abuse(user.id):
        return

    args = context.args
    input_payload = args[0].strip() if args else ""

    if not verify_payload(input_payload, INVITE_PAYLOAD):
        record_failed_auth(user.id)
        return

    # S5: 첫 관리자 부트스트랩 (1회성)
    if not db.is_bootstrap_done():
        db.set_user_role(user.id, "admin", user.username or "")
        db.complete_bootstrap()
        logger.info("S5: Initial bootstrap completed.")
        await safe_reply(
            message,
            "✅ **초기 총괄 관리자로 등록되었습니다.**\n"
            "이제 모든 관리 및 원격 승인 명령을 사용할 수 있습니다.\n\n"
            "• `/groups` : 봇이 연결된 대화방 목록 확인 및 원격 통제\n"
            "• `/status` : 봇 상태 점검\n"
            "• `/myid` : 본인 식별자 확인\n"
            "• `/help` : 전체 도움말"
        )
        return

    current_role = db.get_user_role(user.id)
    if current_role in ["admin", "member"]:
        await safe_reply(message, "✅ 이미 승인된 사용자입니다. 봇을 정상 이용하실 수 있습니다.")
        return

    # 신규 멤버 대기 등록 및 총괄 관리자 알림
    db.set_user_role(user.id, "pending", user.username or "")
    await safe_reply(message, "입장 확인이 접수되었습니다. 관리자 승인을 기다려 주세요.")

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
    """관리자 인라인 버튼 클릭 처리 (멤버 승인 및 그룹 원격 승인/퇴장)"""
    query = update.callback_query
    await query.answer()

    admin_user = update.effective_user
    if not is_admin(admin_user.id):
        return

    data = query.data or ""
    if ":" not in data:
        return

    action, target_id_str = data.split(":", 1)
    target_id = int(target_id_str)

    # 1. 멤버 승인/거절
    if action == "approve":
        db.set_user_role(target_id, "member")
        try:
            await query.edit_message_text(f"✅ 사용자(ID: {target_id}) 승인이 완료되었습니다.")
            await context.bot.send_message(
                chat_id=target_id,
                text="🎉 봇 사용이 승인되었습니다. 이제 대화방에서 번역 기능을 이용하실 수 있습니다."
            )
        except Exception:
            pass
    elif action == "reject":
        db.set_user_role(target_id, "rejected")
        try:
            await query.edit_message_text(f"❌ 사용자(ID: {target_id}) 입장을 거절했습니다.")
        except Exception:
            pass

    # 2. 그룹 원격 승인 / 퇴장
    elif action == "allow_grp":
        db.set_group_allowed(target_id, True)
        conf = db.get_group_config(target_id)
        try:
            await query.edit_message_text(f"✅ 그룹 대화방(ID: `{target_id}`)이 정상 승인되었습니다.", parse_mode="Markdown")
            if conf.get("is_forum", False):
                guide = (
                    "✅ **이 그룹 대화방이 총괄 관리자로부터 원격 승인되었습니다!**\n\n"
                    "🛡️ **안전 모드 적용**: 도배 방지를 위해 기본적으로 모든 주제에서 번역이 꺼져 있습니다.\n"
                    "👉 방장/관리자님은 번역이 필요한 주제(토픽)에 들어가서 **`/topic on`** 을 입력해 주세요!"
                )
            else:
                guide = "✅ **이 그룹 대화방이 총괄 관리자로부터 원격 승인되었습니다.** 이제 번역이 동작합니다."
            await context.bot.send_message(chat_id=target_id, text=guide, parse_mode="Markdown")
        except Exception:
            pass

    elif action == "ban_grp":
        db.set_group_allowed(target_id, False)
        try:
            await query.edit_message_text(f"❌ 그룹 대화방(ID: `{target_id}`) 입장을 거절하고 퇴장했습니다.", parse_mode="Markdown")
            await context.bot.leave_chat(chat_id=target_id)
            db.delete_group(target_id)
        except Exception:
            pass


async def cmd_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """총괄 관리자 전용: 봇이 연결된 모든 대화방 목록 및 상태 조회 (1:1 DM 전용)"""
    user = update.effective_user
    chat = update.effective_chat
    message = update.effective_message

    if not message or chat.type != "private" or not is_admin(user.id):
        return

    groups = db.get_all_groups()
    if not groups:
        await safe_reply(message, "현재 봇이 연결된 그룹 대화방이 없습니다.")
        return

    lines = ["📋 **봇 연결 그룹 대화방 목록**\n"]
    for idx, g in enumerate(groups, 1):
        status_icon = "🟢 승인됨" if g["is_allowed"] else "🟡 대기중(미승인)"
        forum_badge = " (주제별 포럼)" if g["is_forum"] else ""
        lines.append(
            f"**{idx}. {g['title'] or '이름 없음'}**{forum_badge}\n"
            f"• ID: `{g['chat_id']}` | 상태: {status_icon}\n"
            f"• 모드: `{g['lang_mode']}` | 번역 기능: {'ON' if g['is_enabled'] else 'OFF'}\n"
        )

    lines.append(
        "🛠️ **원격 관리 명령**:\n"
        "• `/approve_group [ID]` : 원격 승인\n"
        "• `/ban_group [ID]` : 원격 차단 및 봇 자동 퇴장"
    )

    await safe_reply(message, "\n".join(lines), parse_mode="Markdown")


async def cmd_approve_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """총괄 관리자 전용: 대화방 ID로 원격 승인"""
    user = update.effective_user
    message = update.effective_message

    if not message or not is_admin(user.id):
        return

    args = context.args
    if not args:
        await safe_reply(message, "사용법: `/approve_group [대화방ID]`", parse_mode="Markdown")
        return

    try:
        target_chat_id = int(args[0].strip())
        db.set_group_allowed(target_chat_id, True)
        await safe_reply(message, f"✅ 대화방(`{target_chat_id}`)이 원격 승인되었습니다.", parse_mode="Markdown")
        try:
            await context.bot.send_message(
                chat_id=target_chat_id,
                text="✅ 이 대화방이 총괄 관리자로부터 원격 승인되었습니다. 이제 번역이 동작합니다."
            )
        except Exception:
            pass
    except Exception as e:
        await safe_reply(message, f"오류 발생: {e}")


async def cmd_ban_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """총괄 관리자 전용: 대화방 ID로 원격 차단 및 봇 자동 퇴장"""
    user = update.effective_user
    message = update.effective_message

    if not message or not is_admin(user.id):
        return

    args = context.args
    if not args:
        await safe_reply(message, "사용법: `/ban_group [대화방ID]`", parse_mode="Markdown")
        return

    try:
        target_chat_id = int(args[0].strip())
        db.set_group_allowed(target_chat_id, False)
        try:
            await context.bot.leave_chat(chat_id=target_chat_id)
        except Exception:
            pass
        db.delete_group(target_chat_id)
        await safe_reply(message, f"🔒 대화방(`{target_chat_id}`)이 차단되었으며 봇이 해당 방에서 퇴장했습니다.", parse_mode="Markdown")
    except Exception as e:
        await safe_reply(message, f"오류 발생: {e}")


async def cmd_grant_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """S5: 총괄 관리자 전용 - 보조 관리자 권한 부여 (1:1 DM 전용)"""
    user = update.effective_user
    chat = update.effective_chat
    message = update.effective_message

    if not message or chat.type != "private" or not is_admin(user.id):
        return

    args = context.args
    if not args:
        await safe_reply(message, "사용법: `/grant_admin [대상유저ID]`", parse_mode="Markdown")
        return

    try:
        target_uid = int(args[0].strip())
        db.set_user_role(target_uid, "admin")
        await safe_reply(message, f"✅ 사용자(`{target_uid}`)에게 총괄 관리자 권한을 부여했습니다.", parse_mode="Markdown")
    except Exception as e:
        await safe_reply(message, f"오류 발생: {e}")


async def cmd_revoke_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """S5: 총괄 관리자 권한 회수 (Lockout 방지 검사)"""
    user = update.effective_user
    chat = update.effective_chat
    message = update.effective_message

    if not message or chat.type != "private" or not is_admin(user.id):
        return

    args = context.args
    if not args:
        await safe_reply(message, "사용법: `/revoke_admin [대상유저ID]`", parse_mode="Markdown")
        return

    try:
        target_uid = int(args[0].strip())
        # 관리자 1명 이상 보장
        if target_uid == user.id and db.count_admins() <= 1:
            await safe_reply(message, "❌ 마지막 남은 관리자는 본인의 관리자 권한을 회수할 수 없습니다.")
            return

        db.set_user_role(target_uid, "member")
        await safe_reply(message, f"✅ 사용자(`{target_uid}`)의 관리자 권한을 회수했습니다.", parse_mode="Markdown")
    except Exception as e:
        await safe_reply(message, f"오류 발생: {e}")


async def cmd_allow_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """방 안에서 직접 승인하는 현장 명령어 (총괄 관리자 전용)"""
    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message

    if not message or chat.type == "private" or not is_admin(user.id):
        return

    is_forum = bool(getattr(chat, "is_forum", False))
    db.set_group_allowed(chat.id, True, chat.title or "", is_forum=is_forum)

    if is_forum:
        guide = (
            "✅ **그룹 대화방이 승인되었습니다! (주제별 포럼 감지)**\n\n"
            "🛡️ **초기 안전 모드 적용**: 도배 방지를 위해 기본적으로 모든 주제에서 번역이 꺼져(대기) 있습니다.\n\n"
            "👉 방장/관리자님은 번역을 원하는 특정 주제(토픽)에 들어가서 **`/topic on`** 을 입력해 주세요!\n"
            "*(모든 주제에서 전부 번역되길 원하시면 `/topic all` 입력)*"
        )
    else:
        guide = "✅ **그룹 대화방이 정상 승인되었습니다.** 이제 번역이 동작합니다."

    await safe_reply(message, guide, parse_mode="Markdown")


async def cmd_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """주제별(토픽별) 번역 제어 (총괄 관리자 및 해당 방의 텔레그램 관리자 모두 사용 가능)"""
    chat = update.effective_chat
    message = update.effective_message

    if not message or chat.type == "private":
        return

    # S11: 미승인 그룹에서는 무반응
    if not db.is_group_allowed(chat.id):
        return

    if not await is_group_admin(update, context):
        await safe_reply(message, "안내: 토픽 설정은 대화방 관리자만 변경할 수 있습니다.")
        return

    is_forum = bool(getattr(chat, "is_forum", False))
    if not is_forum:
        await safe_reply(message, "안내: 이 방은 주제(포럼) 기능이 없는 일반 그룹방입니다. 전체 번역 제어는 `/translate on/off`를 사용하세요.")
        return

    args = context.args
    thread_id = message.message_thread_id

    if not args or args[0].lower() not in ["on", "off", "all"]:
        active = db.is_topic_translation_enabled(chat.id, thread_id, is_forum=True)
        conf = db.get_group_config(chat.id)
        topic_mode = conf.get("topic_mode", "selective")
        status_str = "🟢 켜짐(ON)" if active else "⚪ 꺼짐(OFF)"
        mode_desc = "선택된 주제만 번역 (기본)" if topic_mode == "selective" else "모든 주제 번역"

        await safe_reply(
            message,
            f"📌 **현재 주제(Topic ID: {thread_id or '메인'}) 번역 상태: {status_str}**\n"
            f"• 그룹 토픽 모드: `{mode_desc}`\n\n"
            "**명령어 안내**:\n"
            "• `/topic on` : **현재 이 주제에서만** 번역 켜기 (다른 방 조용)\n"
            "• `/topic off` : 현재 이 주제에서 번역 끄기\n"
            "• `/topic all` : 이 그룹의 모든 주제에서 번역 켜기",
            parse_mode="Markdown"
        )
        return

    action = args[0].lower()

    if action == "all":
        db.enable_all_topics(chat.id)
        await safe_reply(message, "🌐 이 그룹의 **모든 주제에서 번역이 활성화**되었습니다. (전체 모드)", parse_mode="Markdown")
    elif action == "on":
        target_thread = thread_id if thread_id is not None else 1
        db.enable_topic(chat.id, target_thread)
        await safe_reply(
            message,
            f"✅ **현재 주제(Topic ID: {target_thread})에서 번역이 활성화되었습니다!**\n"
            "다른 주제에서는 번역하지 않고, 이 주제에서 올라오는 대화만 깔끔하게 번역됩니다.",
            parse_mode="Markdown"
        )
    elif action == "off":
        target_thread = thread_id if thread_id is not None else 1
        db.disable_topic(chat.id, target_thread)
        await safe_reply(message, f"🔒 **현재 주제(Topic ID: {target_thread})에서 번역이 꺼졌습니다.**", parse_mode="Markdown")


async def cmd_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """언어 모드 설정 (총괄 관리자 및 해당 방의 텔레그램 관리자 모두 변경 가능)"""
    chat = update.effective_chat
    message = update.effective_message

    if not message:
        return

    # S11: 미승인 그룹에서는 무반응
    if chat.type != "private" and not db.is_group_allowed(chat.id):
        return

    if chat.type != "private" and not await is_group_admin(update, context):
        await safe_reply(message, "안내: 설정 변경은 대화방 관리자만 가능합니다.")
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
    """번역 켜기/끄기 (총괄 관리자 및 해당 방의 텔레그램 관리자 모두 제어 가능)"""
    chat = update.effective_chat
    message = update.effective_message

    if not message:
        return

    # S11: 미승인 그룹에서는 무반응
    if chat.type != "private" and not db.is_group_allowed(chat.id):
        return

    if chat.type != "private" and not await is_group_admin(update, context):
        await safe_reply(message, "안내: 설정 변경은 대화방 관리자만 가능합니다.")
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


async def cmd_myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message
    if not message or not user:
        return
    if chat.type != "private" and not db.is_group_allowed(chat.id):
        return
    await safe_reply(message, f"본인의 식별자(ID)입니다:\n`{user.id}`", parse_mode="Markdown")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message

    if not message or not user:
        return

    is_group = (chat.type != "private")
    if is_group and not db.is_group_allowed(chat.id):
        return

    if not is_approved_member(user.id):
        return

    conf = db.get_group_config(chat.id)
    is_forum = bool(getattr(chat, "is_forum", False))
    group_auth = conf.get("is_allowed", False) if is_group else True
    enabled = conf.get("is_enabled", True)
    mode = conf.get("lang_mode", "all")

    topic_info = ""
    if is_forum:
        thread_id = message.message_thread_id
        active = db.is_topic_translation_enabled(chat.id, thread_id, is_forum=True)
        topic_mode = conf.get("topic_mode", "selective")
        topic_info = (
            f"• 대화방 구조: 포럼 (주제별 대화방)\n"
            f"• 그룹 토픽 모드: {'선택된 주제만 번역' if topic_mode == 'selective' else '모든 주제 번역'}\n"
            f"• 현재 주제(ID: {thread_id or '메인'}): {'🟢 켜짐(ON)' if active else '⚪ 꺼짐(대기)'}\n"
        )

    status_text = (
        "📊 **현재 상태**\n\n"
        f"• 사용자 권한: {'총괄 관리자' if is_admin(user.id) else '승인 멤버'}\n"
        f"• 대화방 유형: {'그룹 대화방' if is_group else '개인 1:1 대화'}\n"
        f"• 대화방 승인: {'✅ 승인됨' if group_auth else '🔒 미승인'}\n"
        f"{topic_info}"
        f"• 번역 기능: {'✅ 켜짐(ON)' if enabled else '❌ 꺼짐(OFF)'}\n"
        f"• 언어 모드: `{mode}`\n"
        f"• 엔진: `{translation_service.get_engine_name()}`\n"
    )
    await safe_reply(message, status_text, parse_mode="Markdown")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message

    if not message or not user:
        return

    if chat.type != "private" and not db.is_group_allowed(chat.id):
        return

    if not is_approved_member(user.id):
        return

    admin_extra = ""
    if chat.type == "private" and is_admin(user.id):
        admin_extra = (
            "\n👑 **총괄 관리자 전용 (1:1 DM)**:\n"
            "• `/groups` : 연결된 대화방 목록 조회 및 원격 승인/퇴장\n"
            "• `/approve_group [ID]` : 대화방 원격 승인\n"
            "• `/ban_group [ID]` : 대화방 원격 차단/퇴장\n"
            "• `/grant_admin [ID]` : 보조 관리자 권한 부여\n"
            "• `/revoke_admin [ID]` : 관리자 권한 회수\n"
        )

    text = (
        "📖 **사용 안내**\n\n"
        "• 한국어 ↔ 영어 ↔ 베트남어 실시간 자동 감지 번역\n"
        "• 단답형 리액션/감탄사는 자동 필터링\n\n"
        "📌 **주요 명령어**:\n"
        "• `/status` : 현재 설정 및 권한 상태 확인\n"
        "• `/topic on | off | all` : 포럼 주제별 번역 제어 (방장/관리자)\n"
        "• `/lang all | ko-vi | ko-en` : 언어 모드 설정 (방장/관리자)\n"
        "• `/translate on | off` : 번역 켜기/끄기 (방장/관리자)\n"
        "• `/myid` : 본인 식별 번호 확인\n"
        f"{admin_extra}"
    )
    await safe_reply(message, text, parse_mode="Markdown")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    # S11: 그룹 대화방 처리
    if chat.type != "private":
        # 아직 DB에 등록되지 않은 신규 그룹인 경우 등록 및 총괄 관리자 알림
        if not db.is_group_registered(chat.id):
            is_forum = bool(getattr(chat, "is_forum", False))
            db.register_group_pending(chat.id, chat.title or "", is_forum)
            await notify_admins_new_group(chat, user, context)
            return

        # 미승인 그룹인 경우 완전 무반응 (S11)
        if not db.is_group_allowed(chat.id):
            return

        is_forum = bool(getattr(chat, "is_forum", False))
        if not db.is_topic_translation_enabled(chat.id, message.message_thread_id, is_forum):
            return

        conf = db.get_group_config(chat.id)
        mode = conf.get("lang_mode", "all")
    else:
        if not is_approved_member(user.id):
            return
        mode = "all"

    text = message.text

    source_lang = detect_source_language(text)
    if not source_lang:
        return

    targets = get_translation_targets(source_lang, mode=mode)
    if not targets:
        return

    results = []
    for target_code, flag in targets:
        translated = translation_service.translate(text, target_lang=target_code)
        if translated:
            results.append(f"{flag} {translated}")

    if not results:
        return

    reply_content = "\n".join(results)

    await safe_reply(
        message,
        reply_content,
        reply_to_message_id=message.message_id,
    )


async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    err = context.error
    if not err:
        return
    err_str = str(err).lower()
    err_type = type(err).__name__
    if "message to be replied not found" in err_str:
        logger.warning("Notice: Target message was deleted before reply was sent.")
        return
    if "conflict" in err_str or err_type == "Conflict":
        logger.warning("Notice: Instance transition detected (Conflict). Active container is taking over.")
        return
    logger.error(f"Handled exception: {err_type}")


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
    app.add_handler(CommandHandler("groups", cmd_groups))
    app.add_handler(CommandHandler("approve_group", cmd_approve_group))
    app.add_handler(CommandHandler("ban_group", cmd_ban_group))
    app.add_handler(CommandHandler("grant_admin", cmd_grant_admin))
    app.add_handler(CommandHandler("revoke_admin", cmd_revoke_admin))
    app.add_handler(CommandHandler("allow_group", cmd_allow_group))
    app.add_handler(CommandHandler("topic", cmd_topic))
    app.add_handler(CommandHandler("lang", cmd_lang))
    app.add_handler(CommandHandler("translate", cmd_translate))
    app.add_handler(ChatMemberHandler(track_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(CallbackQueryHandler(handle_callback_query))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.add_error_handler(global_error_handler)

    app.run_polling()


if __name__ == "__main__":
    main()
