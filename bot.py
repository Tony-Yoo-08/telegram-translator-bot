import os
import re
import time
import logging
import threading
import asyncio
import html
from collections import OrderedDict
from typing import Optional
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
    determine_translation_plan,
    is_trivial_reaction,
)
from glossary import GlossaryManager

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
# 구글 스프레드시트 용어집 URL
GLOSSARY_SHEET_URL = os.getenv("GLOSSARY_SHEET_URL", "").strip()

# S4: 원자적 SQLite 데이터베이스 초기화
db.init_db()

# 용어집 관리자 인스턴스 초기화
glossary_manager = GlossaryManager(GLOSSARY_SHEET_URL)

# 번역 서비스 인스턴스 (용어집 후처리 연동)
translation_service = UnifiedTranslationService(DEEPL_API_KEY, glossary_manager=glossary_manager)


# --- 중복 번역 방지 캐시 (LRU / TTL) ---
# 1. 메시지 원본 텍스트 캐시: (chat_id, message_id) -> text
PROCESSED_MESSAGE_TEXTS = OrderedDict()
MAX_TEXT_CACHE = 5000

# 2. 봇의 번역 답장 메시지 ID 캐시: (chat_id, user_message_id) -> bot_reply_message_id
BOT_TRANSLATION_REPLIES = OrderedDict()
MAX_REPLY_CACHE = 5000

# 3. 동일 방/토픽 내 최근 번역된 내용 캐시: (chat_id, thread_id, user_id, normalized_text) -> timestamp
RECENT_TRANSLATED_TEXTS = OrderedDict()
MAX_RECENT_TEXTS = 3000
DUPLICATE_TEXT_WINDOW_SECONDS = 30  # 30초 이내 동일 사용자 중복 방지


def get_cached_message_text(chat_id: int, message_id: int) -> Optional[str]:
    """메시지 ID에 대해 캐시된 이전 텍스트 반환 (없으면 None)"""
    return PROCESSED_MESSAGE_TEXTS.get((chat_id, message_id))


def get_bot_reply_id(chat_id: int, message_id: int) -> Optional[int]:
    """특정 사용자 메시지에 대응하는 봇 번역 메시지 ID 반환"""
    return BOT_TRANSLATION_REPLIES.get((chat_id, message_id))


def record_message_cache(
    chat_id: int, message_id: int, text: str, reply_id: Optional[int] = None
):
    """메시지 텍스트 및 봇 답장 ID를 캐시에 기록 (LRU 유지)"""
    key = (chat_id, message_id)
    PROCESSED_MESSAGE_TEXTS[key] = text
    if len(PROCESSED_MESSAGE_TEXTS) > MAX_TEXT_CACHE:
        PROCESSED_MESSAGE_TEXTS.popitem(last=False)

    if reply_id is not None:
        BOT_TRANSLATION_REPLIES[key] = reply_id
        if len(BOT_TRANSLATION_REPLIES) > MAX_REPLY_CACHE:
            BOT_TRANSLATION_REPLIES.popitem(last=False)


def is_already_processed(chat_id: int, message_id: int) -> bool:
    """하위 호환용: 메시지 ID 캐시 존재 여부"""
    return (chat_id, message_id) in PROCESSED_MESSAGE_TEXTS


def mark_as_processed(
    chat_id: int, message_id: int, text: str = "", reply_id: Optional[int] = None
):
    """하위 호환용: 메시지 캐시 등록"""
    record_message_cache(chat_id, message_id, text, reply_id)


def is_duplicate_content(chat_id: int, thread_id: Optional[int], text: str, user_id: int = 0) -> bool:
    """해당 대화방/토픽에서 '동일 사용자'가 최근 30초 이내에 동일한 텍스트를 중복 전송했는지 확인"""
    norm = re.sub(r'\s+', ' ', text).strip().lower()
    target_thread = thread_id if thread_id is not None else 1
    key = (chat_id, target_thread, user_id, norm)
    now = time.time()

    if key in RECENT_TRANSLATED_TEXTS:
        last_time = RECENT_TRANSLATED_TEXTS[key]
        if now - last_time < DUPLICATE_TEXT_WINDOW_SECONDS:
            return True

    return False


def record_translated_content(chat_id: int, thread_id: Optional[int], text: str, user_id: int = 0):
    """번역된 내용을 캐시에 기록"""
    norm = re.sub(r'\s+', ' ', text).strip().lower()
    target_thread = thread_id if thread_id is not None else 1
    key = (chat_id, target_thread, user_id, norm)
    RECENT_TRANSLATED_TEXTS[key] = time.time()
    if len(RECENT_TRANSLATED_TEXTS) > MAX_RECENT_TEXTS:
        RECENT_TRANSLATED_TEXTS.popitem(last=False)


async def safe_reply(message, text: str, **kwargs):
    """
    안전한 메시지 전송:
    1. 포럼 주제(Topic) 스레드 ID 보존
    2. 인용 답장(reply_text) 시도
    3. 원본 메시지가 삭제된 경우 일반 메시지(send_message)로 자동 폴백
    """
    if not message:
        return None

    thread_id = None
    if getattr(message, "is_topic_message", False) and message.message_thread_id:
        thread_id = message.message_thread_id
        kwargs.setdefault("message_thread_id", thread_id)
    elif "message_thread_id" in kwargs:
        thread_id = kwargs["message_thread_id"]

    try:
        return await message.reply_text(text, **kwargs)
    except Exception as e:
        err_str = str(e).lower()
        if "not found" in err_str or "reply" in err_str:
            kwargs.pop("reply_to_message_id", None)
            kwargs.pop("quote", None)
            if thread_id:
                kwargs["message_thread_id"] = thread_id
            try:
                bot = getattr(message, "get_bot", lambda: None)() or getattr(message, "_bot", None)
                if bot:
                    return await bot.send_message(
                        chat_id=message.chat_id,
                        text=text,
                        **kwargs
                    )
            except Exception as e2:
                logger.error(f"Fallback send failed: {type(e2).__name__}")
        else:
            logger.error(f"Reply failed: {type(e).__name__} - {e}")
        return None


async def send_command_feedback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    delete_trigger: bool = True,
    **kwargs
):
    """
    대화방 청결 유지를 위한 스마트 명령어 피드백 전송:
    1. 1:1 개인 대화(DM)에서 실행된 경우: 개인 대화창에 정상 회신
    2. 그룹 대화방에서 실행된 경우:
       - 실행한 관리자의 1:1 봇 개인 대화(DM)로 결과 전송
       - DM 전송 성공 시에만 그룹의 원본 명령어 메시지 삭제 (메시지 증발 방지)
       - 관리자가 봇과 1:1 대화를 시작하지 않아 DM 실패 시, 그룹에 안내 전송
    """
    chat = update.effective_chat
    message = update.effective_message
    user = update.effective_user

    if not message:
        return None

    # 1. 1:1 개인 대화(DM)인 경우
    if not chat or chat.type == "private":
        return await safe_reply(message, text, **kwargs)

    # 2. 그룹 대화방인 경우
    group_title = (chat.title or "그룹").replace("[", "(").replace("]", ")")
    thread_info = ""
    thread_id = getattr(message, "message_thread_id", None)
    if getattr(message, "is_topic_message", False) and thread_id:
        thread_info = f" (토픽 ID: {thread_id})"

    dm_text = f"🏢 [{group_title}{thread_info}] 관리 안내\n\n{text}"

    dm_sent = False
    try:
        await context.bot.send_message(
            chat_id=user.id,
            text=dm_text,
            **kwargs
        )
        logger.info(f"Command feedback sent secretly to user {user.id} in 1:1 DM.")
        dm_sent = True
    except Exception as e:
        logger.warning(f"Could not send DM to user {user.id} (user hasn't /started bot in DM): {e}")

    # DM 전송에 성공한 경우에만 그룹의 원본 명령어 삭제 (메시지 증발 방지)
    if dm_sent:
        if delete_trigger:
            try:
                await message.delete()
            except Exception as e:
                logger.debug(f"Could not delete command trigger message: {e}")
        return None

    # 관리자가 봇과 1:1 대화를 아직 튼 적이 없어 DM이 차단된 경우 그룹으로 폴백 안내
    fallback_text = (
        f"{text}\n\n"
        f"*(💡 대화방 청결 팁: 봇과의 1:1 대화창에서 `/start`를 한 번 눌러두시면, "
        f"다음부터는 대화방을 어지럽히지 않고 관리자 개인 대화창으로 조용히 전송됩니다!)*"
    )
    return await safe_reply(message, fallback_text, **kwargs)


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

    # 2. 텔레그램 익명 관리자 모드(GroupAnonymousBot / Channel)인 경우: 관리자가 보낸 것이므로 승인
    if user.id in [1087968824, 136817688] or getattr(user, "username", "") == "GroupAnonymousBot":
        return True

    # 3. 텔레그램 자체 그룹 방장(creator) 또는 관리자(administrator)인 경우
    try:
        member = await context.bot.get_chat_member(chat_id=chat.id, user_id=user.id)
        return member.status in ["creator", "administrator"]
    except Exception as e:
        logger.warning(f"Could not verify chat member: {e}")
        return is_admin(user.id)


async def notify_admins_new_group(chat, inviter, context: ContextTypes.DEFAULT_TYPE):
    """새 그룹방 연결 시 총괄 관리자들에게 1:1 알림 전송 (HTML 파싱 사용으로 특수문자 오류 방지)"""
    admin_ids = db.get_admin_ids()
    if not admin_ids:
        return

    inviter_name = f"@{html.escape(inviter.username)}" if inviter and inviter.username else (f"ID: {inviter.id}" if inviter else "알 수 없음")
    chat_title = html.escape(chat.title or "이름 없음")
    is_forum = bool(getattr(chat, "is_forum", False))
    is_allowed = db.is_group_allowed(chat.id)
    status_str = "🟢 정상 활성화 (번역 작동 중)" if is_allowed else "🟡 승인 대기 중"

    text = (
        f"🔔 <b>신규 그룹 대화방 연결 감지</b>\n\n"
        f"• 그룹명: <b>{chat_title}</b>\n"
        f"• 그룹 ID: <code>{chat.id}</code>\n"
        f"• 포럼(주제) 여부: {'예' if is_forum else '아니오'}\n"
        f"• 연결/초대자: {inviter_name}\n"
        f"• 현재 상태: {status_str}\n\n"
        f"인가되지 않은 대화방인 경우 아래 버튼으로 즉시 차단/퇴장시킬 수 있습니다."
    )

    keyboard = [
        [
            InlineKeyboardButton("❌ 차단 및 퇴장", callback_data=f"ban_grp:{chat.id}"),
        ]
    ]
    if not is_allowed:
        keyboard[0].insert(0, InlineKeyboardButton("✅ 그룹 승인", callback_data=f"allow_grp:{chat.id}"))

    reply_markup = InlineKeyboardMarkup(keyboard)

    for a_id in admin_ids:
        try:
            await context.bot.send_message(
                chat_id=a_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Failed to notify admin {a_id}: {e}")


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
            db.register_group(chat.id, chat.title or "", is_forum)
            await notify_admins_new_group(chat, inviter, context)
        elif new_status in ["left", "kicked"]:
            db.delete_group(chat.id)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """S4, S5: 딥링크 입장 게이트 (보안 지침 준수: 토큰 검증 후 첫 관리자 부트스트랩)"""
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    if not message or not user or chat.type != "private":
        return

    if check_auth_abuse(user.id):
        return

    args = context.args
    input_payload = args[0].strip() if args else ""

    # S4: 올바른 초대 토큰(비밀 payload) 검증 (공격자의 단순 /start를 통한 관리자 권한 탈취 원천 차단)
    if not verify_payload(input_payload, INVITE_PAYLOAD):
        record_failed_auth(user.id)
        return

    # S5: 첫 관리자 부트스트랩 (1회성 - 올바른 토큰을 가진 최초 진입자만 관리자로 인정)
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
        topic_mode_str = ""
        if g.get("is_forum"):
            t_mode = g.get("topic_mode", "selective")
            topic_mode_str = f" | 토픽모드: {'선택주제만' if t_mode == 'selective' else '전체주제'}"
        lines.append(
            f"**{idx}. {g['title'] or '이름 없음'}**{forum_badge}\n"
            f"• ID: `{g['chat_id']}` | 상태: {status_icon}\n"
            f"• 언어모드: `{g['lang_mode']}` | 번역스위치: {'ON' if g['is_enabled'] else 'OFF'}{topic_mode_str}\n"
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


async def cmd_sync_glossary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """총괄 관리자 전용: 구글 스프레드시트 용어집 최신화 (1:1 DM 및 관리자 명령)"""
    user = update.effective_user
    message = update.effective_message
    if not message or not is_admin(user.id):
        return

    wait_msg = await safe_reply(message, "⏳ 구글 스프레드시트에서 최신 용어집을 동기화하는 중입니다...")
    success, msg = await asyncio.to_thread(glossary_manager.sync)
    if wait_msg:
        try:
            await wait_msg.delete()
        except Exception:
            pass
    await send_command_feedback(update, context, msg, parse_mode="Markdown")



async def cmd_allow_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """방 안에서 직접 승인하는 현장 명령어 (총괄 관리자 및 현장 방장/관리자 가능)"""
    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message

    if not message or chat.type == "private":
        return

    if not await is_group_admin(update, context):
        await send_command_feedback(update, context, "안내: 그룹 승인은 방장 또는 관리자만 가능합니다.")
        return

    is_forum = bool(getattr(chat, "is_forum", False))
    db.set_group_allowed(chat.id, True, chat.title or "", is_forum=is_forum)

    guide = "✅ **이 대화방의 번역 기능이 정상 활성화되었습니다.**"
    if is_forum:
        thread_id = message.message_thread_id
        if thread_id is None and getattr(message, "is_topic_message", False):
            thread_id = 1
        target_thread = thread_id if thread_id is not None else 1
        db.enable_topic(chat.id, target_thread)

        guide += (
            "\n\n🔔 **현재 주제(토픽)의 실시간 자동 번역이 즉시 켜졌습니다!**\n\n"
            "• 다른 주제에서도 번역을 켜시려면 해당 토픽에서 `토픽 on` (또는 `/topic on`)을 입력해 주세요.\n"
            "• 모든 주제에서 동시에 번역을 켜시려면 `토픽 all` (또는 `/topic all`)을 입력해 주세요."
        )

    await send_command_feedback(update, context, guide, parse_mode="Markdown")


async def cmd_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """주제별(토픽별) 번역 제어 (총괄 관리자 및 해당 방의 텔레그램 관리자 모두 사용 가능)"""
    chat = update.effective_chat
    message = update.effective_message

    if not message or chat.type == "private":
        return

    if not await is_group_admin(update, context):
        await send_command_feedback(update, context, "안내: 토픽 설정은 대화방 관리자만 변경할 수 있습니다.")
        return

    # 스레드(토픽) ID 추출 (토픽 메시지인 경우 message_thread_id, 없으면 1)
    thread_id = message.message_thread_id
    if thread_id is None and getattr(message, "is_topic_message", False):
        thread_id = 1

    args = context.args
    raw_action = args[0].lower().strip() if args else ""

    if raw_action in ["on", "켜기", "시작", "활성화"]:
        action = "on"
    elif raw_action in ["off", "끄기", "중지", "비활성화"]:
        action = "off"
    elif raw_action in ["all", "전체", "모두"]:
        action = "all"
    else:
        action = "help"

    if action == "help":
        active = db.is_topic_translation_enabled(chat.id, thread_id, is_forum=True)
        conf = db.get_group_config(chat.id)
        topic_mode = conf.get("topic_mode", "all")
        status_str = "🟢 켜짐 (번역 작동 중)" if active else "⚪ 꺼짐 (대기 중)"
        mode_desc = "모든 주제 번역 (전체 모드)" if topic_mode == "all" else "선택된 주제만 번역 (개별 모드)"

        text = (
            f"📌 **현재 주제 번역 상태: {status_str}**\n"
            f"• 그룹 토픽 설정: `{mode_desc}`\n\n"
            "**주제별 제어 명령어**:\n"
            "• `/topic on` (또는 `토픽 on` / `토픽 켜기`) : **현재 이 주제에서만** 번역 켜기\n"
            "• `/topic off` (또는 `토픽 off` / `토픽 끄기`) : 현재 이 주제에서 번역 끄기\n"
            "• `/topic all` (또는 `토픽 all` / `토픽 전체`) : 이 그룹의 모든 주제에서 번역 켜기"
        )
        await send_command_feedback(update, context, text, parse_mode="Markdown")
        return

    if action == "all":
        db.set_group_allowed(chat.id, True, chat.title or "", is_forum=True)
        db.enable_all_topics(chat.id)
        text = (
            "🌐 **[전체 주제 번역 활성화 완료]**\n\n"
            "이 대화방의 **모든 주제(토픽)에서 실시간 자동 번역이 활성화**되었습니다.\n\n"
            "• 모든 토픽에서 한국어, 영어, 베트남어가 실시간 번역됩니다.\n"
            "• 특정 주제만 번역을 끄고 싶으실 경우, 해당 주제에서 `/topic off`를 입력해 주세요."
        )
        await send_command_feedback(update, context, text, parse_mode="Markdown")
    elif action == "on":
        target_thread = thread_id if thread_id is not None else 1
        db.set_group_allowed(chat.id, True, chat.title or "", is_forum=True)
        db.enable_topic(chat.id, target_thread)
        text = (
            "🔔 **[현재 주제 실시간 번역 켜짐 (ON)]**\n\n"
            "✅ **현재 주제(토픽)의 실시간 자동 번역이 활성화되었습니다!**\n\n"
            "• 이 주제에서 올라오는 대화가 실시간으로 자동 번역됩니다.\n"
            "• 특정 주제만 번역을 끄려면 해당 주제에서 `/topic off`를 입력해 주세요."
        )
        await send_command_feedback(update, context, text, parse_mode="Markdown")
    elif action == "off":
        target_thread = thread_id if thread_id is not None else 1
        db.disable_topic(chat.id, target_thread)
        text = (
            "🔒 **[현재 주제 실시간 번역 꺼짐 (OFF)]**\n\n"
            "현재 주제(토픽)의 실시간 자동 번역이 꺼졌습니다.\n"
            "이제 이 주제의 대화는 번역되지 않습니다.\n\n"
            "💡 다시 번역을 켜려면 `/topic on`을 입력해 주세요."
        )
        await send_command_feedback(update, context, text, parse_mode="Markdown")


async def cmd_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """언어 모드 설정 (총괄 관리자 및 해당 방의 텔레그램 관리자 모두 변경 가능)"""
    chat = update.effective_chat
    message = update.effective_message

    if not message:
        return

    if chat.type != "private" and not await is_group_admin(update, context):
        await send_command_feedback(update, context, "안내: 설정 변경은 대화방 관리자만 가능합니다.")
        return

    args = context.args
    raw_mode = args[0].lower().strip() if args else ""
    if raw_mode in ["all", "전체", "모두", "3개국어", "3"]:
        new_mode = "all"
    elif raw_mode in ["ko-vi", "vi", "한베", "베트남", "베트남어"]:
        new_mode = "ko-vi"
    elif raw_mode in ["ko-en", "en", "한영", "영어"]:
        new_mode = "ko-en"
    else:
        conf = db.get_group_config(chat.id)
        current = conf.get("lang_mode", "all")
        current_names = {
            "all": "3개국어 통합 모드 (한국어 ↔ 영어 ↔ 베트남어)",
            "ko-vi": "한-베 전용 모드 (한국어 ↔ 베트남어)",
            "ko-en": "한-영 전용 모드 (한국어 ↔ 영어)"
        }
        await send_command_feedback(
            update,
            context,
            f"📊 **현재 언어 모드**: **`{current_names.get(current, current)}`**\n\n"
            "**언어 모드 변경 명령어**:\n"
            "• `/lang all` (또는 `언어 all` / `언어 전체`): 3개국어 통합 모드 (한국어 ➡️ 영+베 동시 번역)\n"
            "• `/lang ko-vi` (또는 `언어 한베` / `언어 vi`): 한-베 전용 모드 (한국어 ↔ 베트남어)\n"
            "• `/lang ko-en` (또는 `언어 한영` / `언어 en`): 한-영 전용 모드 (한국어 ↔ 영어)",
            parse_mode="Markdown"
        )
        return

    if chat.type != "private":
        db.set_group_allowed(chat.id, True, chat.title or "")
    db.update_group_config(chat.id, lang_mode=new_mode)

    if new_mode == "all":
        desc = (
            "🌐 **[언어 설정 변경: 3개국어 통합 모드]**\n\n"
            "실시간 번역 모드가 **'3개국어 통합 모드'** 로 설정되었습니다.\n\n"
            "• 🇰🇷 **한국어** 입력 ➡️ 🇺🇸 영어 + 🇻🇳 베트남어 동시 번역\n"
            "• 🇺🇸 **영어** 입력 ➡️ 🇰🇷 한국어로 번역\n"
            "• 🇻🇳 **베트남어** 입력 ➡️ 🇰🇷 한국어로 번역\n\n"
            "✨ 모든 참가자가 언어 장벽 없이 원활하게 소통할 수 있습니다."
        )
    elif new_mode == "ko-vi":
        desc = (
            "🇻🇳 **[언어 설정 변경: 한국어 ↔ 베트남어 전용 모드]**\n\n"
            "실시간 번역 모드가 **'한-베 전용 모드'** 로 설정되었습니다.\n\n"
            "• 🇰🇷 **한국어** 입력 ➡️ 🇻🇳 베트남어로 번역\n"
            "• 🇻🇳 **베트남어** 입력 ➡️ 🇰🇷 한국어로 번역\n"
            "(영어는 번역되지 않고 원문 그대로 유지됩니다.)\n\n"
            "✨ 한국어와 베트남어 집중 소통에 최적화되었습니다."
        )
    elif new_mode == "ko-en":
        desc = (
            "🇺🇸 **[언어 설정 변경: 한국어 ↔ 영어 전용 모드]**\n\n"
            "실시간 번역 모드가 **'한-영 전용 모드'** 로 설정되었습니다.\n\n"
            "• 🇰🇷 **한국어** 입력 ➡️ 🇺🇸 영어로 번역\n"
            "• 🇺🇸 **영어** 입력 ➡️ 🇰🇷 한국어로 번역\n"
            "(베트남어는 번역되지 않고 원문 그대로 유지됩니다.)\n\n"
            "✨ 한국어와 영어 집중 소통에 최적화되었습니다."
        )
    else:
        desc = f"✅ 언어 모드가 `{new_mode}`로 변경되었습니다."

    await send_command_feedback(update, context, desc, parse_mode="Markdown")


async def cmd_translate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """번역 켜기/끄기 (총괄 관리자 및 해당 방의 텔레그램 관리자 모두 제어 가능)"""
    chat = update.effective_chat
    message = update.effective_message

    if not message:
        return

    if chat.type != "private" and not await is_group_admin(update, context):
        await send_command_feedback(update, context, "안내: 설정 변경은 대화방 관리자만 가능합니다.")
        return

    args = context.args
    raw_action = args[0].lower().strip() if args else ""
    if raw_action in ["on", "켜기", "시작", "활성화"]:
        enabled = True
    elif raw_action in ["off", "끄기", "중지", "비활성화"]:
        enabled = False
    else:
        conf = db.get_group_config(chat.id)
        status_str = "ON (켜짐)" if conf.get("is_enabled", True) else "OFF (꺼짐)"
        await send_command_feedback(update, context, f"📊 현재 번역 기능 상태: **{status_str}** (`/translate on/off` 또는 `번역 on/off` / `번역 켜기/끄기`)")
        return

    if enabled and chat.type != "private":
        db.set_group_allowed(chat.id, True, chat.title or "")
    db.update_group_config(chat.id, is_enabled=enabled)
    await send_command_feedback(update, context, f"✅ 번역 기능이 **{'켜짐(ON)' if enabled else '꺼짐(OFF)'}** 처리되었습니다.")


async def cmd_myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message
    if not message or not user:
        return
    if chat.type != "private" and not db.is_group_allowed(chat.id):
        return
    await send_command_feedback(update, context, f"본인의 식별자(ID)입니다:\n`{user.id}`", parse_mode="Markdown")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message

    if not message or not user:
        return

    is_group = (chat.type != "private")
    if is_group and not db.is_group_allowed(chat.id):
        return

    if not is_group and not is_approved_member(user.id):
        return

    conf = db.get_group_config(chat.id)
    is_forum = bool(getattr(chat, "is_forum", False))
    group_auth = conf.get("is_allowed", False) if is_group else True
    enabled = conf.get("is_enabled", True)
    mode = conf.get("lang_mode", "all")

    topic_info = ""
    if is_forum:
        thread_id = message.message_thread_id
        if thread_id is None and getattr(message, "is_topic_message", False):
            thread_id = 1
        target_thread = thread_id if thread_id is not None else 1
        active = db.is_topic_translation_enabled(chat.id, target_thread, is_forum=True)
        topic_mode = conf.get("topic_mode", "all")
        topic_info = (
            f"• 대화방 구조: 포럼 (주제별 대화방)\n"
            f"• 그룹 토픽 모드: {'모든 주제 번역 (전체 모드)' if topic_mode == 'all' else '선택된 주제만 번역 (개별 모드)'}\n"
            f"• 현재 주제(ID: {target_thread}): {'🟢 켜짐(ON)' if active else '⚪ 꺼짐(대기)'}\n"
        )

    status_text = (
        "📊 **현재 상태**\n\n"
        f"• 사용자 권한: {'총괄 관리자' if is_admin(user.id) else '일반 사용자'}\n"
        f"• 대화방 유형: {'그룹 대화방' if is_group else '개인 1:1 대화'}\n"
        f"• 대화방 승인: {'✅ 승인됨' if group_auth else '🔒 미승인'}\n"
        f"{topic_info}"
        f"• 번역 기능: {'✅ 켜짐(ON)' if enabled else '❌ 꺼짐(OFF)'}\n"
        f"• 언어 모드: `{mode}`\n"
        f"• 용어집 연동: {glossary_manager.get_status_summary()}\n"
        f"• 엔진: `{translation_service.get_engine_name()}`\n"
    )
    await send_command_feedback(update, context, status_text, parse_mode="Markdown")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message

    if not message or not user:
        return

    if chat.type != "private" and not db.is_group_allowed(chat.id):
        return

    if chat.type == "private" and not is_approved_member(user.id):
        return

    admin_extra = ""
    if chat.type == "private" and is_admin(user.id):
        admin_extra = (
            "\n👑 **총괄 관리자 전용 (1:1 DM)**:\n"
            "• `/sync_glossary` (또는 `용어집 갱신`): 구글 시트 용어집 즉시 동기화\n"
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
        "📌 **주요 명령어 (영문 / 한글 모두 지원)**:\n"
        "• `/status` (또는 `상태`) : 현재 설정 및 권한 상태 확인\n"
        "• `/topic on | off | all` (또는 `토픽 on | off | all` / `토픽 켜기 | 끄기`): 포럼 주제별 번역 제어 (방장/관리자)\n"
        "• `/lang all | ko-vi | ko-en` (또는 `언어 전체 | 한베 | 한영`): 언어 모드 설정 (방장/관리자)\n"
        "• `/translate on | off` (또는 `번역 on | off`): 방 전체 번역 켜기/끄기 (방장/관리자)\n"
        "• `/myid` : 본인 식별 번호 확인\n"
        f"{admin_extra}"
    )
    await send_command_feedback(update, context, text, parse_mode="Markdown")


async def handle_custom_or_korean_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """한글 명령어 및 슬래시 없는 단축 명령어 처리 (/토픽 on, 토픽 on, /번역 켜기 등)"""
    message = update.effective_message
    if not message or not message.text:
        return False

    raw = message.text.strip()
    parts = raw.split()
    if not parts:
        return False

    first_token = parts[0].lower()
    has_slash = first_token.startswith("/")
    cmd_name = first_token[1:] if has_slash else first_token
    cmd_args = parts[1:]

    # 1. 띄어쓰기 없이 붙여 쓴 형태 (/topicon, 토픽on, /topicoff, 토픽off, /topicall, 토픽all 등) 처리
    joined_topic_map = {
        "topicon": "on", "topic_on": "on", "토픽on": "on", "토픽켜기": "on", "topic켜기": "on",
        "topicoff": "off", "topic_off": "off", "토픽off": "off", "토픽끄기": "off", "topic끄기": "off",
        "topicall": "all", "topic_all": "all", "토픽all": "all", "토픽전체": "all", "topic전체": "all", "토픽모두": "all",
    }
    joined_translate_map = {
        "translateon": "on", "translate_on": "on", "번역on": "on", "번역켜기": "on",
        "translateoff": "off", "translate_off": "off", "번역off": "off", "번역끄기": "off",
    }
    joined_lang_map = {
        "langall": "all", "lang_all": "all", "언어all": "all", "언어전체": "all", "언어3개국어": "all",
        "langkovi": "ko-vi", "lang_kovi": "ko-vi", "langko-vi": "ko-vi", "langvi": "ko-vi", "언어vi": "ko-vi", "언어한베": "ko-vi", "언어베트남": "ko-vi",
        "langkoen": "ko-en", "lang_koen": "ko-en", "langko-en": "ko-en", "langen": "ko-en", "언어en": "ko-en", "언어한영": "ko-en", "언어영어": "ko-en",
    }

    if cmd_name in joined_topic_map:
        context.args = [joined_topic_map[cmd_name]]
        await cmd_topic(update, context)
        return True
    elif cmd_name in joined_translate_map:
        context.args = [joined_translate_map[cmd_name]]
        await cmd_translate(update, context)
        return True
    elif cmd_name in joined_lang_map:
        context.args = [joined_lang_map[cmd_name]]
        await cmd_lang(update, context)
        return True

    # 2. 일반 분리형 명령어 검증
    # 슬래시가 있거나(/토픽, /번역 등), 유효한 명령어 키워드와 인자 조합일 때만 실행
    if cmd_name in ["topic", "토픽"]:
        if has_slash or not cmd_args or cmd_args[0].lower() in ["on", "off", "all", "켜기", "끄기", "전체", "모두", "시작", "중지"]:
            context.args = cmd_args
            await cmd_topic(update, context)
            return True
    elif cmd_name in ["translate", "번역"]:
        if has_slash or not cmd_args or cmd_args[0].lower() in ["on", "off", "켜기", "끄기", "시작", "중지", "활성화", "비활성화"]:
            context.args = cmd_args
            await cmd_translate(update, context)
            return True
    elif cmd_name in ["lang", "언어"]:
        if has_slash or not cmd_args or cmd_args[0].lower() in ["all", "ko-vi", "ko-en", "전체", "모두", "3개국어", "한베", "베트남", "베트남어", "한영", "영어", "vi", "en"]:
            context.args = cmd_args
            await cmd_lang(update, context)
            return True
    elif cmd_name in ["status", "상태"]:
        if has_slash or len(parts) == 1:
            context.args = cmd_args
            await cmd_status(update, context)
            return True
    elif cmd_name in ["help", "도움말"]:
        if has_slash or len(parts) == 1:
            context.args = cmd_args
            await cmd_help(update, context)
            return True
    elif cmd_name in ["start", "시작"]:
        if has_slash or len(parts) == 1:
            context.args = cmd_args
            await cmd_start(update, context)
            return True
    elif cmd_name in ["sync_glossary", "syncglossary", "용어집", "용어집갱신", "용어집동기화"]:
        if is_admin(update.effective_user.id):
            await cmd_sync_glossary(update, context)
            return True


    # 그 외 슬래시(/)로 시작하는 미인식 명령어는 일반 번역을 하지 않고 무시
    if has_slash:
        return True

    return False


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 1. effective_message 확인 (신규 메시지 및 수정된 메시지 모두 허용)
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    if not message or not user:
        return
    if user.is_bot:
        return

    raw_text = message.text or message.caption or ""
    current_text = raw_text.strip()
    if not current_text:
        return

    has_photo = bool(message.photo)

    # 2. 텍스트 변경 여부 확인 (메시지 수정 vs 단순 리액션/반응 구분)
    previous_text = get_cached_message_text(chat.id, message.message_id)
    is_edit = (previous_text is not None) or (update.edited_message is not None)

    if previous_text is not None:
        if previous_text == current_text:
            # 텍스트 내용에 변화가 없음 -> 단순 이모지 리액션 또는 중복 이벤트
            logger.info(f"Message {message.message_id} in chat {chat.id} text unchanged. Skipping.")
            return
        logger.info(f"Message {message.message_id} in chat {chat.id} was EDITED. Updating translation.")
    elif update.edited_message is not None:
        logger.info(f"Message {message.message_id} in chat {chat.id} received as edited_message without cache.")

    # 커스텀 및 한글 단축 명령어 가로채기
    if await handle_custom_or_korean_command(update, context):
        record_message_cache(chat.id, message.message_id, current_text)
        return

    # 3. 봇의 번역 답장에 대한 단순 인용/반응 필터링
    if message.reply_to_message and message.reply_to_message.from_user:
        if message.reply_to_message.from_user.id == context.bot.id:
            if is_trivial_reaction(current_text):
                return

    # S10: 레이트 리밋 검사
    if not check_rate_limit(user.id):
        return

    # S11: 그룹 대화방 처리
    thread_id = message.message_thread_id
    is_forum_chat = False
    if chat.type != "private":
        # 아직 DB에 등록되지 않은 신규 그룹인 경우 등록 및 알림
        if not db.is_group_registered(chat.id):
            is_forum = bool(getattr(chat, "is_forum", False))
            db.register_group(chat.id, chat.title or "", is_forum)
            await notify_admins_new_group(chat, user, context)

        # 미승인 그룹인 경우 완전 무반응
        if not db.is_group_allowed(chat.id):
            logger.info(f"Group {chat.id} is blocked/unapproved. Skipping.")
            return

        conf = db.get_group_config(chat.id)
        is_forum_chat = (
            bool(getattr(message, "is_topic_message", False))
            or (thread_id is not None and thread_id != 0)
            or bool(conf.get("is_forum", False))
            or bool(getattr(chat, "is_forum", False))
        )

        if is_forum_chat:
            target_thread = thread_id if thread_id is not None else 1
            if not db.is_topic_translation_enabled(chat.id, target_thread, is_forum=True):
                logger.info(f"Topic {target_thread} in {chat.id} is disabled. Skipping.")
                return

        mode = conf.get("lang_mode", "all")
    else:
        if not is_approved_member(user.id):
            return
        mode = "all"

    # 4. 동일 대화방/토픽 내 30초 이내 동일 사용자 중복 번역 방지
    current_target_thread = thread_id if (chat.type != "private" and is_forum_chat) else None
    if not is_edit and is_duplicate_content(chat.id, current_target_thread, current_text, user.id):
        logger.info(f"Duplicate content from user {user.id} in chat {chat.id}. Skipping duplicate translation.")
        return

    targets, text_to_translate = determine_translation_plan(
        current_text, mode=mode, has_photo=has_photo
    )
    if not targets or not text_to_translate:
        logger.info(f"No translation needed for message in chat_id={chat.id} (mode={mode}). Skipping.")
        return

    logger.info(f"Translating in chat_id={chat.id} to {[t[0] for t in targets]} (has_photo={has_photo})")

    # 동기 HTTP 번역 요청을 비동기 스레드 풀에서 병렬(asyncio.gather) 실행하여 이벤트 루프 블로킹 방지 및 지연시간 50% 단축
    async def _do_translate(target_code: str, flag: str):
        try:
            translated = await asyncio.to_thread(
                translation_service.translate,
                text_to_translate,
                target_lang=target_code
            )
            if translated:
                return f"{flag} {translated}"
        except Exception as e:
            logger.error(f"Translation error to {target_code}: {e}")
        return None

    tasks = [_do_translate(target_code, flag) for target_code, flag in targets]
    gathered_results = await asyncio.gather(*tasks)
    results = [r for r in gathered_results if r]

    if not results:
        logger.warning(f"Translation produced empty result in chat_id={chat.id}")
        return

    reply_content = "\n".join(results)

    # 5. 전송 처리: 메시지 수정인 경우 기존 봇 번역 메시지 내용 수정 시도, 실패 시 신규 답장 전송
    reply_msg_id = None
    if is_edit:
        prev_reply_id = get_bot_reply_id(chat.id, message.message_id)
        if prev_reply_id:
            try:
                await context.bot.edit_message_text(
                    chat_id=chat.id,
                    message_id=prev_reply_id,
                    text=reply_content,
                )
                reply_msg_id = prev_reply_id
                logger.info(f"Successfully edited existing translation {prev_reply_id} for message {message.message_id}")
            except Exception as e:
                err_str = str(e).lower()
                if "message is not modified" in err_str:
                    logger.info(f"Translation output unchanged for message {message.message_id}. No edit needed.")
                    reply_msg_id = prev_reply_id
                else:
                    logger.warning(f"Failed to edit existing translation {prev_reply_id}: {e}. Sending new reply.")

    if not reply_msg_id:
        sent_msg = await safe_reply(
            message,
            reply_content,
            reply_to_message_id=message.message_id,
        )
        if sent_msg:
            reply_msg_id = sent_msg.message_id

    # 번역 성공 후 메시지 텍스트 및 봇 답장 ID 캐시에 등록
    record_message_cache(chat.id, message.message_id, current_text, reply_msg_id)
    record_translated_content(chat.id, current_target_thread, current_text, user.id)
    logger.info(f"Translation completed in chat_id={chat.id} (is_edit={is_edit})")


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
    logger.error(f"Handled exception: {err_type} - {err}", exc_info=err)


class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Service active.")

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()

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


async def periodic_glossary_sync():
    """백그라운드에서 1시간마다 최신 용어집 자동 갱신"""
    while True:
        try:
            await asyncio.sleep(3600)
            if GLOSSARY_SHEET_URL:
                logger.info("Running scheduled glossary sync...")
                await asyncio.to_thread(glossary_manager.sync)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning(f"Periodic glossary sync error: {e}")


async def post_init(application):
    """봇 기동 직후 초기 용어집 동기화 및 주기적 갱신 태스크 등록"""
    if GLOSSARY_SHEET_URL:
        logger.info("Initializing glossary sync on bot startup...")
        # 초기 1회 비동기 동기화
        asyncio.create_task(asyncio.to_thread(glossary_manager.sync))
        # 1시간 주기적 동기화 백그라운드 태스크 실행
        asyncio.create_task(periodic_glossary_sync())


def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN missing.")
        return

    port = int(os.getenv("PORT", "8080"))
    start_health_check_server(port)

    logger.info("Starting Telegram Bot application...")
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()

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
    app.add_handler(CommandHandler("sync_glossary", cmd_sync_glossary))
    app.add_handler(CommandHandler("allow_group", cmd_allow_group))
    app.add_handler(CommandHandler("topic", cmd_topic))
    app.add_handler(CommandHandler("lang", cmd_lang))
    app.add_handler(CommandHandler("translate", cmd_translate))
    app.add_handler(ChatMemberHandler(track_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(CallbackQueryHandler(handle_callback_query))

    message_filter = (filters.TEXT | filters.CAPTION) & ~filters.COMMAND
    app.add_handler(MessageHandler(message_filter, handle_message))
    app.add_handler(MessageHandler(filters.UpdateType.EDITED_MESSAGE & message_filter, handle_message))

    app.add_error_handler(global_error_handler)

    app.run_polling()


if __name__ == "__main__":
    main()

