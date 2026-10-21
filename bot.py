import os
import re
import time
import logging
import threading
import asyncio
import html
from collections import OrderedDict
from typing import Optional, Tuple, Dict, Any, Set
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

try:
    from telegram.ext import MessageReactionHandler
    HAS_REACTION_HANDLER = True
except ImportError:
    HAS_REACTION_HANDLER = False

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
    SUPPORTED_TARGET_LANGUAGES,
    ORDERED_TARGET_LANGS,
    parse_active_languages,
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

# 4. 활성화 시 대화형 언어 선택 대기 메시지 캐시: chat_id -> message_id (선택 완료 시 자동 삭제용)
PENDING_LANG_PROMPTS: Dict[int, int] = {}
# 5. 다중 선택 체크박스 임시 상태 캐시: chat_id -> Set[str] (예: {'en', 'vi'})
PENDING_LANG_SELECTIONS: Dict[int, Set[str]] = {}


def build_lang_keyboard(chat_id: int, current_set: Optional[Set[str]] = None) -> InlineKeyboardMarkup:
    """대화방 언어 다중 선택 체크박스 인라인 키보드 (2x2 언어 체크박스 + 전체선택 + 적용완료)"""
    if current_set is None:
        if chat_id in PENDING_LANG_SELECTIONS:
            current_set = PENDING_LANG_SELECTIONS[chat_id]
        else:
            conf = db.get_group_config(chat_id)
            current_set = parse_active_languages(conf.get("lang_mode", "all"))
            PENDING_LANG_SELECTIONS[chat_id] = set(current_set)

    def _btn(code: str, label: str):
        checked = code in current_set
        icon = "☑️" if checked else "⬜"
        return InlineKeyboardButton(f"{icon} {label}", callback_data=f"tgl_lang:{chat_id}:{code}")

    all_checked = (len(current_set) == len(ORDERED_TARGET_LANGS))
    all_btn_text = "🌐 5개국어 전체 해제" if all_checked else "🌐 5개국어 전체 선택 (한·영·베·중·스)"

    buttons = [
        [
            _btn("en", "🇺🇸 영어"),
            _btn("vi", "🇻🇳 베트남어"),
        ],
        [
            _btn("zh", "🇨🇳 중국어"),
            _btn("es", "🇪🇸 스페인어"),
        ],
        [
            InlineKeyboardButton(all_btn_text, callback_data=f"tgl_all:{chat_id}"),
        ],
        [
            InlineKeyboardButton("✅ 설정 완료 (적용하기)", callback_data=f"save_lang:{chat_id}"),
        ]
    ]
    return InlineKeyboardMarkup(buttons)


def build_lang_card_text(current_set: Set[str]) -> str:
    """선택된 언어 상태에 따른 안내 카드 본문 텍스트 생성"""
    if len(current_set) == len(ORDERED_TARGET_LANGS):
        summary = "🌐 **5개국어 전체 번역** (한국어 ↔ 영어, 베트남어, 중국어, 스페인어)"
    elif not current_set:
        summary = "⚠️ *선택된 언어 없음 (최소 1개 이상 체크해 주세요)*"
    else:
        names = [
            f"{SUPPORTED_TARGET_LANGUAGES[k]['flag']} {SUPPORTED_TARGET_LANGUAGES[k]['name']}"
            for k in ORDERED_TARGET_LANGS
            if k in current_set
        ]
        summary = f"**{', '.join(names)}** (총 {len(current_set)}개 언어)"

    return (
        "🌐 **대화방 번역 언어 다중 선택 (체크박스)**\n\n"
        f"• 현재 선택: {summary}\n\n"
        "원하시는 번역 언어를 **중복 체크(다중 선택)** 하실 수 있습니다.\n"
        "버튼을 눌러 언어를 켜고(☑️) 끈(⬜) 뒤, 하단의 **[✅ 설정 완료 (적용하기)]** 를 눌러주세요:\n\n"
        "• 🇺🇸 **영어** : 한국어 ↔ 영어 실시간 번역\n"
        "• 🇻🇳 **베트남어** : 한국어 ↔ 베트남어 실시간 번역\n"
        "• 🇨🇳 **중국어** : 한국어 ↔ 중국어 실시간 번역\n"
        "• 🇪🇸 **스페인어** : 한국어 ↔ 스페인어 실시간 번역\n"
        "• 🌐 **5개국어 전체** : 한국어 ↔ 4개국 외국어 동시 번역\n\n"
        "*(명령어로도 즉시 설정 가능: `/lang all`, `/lang en vi`)*\n\n"
        "⚠️ *대화방 관리자(방장/어드민)만 설정할 수 있습니다.*"
    )


def get_lang_mode_display_name(mode: str) -> str:
    """언어 모드 코드에 대응하는 사용자 친화적 명칭 반환"""
    active = parse_active_languages(mode)
    if len(active) == len(ORDERED_TARGET_LANGS):
        return "🌐 5개국어 전체 (한·영·베·중·스)"
    if active == {"en"}:
        return "🇺🇸 한-영 (English)"
    if active == {"vi"}:
        return "🇻🇳 한-베 (Tiếng Việt)"
    if active == {"zh"}:
        return "🇨🇳 한-중 (中文)"
    if active == {"es"}:
        return "🇪🇸 한-스 (Español)"
    if not active:
        return "⚠️ 선택된 언어 없음"

    names = [
        f"{SUPPORTED_TARGET_LANGUAGES[k]['flag']} {SUPPORTED_TARGET_LANGUAGES[k]['name']}"
        for k in ORDERED_TARGET_LANGS
        if k in active
    ]
    return " + ".join(names) + " (다중 선택)"


def get_cached_message_text(chat_id: int, message_id: int) -> Optional[str]:
    """메시지 ID에 대해 캐시된 이전 텍스트 반환 (L1 메모리 -> L2 DB 영구 저장소 조회)"""
    key = (chat_id, message_id)
    if key in PROCESSED_MESSAGE_TEXTS:
        return PROCESSED_MESSAGE_TEXTS[key]

    # L2 DB 확인 (서버 재기동/신규 패치 후에도 유지)
    record = db.get_message_translation(chat_id, message_id)
    if record and record.get("original_text") is not None:
        text = record["original_text"]
        PROCESSED_MESSAGE_TEXTS[key] = text
        if len(PROCESSED_MESSAGE_TEXTS) > MAX_TEXT_CACHE:
            PROCESSED_MESSAGE_TEXTS.popitem(last=False)
        return text
    return None


def get_bot_reply_id(chat_id: int, message_id: int) -> Optional[int]:
    """특정 사용자 메시지에 대응하는 봇 번역 메시지 ID 반환 (L1 메모리 -> L2 DB 조회)"""
    key = (chat_id, message_id)
    if key in BOT_TRANSLATION_REPLIES:
        return BOT_TRANSLATION_REPLIES[key]

    # L2 DB 확인
    record = db.get_message_translation(chat_id, message_id)
    if record and record.get("bot_reply_id") is not None:
        reply_id = record["bot_reply_id"]
        BOT_TRANSLATION_REPLIES[key] = reply_id
        if len(BOT_TRANSLATION_REPLIES) > MAX_REPLY_CACHE:
            BOT_TRANSLATION_REPLIES.popitem(last=False)
        return reply_id
    return None


def record_message_cache(
    chat_id: int,
    message_id: int,
    text: str,
    reply_id: Optional[int] = None,
    user_id: int = 0,
):
    """메시지 텍스트 및 봇 답장 ID를 L1 메모리 캐시 및 L2 SQLite DB에 영구 기록"""
    key = (chat_id, message_id)
    PROCESSED_MESSAGE_TEXTS[key] = text
    if len(PROCESSED_MESSAGE_TEXTS) > MAX_TEXT_CACHE:
        PROCESSED_MESSAGE_TEXTS.popitem(last=False)

    if reply_id is not None:
        BOT_TRANSLATION_REPLIES[key] = reply_id
        if len(BOT_TRANSLATION_REPLIES) > MAX_REPLY_CACHE:
            BOT_TRANSLATION_REPLIES.popitem(last=False)

    # L2 DB 영구 저장 (봇 재부팅/패치 후에도 메시지 수정 및 리액션 무시 기능 보존)
    db.record_message_translation(chat_id, message_id, user_id, text, reply_id)


def is_already_processed(chat_id: int, message_id: int) -> bool:
    """하위 호환용: 메시지 ID 캐시/DB 존재 여부"""
    return get_cached_message_text(chat_id, message_id) is not None


def mark_as_processed(
    chat_id: int, message_id: int, text: str = "", reply_id: Optional[int] = None, user_id: int = 0
):
    """하위 호환용: 메시지 캐시 및 DB 등록"""
    record_message_cache(chat_id, message_id, text, reply_id, user_id)


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
    3. 마크다운/HTML 엔티티 파싱 오류 발생 시 자동 복구 및 서식 제거 재전송 (메시지 증발 방지)
    4. 원본 메시지가 삭제된 경우 일반 메시지(send_message)로 자동 폴백
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

        # 1. 텔레그램 마크다운/HTML 파싱 에러인 경우 -> 서식 제거 후 즉시 재전송 (메시지 증발 방지)
        if "parse" in err_str or "entity" in err_str or "can't find end" in err_str:
            logger.warning(f"Telegram parse_mode failed ({e}). Falling back to plain text.")
            kwargs.pop("parse_mode", None)
            try:
                clean_text = re.sub(r'<[^>]+>', '', text)
                clean_text = clean_text.replace("**", "").replace("__", "").replace("`", "")
                return await message.reply_text(clean_text, **kwargs)
            except Exception as e_plain:
                logger.error(f"Plain reply also failed: {e_plain}")

        # 2. 원본 메시지 부재로 인한 reply 실패인 경우 -> send_message로 재시도
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
    delete_trigger: bool = False,
    **kwargs
):
    """
    명령어를 입력한 바로 그 대화방(개인 DM 또는 공용 그룹/포럼 토픽)으로 직접 피드백 전송
    """
    message = update.effective_message
    if not message:
        return None

    # 명령어가 입력된 바로 그 대화방 및 토픽 스레드로 직접 답장 전송
    return await safe_reply(message, text, **kwargs)


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
            is_already_registered = db.is_group_registered(chat.id)
            db.register_group(chat.id, chat.title or "", is_forum)
            await notify_admins_new_group(chat, inviter, context)

            # 요구사항 1 & 4: 신규 방 초대 시에만 즉시 언어 선택 질문 카드 전송 (기존 방은 설정 보존 및 중복 전송 방지)
            if not is_already_registered and db.is_group_allowed(chat.id):
                try:
                    init_set = set(ORDERED_TARGET_LANGS)
                    PENDING_LANG_SELECTIONS[chat.id] = set(init_set)
                    guide_text = build_lang_card_text(init_set)
                    reply_markup = build_lang_keyboard(chat.id, init_set)
                    prompt_msg = await context.bot.send_message(
                        chat_id=chat.id,
                        text=guide_text,
                        reply_markup=reply_markup,
                        parse_mode="Markdown"
                    )
                    if prompt_msg:
                        PENDING_LANG_PROMPTS[chat.id] = prompt_msg.message_id
                except Exception as e:
                    logger.warning(f"Failed to send onboarding lang prompt to chat {chat.id}: {e}")
        elif new_status in ["left", "kicked"]:
            db.delete_group(chat.id)
            PENDING_LANG_PROMPTS.pop(chat.id, None)


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
    """인라인 버튼 클릭 처리 (대화방 언어 선택, 멤버 승인 및 그룹 원격 제어)"""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    data = query.data or ""
    if ":" not in data:
        return

    action = data.split(":", 1)[0]

    async def _check_group_perm(target_chat_id: int) -> bool:
        if is_admin(user.id):
            return True
        if user.id in [1087968824, 136817688] or getattr(user, "username", "") == "GroupAnonymousBot":
            return True
        try:
            member = await context.bot.get_chat_member(target_chat_id, user.id)
            return member.status in ["creator", "administrator"]
        except Exception:
            return False

    # 1. 다중 선택 체크박스 토글 (개별 언어 on/off)
    if action == "tgl_lang":
        parts = data.split(":")
        target_chat_id = int(parts[1])
        lang_code = parts[2]

        if not await _check_group_perm(target_chat_id):
            await query.answer("대화방 관리자(방장/어드민)만 언어 설정을 변경할 수 있습니다.", show_alert=True)
            return

        if target_chat_id not in PENDING_LANG_SELECTIONS:
            conf = db.get_group_config(target_chat_id)
            PENDING_LANG_SELECTIONS[target_chat_id] = set(parse_active_languages(conf.get("lang_mode", "all")))

        current_set = PENDING_LANG_SELECTIONS[target_chat_id]
        if lang_code in current_set:
            current_set.remove(lang_code)
        else:
            current_set.add(lang_code)

        new_text = build_lang_card_text(current_set)
        new_markup = build_lang_keyboard(target_chat_id, current_set)

        try:
            await query.edit_message_text(new_text, reply_markup=new_markup, parse_mode="Markdown")
        except Exception as e:
            if "message is not modified" not in str(e).lower():
                logger.warning(f"Failed to edit message in tgl_lang: {e}")
        return

    # 2. 5개국어 전체 선택 / 전체 해제 토글
    elif action == "tgl_all":
        parts = data.split(":")
        target_chat_id = int(parts[1])

        if not await _check_group_perm(target_chat_id):
            await query.answer("대화방 관리자(방장/어드민)만 언어 설정을 변경할 수 있습니다.", show_alert=True)
            return

        if target_chat_id not in PENDING_LANG_SELECTIONS:
            conf = db.get_group_config(target_chat_id)
            PENDING_LANG_SELECTIONS[target_chat_id] = set(parse_active_languages(conf.get("lang_mode", "all")))

        current_set = PENDING_LANG_SELECTIONS[target_chat_id]
        if len(current_set) == len(ORDERED_TARGET_LANGS):
            current_set.clear()
        else:
            current_set = set(ORDERED_TARGET_LANGS)
        PENDING_LANG_SELECTIONS[target_chat_id] = current_set

        new_text = build_lang_card_text(current_set)
        new_markup = build_lang_keyboard(target_chat_id, current_set)

        try:
            await query.edit_message_text(new_text, reply_markup=new_markup, parse_mode="Markdown")
        except Exception as e:
            if "message is not modified" not in str(e).lower():
                logger.warning(f"Failed to edit message in tgl_all: {e}")
        return

    # 3. 설정 완료 (적용하기)
    elif action == "save_lang":
        parts = data.split(":")
        target_chat_id = int(parts[1])

        if not await _check_group_perm(target_chat_id):
            await query.answer("대화방 관리자(방장/어드민)만 언어 설정을 저장할 수 있습니다.", show_alert=True)
            return

        if target_chat_id not in PENDING_LANG_SELECTIONS:
            conf = db.get_group_config(target_chat_id)
            PENDING_LANG_SELECTIONS[target_chat_id] = set(parse_active_languages(conf.get("lang_mode", "all")))

        current_set = PENDING_LANG_SELECTIONS[target_chat_id]
        if not current_set:
            await query.answer("⚠️ 최소 1개 이상의 번역 언어를 체크해 주세요!", show_alert=True)
            return

        if len(current_set) == len(ORDERED_TARGET_LANGS):
            saved_mode = "all"
        else:
            saved_mode = ",".join([k for k in ORDERED_TARGET_LANGS if k in current_set])

        db.set_group_allowed(target_chat_id, True)
        db.update_group_config(target_chat_id, lang_mode=saved_mode)
        PENDING_LANG_PROMPTS.pop(target_chat_id, None)
        PENDING_LANG_SELECTIONS.pop(target_chat_id, None)

        mode_name = get_lang_mode_display_name(saved_mode)

        # 1. 안내 메시지 카드 자동 삭제 (대화방 정리)
        try:
            await query.message.delete()
        except Exception:
            pass

        # 2. 간결한 완료 메시지 전송 후 7초 뒤 자동 정리
        try:
            sent_notice = await context.bot.send_message(
                chat_id=target_chat_id,
                text=(
                    f"✅ 대화방 번역 모드가 **{mode_name}**(으)로 설정되었습니다.\n\n"
                    f"• 이제 대화방에 메시지를 올리시면 실시간 자동 번역됩니다.\n\n"
                    f"💡 **사용 팁**:\n"
                    f"• 언제든 언어 변경: `/lang`\n"
                    f"• 대화방 기능 및 명령어 확인: `/help`"
                ),
                parse_mode="Markdown"
            )
            if sent_notice:
                async def _cleanup(msg):
                    await asyncio.sleep(7)
                    try:
                        await msg.delete()
                    except Exception:
                        pass
                asyncio.create_task(_cleanup(sent_notice))
        except Exception as e:
            logger.warning(f"Failed to send save confirmation notice: {e}")
        return

    # 4. 하위 호환용 단일 선택 모드 (과거 메시지 버튼 클릭 대응)
    elif action == "room_lang":
        parts = data.split(":")
        target_chat_id = int(parts[1])
        chosen_mode = parts[2]

        if not await _check_group_perm(target_chat_id):
            await query.answer("대화방 관리자(방장/어드민)만 언어 모드를 설정할 수 있습니다.", show_alert=True)
            return

        mode_name = get_lang_mode_display_name(chosen_mode)

        db.set_group_allowed(target_chat_id, True)
        db.update_group_config(target_chat_id, lang_mode=chosen_mode)
        PENDING_LANG_PROMPTS.pop(target_chat_id, None)
        PENDING_LANG_SELECTIONS.pop(target_chat_id, None)

        try:
            await query.message.delete()
        except Exception:
            pass

        try:
            sent_notice = await context.bot.send_message(
                chat_id=target_chat_id,
                text=(
                    f"✅ 대화방 번역 모드가 **{mode_name}**으로 설정되었습니다. 이제 자유롭게 대화하시면 번역됩니다.\n\n"
                    f"💡 **사용 팁**:\n"
                    f"• 언제든 언어 변경: `/lang`\n"
                    f"• 대화방 기능 및 명령어 확인: `/help`"
                ),
                parse_mode="Markdown"
            )
            if sent_notice:
                async def _cleanup(msg):
                    await asyncio.sleep(7)
                    try:
                        await msg.delete()
                    except Exception:
                        pass
                asyncio.create_task(_cleanup(sent_notice))
        except Exception:
            pass
        return

    # 이하 총괄 관리자(Super Admin) 전용 명령들
    if not is_admin(user.id):
        return

    # 2. 멤버 승인/거절
    if action == "approve":
        target_id = int(data.split(":", 1)[1])
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
        target_id = int(data.split(":", 1)[1])
        db.set_user_role(target_id, "rejected")
        try:
            await query.edit_message_text(f"❌ 사용자(ID: {target_id}) 입장을 거절했습니다.")
        except Exception:
            pass

    # 3. 그룹 원격 승인 / 퇴장
    elif action == "allow_grp":
        target_id = int(data.split(":", 1)[1])
        db.set_group_allowed(target_id, True)
        try:
            await query.edit_message_text(f"✅ 그룹 대화방(ID: `{target_id}`)이 정상 승인되었습니다.", parse_mode="Markdown")
            init_set = parse_active_languages(db.get_group_config(target_id).get("lang_mode", "all"))
            PENDING_LANG_SELECTIONS[target_id] = set(init_set)
            guide_text = build_lang_card_text(init_set)
            reply_markup = build_lang_keyboard(target_id, init_set)
            prompt_msg = await context.bot.send_message(
                chat_id=target_id,
                text=guide_text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
            if prompt_msg:
                PENDING_LANG_PROMPTS[target_id] = prompt_msg.message_id
        except Exception:
            pass

    elif action == "ban_grp":
        target_id = int(data.split(":", 1)[1])
        db.set_group_allowed(target_id, False)
        try:
            await query.edit_message_text(f"❌ 그룹 대화방(ID: `{target_id}`) 입장을 거절하고 퇴장했습니다.", parse_mode="Markdown")
            await context.bot.leave_chat(chat_id=target_id)
            db.delete_group(target_id)
        except Exception:
            pass

    # 4. 총괄 관리자 1:1 DM 그룹 원격 제어 패널 (sel_grp, adm_lang, adm_toggle, adm_back)
    elif action == "sel_grp":
        target_chat_id = int(data.split(":")[1])
        conf = db.get_group_config(target_chat_id)
        groups = db.get_all_groups()
        target_grp = next((g for g in groups if g["chat_id"] == target_chat_id), None)
        title = target_grp["title"] if target_grp else f"대화방 {target_chat_id}"
        safe_title = html.escape(title)

        mode_str = get_lang_mode_display_name(conf.get("lang_mode", "all"))
        switch_str = "🟢 켜짐(ON)" if conf.get("is_enabled", True) else "⚪ 꺼짐(OFF)"

        card_text = (
            f"⚙️ <b>대화방 원격 설정: {safe_title}</b>\n\n"
            f"• 식별 ID: <code>{target_chat_id}</code>\n"
            f"• 현재 언어 모드: <b>{mode_str}</b>\n"
            f"• 번역 스위치: <b>{switch_str}</b>\n\n"
            "변경하실 언어 모드나 스위치 버튼을 눌러주세요:"
        )
        card_kb = [
            [
                InlineKeyboardButton("🇺🇸 한-영", callback_data=f"adm_lang:{target_chat_id}:ko-en"),
                InlineKeyboardButton("🇻🇳 한-베", callback_data=f"adm_lang:{target_chat_id}:ko-vi"),
            ],
            [
                InlineKeyboardButton("🇨🇳 한-중", callback_data=f"adm_lang:{target_chat_id}:ko-zh"),
                InlineKeyboardButton("🇪🇸 한-스", callback_data=f"adm_lang:{target_chat_id}:ko-es"),
            ],
            [
                InlineKeyboardButton("🌐 3개국어 전체", callback_data=f"adm_lang:{target_chat_id}:all"),
            ],
            [
                InlineKeyboardButton("⚡ 번역 ON/OFF", callback_data=f"adm_toggle:{target_chat_id}"),
                InlineKeyboardButton("🔙 목록으로", callback_data="adm_back:0"),
            ]
        ]
        await query.edit_message_text(card_text, reply_markup=InlineKeyboardMarkup(card_kb), parse_mode="HTML")

    elif action == "adm_lang":
        parts = data.split(":")
        target_chat_id = int(parts[1])
        new_mode = parts[2]
        db.update_group_config(target_chat_id, lang_mode=new_mode)
        mode_str = get_lang_mode_display_name(new_mode)
        await query.answer(f"대화방 언어가 '{mode_str}'(으)로 변경되었습니다!", show_alert=True)

        conf = db.get_group_config(target_chat_id)
        groups = db.get_all_groups()
        target_grp = next((g for g in groups if g["chat_id"] == target_chat_id), None)
        title = target_grp["title"] if target_grp else f"대화방 {target_chat_id}"
        safe_title = html.escape(title)
        switch_str = "🟢 켜짐(ON)" if conf.get("is_enabled", True) else "⚪ 꺼짐(OFF)"

        card_text = (
            f"⚙️ <b>대화방 원격 설정: {safe_title}</b>\n\n"
            f"• 식별 ID: <code>{target_chat_id}</code>\n"
            f"• 현재 언어 모드: <b>{mode_str}</b> (변경 완료 ✅)\n"
            f"• 번역 스위치: <b>{switch_str}</b>\n\n"
            "변경하실 언어 모드나 스위치 버튼을 눌러주세요:"
        )
        card_kb = [
            [
                InlineKeyboardButton("🇺🇸 한-영", callback_data=f"adm_lang:{target_chat_id}:ko-en"),
                InlineKeyboardButton("🇻🇳 한-베", callback_data=f"adm_lang:{target_chat_id}:ko-vi"),
            ],
            [
                InlineKeyboardButton("🇨🇳 한-중", callback_data=f"adm_lang:{target_chat_id}:ko-zh"),
                InlineKeyboardButton("🇪🇸 한-스", callback_data=f"adm_lang:{target_chat_id}:ko-es"),
            ],
            [
                InlineKeyboardButton("🌐 3개국어 전체", callback_data=f"adm_lang:{target_chat_id}:all"),
            ],
            [
                InlineKeyboardButton("⚡ 번역 ON/OFF", callback_data=f"adm_toggle:{target_chat_id}"),
                InlineKeyboardButton("🔙 목록으로", callback_data="adm_back:0"),
            ]
        ]
        await query.edit_message_text(card_text, reply_markup=InlineKeyboardMarkup(card_kb), parse_mode="HTML")

    elif action == "adm_toggle":
        target_chat_id = int(data.split(":")[1])
        conf = db.get_group_config(target_chat_id)
        new_state = not conf.get("is_enabled", True)
        db.update_group_config(target_chat_id, is_enabled=new_state)
        await query.answer(f"번역 스위치가 {'ON' if new_state else 'OFF'} 되었습니다.", show_alert=True)

        groups = db.get_all_groups()
        target_grp = next((g for g in groups if g["chat_id"] == target_chat_id), None)
        title = target_grp["title"] if target_grp else f"대화방 {target_chat_id}"
        safe_title = html.escape(title)
        mode_str = {"ko-en": "🇺🇸 한-영", "ko-vi": "🇻🇳 한-베", "all": "🌐 3개국어"}.get(conf.get("lang_mode"), conf.get("lang_mode", "all"))
        switch_str = "🟢 켜짐(ON)" if new_state else "⚪ 꺼짐(OFF)"

        card_text = (
            f"⚙️ <b>대화방 원격 설정: {safe_title}</b>\n\n"
            f"• 식별 ID: <code>{target_chat_id}</code>\n"
            f"• 현재 언어 모드: <b>{mode_str}</b>\n"
            f"• 번역 스위치: <b>{switch_str}</b> (변경 완료 ✅)\n\n"
            "변경하실 언어 모드나 스위치 버튼을 눌러주세요:"
        )
        card_kb = [
            [
                InlineKeyboardButton("🇺🇸 한-영", callback_data=f"adm_lang:{target_chat_id}:ko-en"),
                InlineKeyboardButton("🇻🇳 한-베", callback_data=f"adm_lang:{target_chat_id}:ko-vi"),
                InlineKeyboardButton("🌐 3개국어", callback_data=f"adm_lang:{target_chat_id}:all"),
            ],
            [
                InlineKeyboardButton("⚡ 번역 ON/OFF", callback_data=f"adm_toggle:{target_chat_id}"),
                InlineKeyboardButton("🔙 목록으로", callback_data="adm_back:0"),
            ]
        ]
        await query.edit_message_text(card_text, reply_markup=InlineKeyboardMarkup(card_kb), parse_mode="HTML")

    elif action == "adm_back":
        text, reply_markup = build_groups_menu()
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="HTML")


def build_groups_menu():
    """총괄 관리자용 대화방 목록 및 인라인 버튼 메뉴 생성 (HTML 사용으로 특수문자 완벽 호환)"""
    groups = db.get_all_groups()
    if not groups:
        return "현재 봇이 연결된 그룹 대화방이 없습니다.", None

    lines = ["📋 <b>봇 연결 그룹 대화방 목록 및 원격 제어</b>\n"]
    keyboard = []
    mode_names = {"ko-en": "🇺🇸한영", "ko-vi": "🇻🇳한베", "ko-zh": "🇨🇳한중", "ko-es": "🇪🇸한스", "all": "🌐3개국어"}

    for idx, g in enumerate(groups, 1):
        status_icon = "🟢 승인됨" if g["is_allowed"] else "🟡 대기중"
        forum_badge = " (포럼)" if g["is_forum"] else ""
        m_name = mode_names.get(g["lang_mode"], g["lang_mode"])
        sw_name = "ON" if g["is_enabled"] else "OFF"
        safe_title = html.escape(g['title'] or '이름 없음')
        lines.append(
            f"<b>{idx}. {safe_title}</b>{forum_badge}\n"
            f"• ID: <code>{g['chat_id']}</code> | 상태: {status_icon}\n"
            f"• 설정: 언어 <b><code>{m_name}</code></b> | 번역: <b><code>{sw_name}</code></b>\n"
        )
        title_btn = (g['title'] or f"방 {idx}")[:14]
        keyboard.append([
            InlineKeyboardButton(f"⚙️ {idx}. {title_btn} 설정", callback_data=f"sel_grp:{g['chat_id']}")
        ])

    lines.append(
        "💡 <b>원격 관리</b>: 위 버튼을 누르면 해당 방의 언어(<code>한영/한베/한중/한스/3개국어</code>)와 번역 스위치를 즉시 변경할 수 있습니다.\n"
        "• 명령어로 변경: <code>/set_lang [대화방ID] [all | ko-en | ko-vi | ko-zh | ko-es]</code>"
    )
    return "\n".join(lines), InlineKeyboardMarkup(keyboard)


async def cmd_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """총괄 관리자 전용: 봇이 연결된 모든 대화방 목록 및 상태 조회 (1:1 DM 전용)"""
    user = update.effective_user
    chat = update.effective_chat
    message = update.effective_message

    if not message:
        return

    if chat.type != "private":
        await safe_reply(message, "🔒 이 명령어는 봇과의 1:1 개인 대화창(DM)에서만 사용 가능합니다.")
        return

    if not is_admin(user.id):
        await safe_reply(
            message,
            f"⚠️ <b>총괄 관리자 권한이 필요합니다.</b>\n\n"
            f"• 현재 사용자 텔레그램 ID: <code>{user.id}</code>\n"
            f"• 이 명령어는 등록된 총괄 관리자만 사용할 수 있습니다.\n"
            f"• 본인을 총괄 관리자로 등록하시려면 Render 환경변수 <code>EMERGENCY_ADMIN_ID</code>에 위 ID(<code>{user.id}</code>)를 입력해 주세요.",
            parse_mode="HTML"
        )
        return

    text, reply_markup = build_groups_menu()
    await safe_reply(message, text, reply_markup=reply_markup, parse_mode="HTML")


async def cmd_set_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """총괄 관리자 전용: 특정 대화방의 번역 언어 모드 원격 변경"""
    user = update.effective_user
    message = update.effective_message
    if not message:
        return

    if not is_admin(user.id):
        await safe_reply(
            message,
            f"⚠️ 총괄 관리자 권한이 필요합니다. (본인 ID: `{user.id}`)\n"
            f"Render 환경변수 `EMERGENCY_ADMIN_ID`에 본인 ID를 등록해 주세요.",
            parse_mode="Markdown"
        )
        return

    args = context.args or []
    if len(args) < 2:
        await safe_reply(
            message,
            "사용법: `/set_lang [대화방ID] [all | ko-en | ko-vi | ko-zh | ko-es]`\n"
            "예시: `/set_lang -100123456789 ko-en`\n\n"
            "• `all` : 3개국어 (한국어 ↔ 영어 ↔ 베트남어)\n"
            "• `ko-en` : 한-영 전용 (한국어 ↔ 영어)\n"
            "• `ko-vi` : 한-베 전용 (한국어 ↔ 베트남어)\n"
            "• `ko-zh` : 한-중 전용 (한국어 ↔ 중국어)\n"
            "• `ko-es` : 한-스 전용 (한국어 ↔ 스페인어)",
            parse_mode="Markdown"
        )
        return

    try:
        target_chat_id = int(args[0].strip())
        raw_mode = args[1].strip().lower()
        mode_map = {
            "all": "all", "전체": "all", "3개국어": "all",
            "ko-en": "ko-en", "koen": "ko-en", "한영": "ko-en", "영어": "ko-en",
            "ko-vi": "ko-vi", "kovi": "ko-vi", "한베": "ko-vi", "베트남": "ko-vi", "베트남어": "ko-vi",
            "ko-zh": "ko-zh", "kozh": "ko-zh", "한중": "ko-zh", "중국": "ko-zh", "중국어": "ko-zh",
            "ko-es": "ko-es", "koes": "ko-es", "한스": "ko-es", "스페인": "ko-es", "스페인어": "ko-es"
        }
        if raw_mode not in mode_map:
            await safe_reply(message, "지원 언어 모드: `all`, `ko-en`, `ko-vi`, `ko-zh`, `ko-es`")
            return

        target_mode = mode_map[raw_mode]
        db.update_group_config(target_chat_id, lang_mode=target_mode)
        mode_display = get_lang_mode_display_name(target_mode)
        await safe_reply(
            message,
            f"✅ 대화방(`{target_chat_id}`)의 언어 모드가 **{mode_display} (`{target_mode}`)**으로 원격 변경되었습니다.",
            parse_mode="Markdown"
        )
    except Exception as e:
        await safe_reply(message, f"오류 발생: {e}")


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

PAUSE_NOTICE_TEXT = (
    "⚠️ **[시스템 점검 안내 / Maintenance Notice]**\n\n"
    "더 원활하고 안정적인 번역 서비스를 위해 시스템 점검을 진행 중입니다.\n"
    "점검 기간 동안 번역 기능이 잠시 중단되오니 양해 부탁드립니다.\n"
    "작업 완료 후 즉시 재안내 드리겠습니다.\n\n"
    "• Translation is temporarily paused for system maintenance.\n"
    "• Dịch thuật tạm thời bị tạm dừng để bảo trì hệ thống."
)

RESUME_NOTICE_TEXT = (
    "✅ **[시스템 정상화 안내 / Service Resumed]**\n\n"
    "번역 시스템 점검이 완료되었습니다.\n"
    "지금부터 모든 대화방에서 정상적으로 번역 기능을 이용하실 수 있습니다.\n"
    "기다려 주셔서 감사합니다.\n\n"
    "• System maintenance is complete. Translation service is now restored.\n"
    "• Quá trình bảo trì hệ thống đã hoàn tất. Dịch vụ dịch thuật đã được khôi phục."
)


async def broadcast_maintenance_notice(context: ContextTypes.DEFAULT_TYPE, text: str) -> Tuple[int, int]:
    """
    승인된 모든 그룹 대화방에 시스템 공지 발송 (포럼 방의 경우 메인/일반 토픽에만 1회 발송)
    반환값: (성공 건수, 실패 건수)
    """
    groups = db.get_allowed_groups()
    success_count = 0
    fail_count = 0

    for g in groups:
        chat_id = g["chat_id"]
        is_forum = bool(g.get("is_forum", False))

        try:
            if is_forum:
                # 포럼 방의 경우 메인/일반(General) 토픽(ID: 1)으로 전송하여 서브 토픽 도배 방지
                try:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=text,
                        message_thread_id=1,
                        parse_mode="Markdown"
                    )
                except Exception as forum_e:
                    logger.debug(f"Forum thread_id 1 failed for chat {chat_id}: {forum_e}, falling back to default thread.")
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=text,
                        parse_mode="Markdown"
                    )
            else:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode="Markdown"
                )
            success_count += 1
        except Exception as e:
            logger.warning(f"Failed to send maintenance notice to chat {chat_id}: {e}")
            fail_count += 1

        # 텔레그램 발송 제한(Rate limit) 준수
        await asyncio.sleep(0.05)

    return success_count, fail_count


async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """총괄 관리자 전용: 전체 번역 일괄 중단 (점검 모드)"""
    user = update.effective_user
    message = update.effective_message
    if not message:
        return

    if not is_admin(user.id):
        await safe_reply(
            message,
            f"⚠️ **총괄 관리자 권한이 필요합니다.** (본인 ID: `{user.id}`)\n"
            f"Render 환경변수 `EMERGENCY_ADMIN_ID`에 본인 ID를 등록해 주세요.",
            parse_mode="Markdown"
        )
        return

    args = context.args or []
    text_arg = " ".join(args).lower()
    is_silent = "silent" in text_arg or "조용" in text_arg

    db.set_maintenance_mode(True)
    logger.info(f"System maintenance mode ENABLED by admin {user.id} (silent={is_silent})")

    if not is_silent:
        wait_msg = await safe_reply(message, "⏳ 전체 대화방에 시스템 점검 공지를 발송하는 중입니다...")
        succ, fail = await broadcast_maintenance_notice(context, PAUSE_NOTICE_TEXT)
        if wait_msg:
            try:
                await wait_msg.delete()
            except Exception:
                pass
        await send_command_feedback(
            update,
            context,
            f"🚨 **전체 번역 일괄 중단(점검 모드) 가동 완료**\n\n"
            f"• 현재 상태: **🔴 점검 중 (번역 전면 중단)**\n"
            f"• 공지 발송 결과: 성공 {succ}개 방 / 실패 {fail}개 방\n\n"
            f"💡 점검이 끝난 후 `/resume` (또는 `점검완료`)를 입력하면 정상화 공지와 함께 번역이 재개됩니다.",
            parse_mode="Markdown"
        )
    else:
        await send_command_feedback(
            update,
            context,
            f"🚨 **전체 번역 일괄 중단(조용한 점검 모드) 가동 완료**\n\n"
            f"• 현재 상태: **🔴 점검 중 (번역 전면 중단)**\n"
            f"• 공지 발송: **생략됨 (silent)**\n\n"
            f"💡 점검이 끝난 후 `/resume` (또는 `점검완료`)를 입력하면 번역이 재개됩니다.",
            parse_mode="Markdown"
        )


async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """총괄 관리자 전용: 전체 번역 일괄 재개 (정상화)"""
    user = update.effective_user
    message = update.effective_message
    if not message:
        return

    if not is_admin(user.id):
        await safe_reply(
            message,
            f"⚠️ **총괄 관리자 권한이 필요합니다.** (본인 ID: `{user.id}`)\n"
            f"Render 환경변수 `EMERGENCY_ADMIN_ID`에 본인 ID를 등록해 주세요.",
            parse_mode="Markdown"
        )
        return

    args = context.args or []
    text_arg = " ".join(args).lower()
    is_silent = "silent" in text_arg or "조용" in text_arg

    db.set_maintenance_mode(False)
    logger.info(f"System maintenance mode DISABLED by admin {user.id} (silent={is_silent})")

    if not is_silent:
        wait_msg = await safe_reply(message, "⏳ 전체 대화방에 시스템 정상화 공지를 발송하는 중입니다...")
        succ, fail = await broadcast_maintenance_notice(context, RESUME_NOTICE_TEXT)
        if wait_msg:
            try:
                await wait_msg.delete()
            except Exception:
                pass
        await send_command_feedback(
            update,
            context,
            f"✅ **전체 번역 정상화(점검 종료) 완료**\n\n"
            f"• 현재 상태: **🟢 정상 운영 중 (번역 활성)**\n"
            f"• 공지 발송 결과: 성공 {succ}개 방 / 실패 {fail}개 방\n\n"
            f"이제 모든 연결된 대화방에서 정상 번역이 작동합니다.",
            parse_mode="Markdown"
        )
    else:
        await send_command_feedback(
            update,
            context,
            f"✅ **전체 번역 정상화(조용한 재개) 완료**\n\n"
            f"• 현재 상태: **🟢 정상 운영 중 (번역 활성)**\n"
            f"• 공지 발송: **생략됨 (silent)**\n\n"
            f"이제 모든 연결된 대화방에서 정상 번역이 작동합니다.",
            parse_mode="Markdown"
        )


async def cmd_sync_glossary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """총괄 관리자 전용: 구글 스프레드시트 용어집 최신화 (1:1 DM 및 관리자 명령)"""
    user = update.effective_user
    message = update.effective_message
    if not message:
        return

    if not is_admin(user.id):
        await safe_reply(
            message,
            f"⚠️ **총괄 관리자 권한이 필요합니다.** (본인 ID: `{user.id}`)\n"
            f"Render 환경변수 `EMERGENCY_ADMIN_ID`에 본인 ID를 등록해 주세요.",
            parse_mode="Markdown"
        )
        return

    wait_msg = await safe_reply(message, "⏳ 행정용어집(엑셀/시트) 데이터를 최신화하고 동기화하는 중입니다...")
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

    topic_guide = ""
    if is_forum:
        thread_id = message.message_thread_id
        if thread_id is None and getattr(message, "is_topic_message", False):
            thread_id = 1
        target_thread = thread_id if thread_id is not None else 1
        db.enable_topic(chat.id, target_thread)
        topic_guide = f"• **현재 주제(토픽 ID: {target_thread})** 번역이 즉시 켜졌습니다.\n\n"

    init_set = parse_active_languages(db.get_group_config(chat.id).get("lang_mode", "all"))
    PENDING_LANG_SELECTIONS[chat.id] = set(init_set)
    reply_markup = build_lang_keyboard(chat.id, init_set)
    guide = (
        "🎉 **이 대화방의 번역 기능이 활성화되었습니다!**\n\n"
        f"{topic_guide}"
        f"{build_lang_card_text(init_set)}"
    )

    prompt_msg = await send_command_feedback(update, context, guide, reply_markup=reply_markup, parse_mode="Markdown")
    if prompt_msg:
        PENDING_LANG_PROMPTS[chat.id] = prompt_msg.message_id


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

    args = context.args or []
    if not args:
        conf = db.get_group_config(chat.id)
        current = conf.get("lang_mode", "all")
        current_set = parse_active_languages(current)
        PENDING_LANG_SELECTIONS[chat.id] = set(current_set)

        guide_text = build_lang_card_text(current_set)
        reply_markup = build_lang_keyboard(chat.id, current_set)

        prompt_msg = await send_command_feedback(
            update,
            context,
            guide_text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        if prompt_msg:
            PENDING_LANG_PROMPTS[chat.id] = prompt_msg.message_id
        return

    # 직접 언어 인자를 입력한 경우 (예: /lang en vi, /lang 영어 중국어, /lang all)
    raw_input = " ".join(args).lower().strip()
    active = parse_active_languages(raw_input)
    if not active:
        await send_command_feedback(
            update,
            context,
            "⚠️ 유효한 언어가 지정되지 않았습니다.\n예: `/lang all`, `/lang en vi`, `/lang 영어 중국어`"
        )
        return

    if len(active) == len(ORDERED_TARGET_LANGS):
        new_mode = "all"
    else:
        new_mode = ",".join([k for k in ORDERED_TARGET_LANGS if k in active])

    if chat.type != "private":
        db.set_group_allowed(chat.id, True, chat.title or "")
    db.update_group_config(chat.id, lang_mode=new_mode)
    PENDING_LANG_SELECTIONS.pop(chat.id, None)

    # 대기 중인 언어 선택 안내 카드가 있다면 자동 삭제
    if chat.id in PENDING_LANG_PROMPTS:
        old_prompt_id = PENDING_LANG_PROMPTS.pop(chat.id)
        try:
            await context.bot.delete_message(chat_id=chat.id, message_id=old_prompt_id)
        except Exception:
            pass

    mode_name = get_lang_mode_display_name(new_mode)
    target_names = [
        f"{SUPPORTED_TARGET_LANGUAGES[k]['flag']} {SUPPORTED_TARGET_LANGUAGES[k]['name']}"
        for k in ORDERED_TARGET_LANGS
        if k in active
    ]

    desc = (
        f"✅ **[대화방 번역 언어 설정 완료]**\n\n"
        f"• 적용 모드: **{mode_name}**\n"
        f"• 활성 외국어: **{', '.join(target_names)}**\n\n"
        f"• 🇰🇷 **한국어** 입력 ➡️ {', '.join(target_names)} 동시 실시간 번역\n"
        f"• 외국어 입력 ➡️ 🇰🇷 **한국어**로 자동 번역\n\n"
        f"✨ 참가자들이 언어 장벽 없이 원활하게 소통할 수 있습니다."
    )

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
        await safe_reply(
            message,
            f"📊 **현재 상태**\n\n"
            f"• 계정 권한: 🟡 미승인 계정\n"
            f"• 본인 텔레그램 ID: `{user.id}`\n\n"
            f"💡 총괄 관리자 권한이 필요하신 경우 Render의 `EMERGENCY_ADMIN_ID`에 본인 ID(`{user.id}`)를 등록해 주세요.",
            parse_mode="Markdown"
        )
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

    maint_mode = db.is_maintenance_mode()
    maint_status = "🔴 점검 중 (번역 일괄 중단 상태)" if maint_mode else "🟢 정상 운영 중"

    status_text = (
        "📊 **현재 상태**\n\n"
        f"• 시스템 상태: **{maint_status}**\n"
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

    # 그룹 대화방인 경우 (미인가 방은 침묵 - S11)
    if chat.type != "private":
        if not db.is_group_allowed(chat.id):
            return

        # 요구사항 2: 대화방에서는 대화방 실무 필수 명령어만 깔끔하게 노출
        group_text = (
            "📖 **대화방 번역 봇 사용 안내 (5개국어 지원)**\n\n"
            "• 한국어 ↔ 영어, 베트남어, 중국어, 스페인어 실시간 양방향 자동 번역\n"
            "• 원하는 언어만 자유롭게 골라 번역하는 **다중 체크(중복 선택)** 지원\n"
            "• 단순 감탄사/단답형 리액션 자동 필터링\n\n"
            "📌 **대화방 주요 명령어 (방장/관리자 전용)**:\n"
            "• `/lang` (또는 `언어`) : **번역 언어 다중 선택 카드 열기** (원하는 언어 체크박스 선택 후 적용)\n"
            "• `/lang all` : 5개국어 전체 번역 일괄 적용\n"
            "• `/lang [언어들]` : 직접 언어 지정 (예: `/lang en vi`, `/lang 영어 중국어`)\n"
            "• `/translate on | off` (또는 `번역 켜기 | 끄기`) : 대화방 전체 번역 일시정지 / 재개\n"
            "• `/topic on | off | all` : (포럼 방인 경우) 현재 주제(토픽)별 번역 켜기/끄기\n"
            "• `/status` (또는 `상태`) : 현재 방의 언어 설정 및 작동 상태 확인\n"
            "• `/myid` : 본인 텔레그램 식별 번호 확인"
        )
        await send_command_feedback(update, context, group_text, parse_mode="Markdown")
        return

    # 이하 1:1 개인 대화(DM)
    if not is_approved_member(user.id):
        text = (
            f"👋 안녕하세요! 다국어 실시간 번역 봇입니다.\n\n"
            f"현재 계정은 관리자 미등록 상태입니다.\n"
            f"• 본인 텔레그램 ID: `{user.id}`\n\n"
            f"총괄 관리자 권한이 필요하신 경우 Render 환경변수의 `EMERGENCY_ADMIN_ID`에 위 ID(`{user.id}`)를 등록해 주세요."
        )
        await safe_reply(message, text, parse_mode="Markdown")
        return

    admin_extra = ""
    if is_admin(user.id):
        admin_extra = (
            "\n👑 **총괄 관리자 전용 (1:1 DM 전용 명령)**:\n"
            "• `/pause` (또는 `점검시작`) : 전체 번역 일괄 중단 + 모든 방에 점검 공지 발송\n"
            "• `/pause silent` (또는 `조용히정지`) : 공지 없이 조용히 번역 일괄 중단\n"
            "• `/resume` (또는 `점검완료`) : 전체 번역 일괄 정상화 + 모든 방에 완료 공지 발송\n"
            "• `/resume silent` (또는 `조용히재개`) : 공지 없이 조용히 번역 일괄 정상화\n"
            "• `/sync_glossary` (또는 `용어집 갱신`): 구글 시트 용어집 즉시 동기화\n"
            "• `/groups` : 연결된 대화방 목록 조회 및 원클릭 버튼 원격 설정\n"
            "• `/set_lang [ID] [모드]` : 대화방 언어 모드 원격 지정 (all, ko-en, ko-vi, ko-zh, ko-es)\n"
            "• `/approve_group [ID]` : 대화방 원격 승인\n"
            "• `/ban_group [ID]` : 대화방 원격 차단/퇴장\n"
            "• `/grant_admin [ID]` : 보조 관리자 권한 부여\n"
            "• `/revoke_admin [ID]` : 관리자 권한 회수\n"
        )

    text = (
        "📖 **개인 대화(DM) 사용 안내**\n\n"
        "• 한국어 ↔ 영어 ↔ 베트남어 ↔ 중국어 ↔ 스페인어 실시간 자동 감지 번역\n"
        "• 단답형 리액션/감탄사는 자동 필터링\n\n"
        "📌 **기본 명령어**:\n"
        "• `/status` : 현재 시스템 및 계정 권한 확인\n"
        "• `/myid` : 본인 식별 번호 확인\n"
        f"{admin_extra}"
    )
    await safe_reply(message, text, parse_mode="Markdown")


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
        "langkozh": "ko-zh", "lang_kozh": "ko-zh", "langko-zh": "ko-zh", "langzh": "ko-zh", "언어zh": "ko-zh", "언어한중": "ko-zh", "언어중국": "ko-zh", "언어중국어": "ko-zh",
        "langkoes": "ko-es", "lang_koes": "ko-es", "langko-es": "ko-es", "langes": "ko-es", "언어es": "ko-es", "언어한스": "ko-es", "언어스페인": "ko-es", "언어스페인어": "ko-es",
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
        if has_slash or not cmd_args or cmd_args[0].lower() in [
            "all", "ko-vi", "ko-en", "ko-zh", "ko-es", "전체", "모두", "3개국어",
            "한베", "베트남", "베트남어", "한영", "영어", "한중", "중국", "중국어",
            "한스", "스페인", "스페인어", "vi", "en", "zh", "es"
        ]:
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
        await cmd_sync_glossary(update, context)
        return True
    elif cmd_name in ["pause", "점검시작", "일괄정지", "점검", "정지"]:
        context.args = cmd_args
        await cmd_pause(update, context)
        return True
    elif cmd_name in ["resume", "점검완료", "점검종료", "일괄재개", "재개"]:
        context.args = cmd_args
        await cmd_resume(update, context)
        return True
    elif cmd_name in ["groups", "대화방", "그룹목록", "방목록", "대화방목록"]:
        context.args = cmd_args
        await cmd_groups(update, context)
        return True
    elif cmd_name in ["set_lang", "setlang", "방언어", "방언어설정", "언어설정"]:
        context.args = cmd_args
        await cmd_set_lang(update, context)
        return True
    elif cmd_name in ["allow_group", "allowgroup", "방승인", "그룹승인", "활성화"]:
        await cmd_allow_group(update, context)
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

    if update.edited_message is not None:
        # 텔레그램에서 edited_message 이벤트(수정/반응/상태변경)로 들어온 경우
        if previous_text is not None:
            if previous_text == current_text:
                # 텍스트 내용에 변화가 없음 -> 단순 이모지 리액션 또는 텔레그램 내부 상태 갱신
                logger.info(
                    f"Message {message.message_id} in chat {chat.id} text unchanged "
                    "(emoji reaction / status update). Skipping translation."
                )
                return
            # 텍스트가 실제로 변경됨 -> 메시지 내용 수정(Edit)
            is_edit = True
            logger.info(
                f"Message {message.message_id} in chat {chat.id} was EDITED (text changed). "
                "Updating existing translation."
            )
        else:
            # DB 및 메모리에 이전 번역 이력이 없는 경우 (패치 이전 과거 메시지 또는 미번역 메시지)
            # 기존 메시지에 리액션을 눌렀을 때 재번역 답장이 발생하는 문제를 방지하기 위해 스킵
            logger.info(
                f"Message {message.message_id} in chat {chat.id} received as edited_message "
                "without previous translation record. Skipping to avoid duplicate translation on reaction."
            )
            return
    else:
        # 일반 신규 메시지 수신
        if previous_text is not None:
            if previous_text == current_text:
                # 네트워크 재전송 등에 의한 완전 동일 메시지 중복 처리 방지
                logger.info(f"Message {message.message_id} in chat {chat.id} already processed. Skipping duplicate.")
                return
            is_edit = True
        else:
            is_edit = False

    # 커스텀 및 한글 단축 명령어 가로채기
    if await handle_custom_or_korean_command(update, context):
        record_message_cache(chat.id, message.message_id, current_text, user_id=user.id)
        return

    # 2-1. 시스템 점검(일괄 정지) 모드 확인
    # 관리자 명령어를 제외한 모든 일반 대화의 번역을 전면 차단합니다.
    if db.is_maintenance_mode():
        logger.info(f"System maintenance mode is ACTIVE. Skipping translation in chat {chat.id}.")
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
    record_message_cache(chat.id, message.message_id, current_text, reply_msg_id, user_id=user.id)
    record_translated_content(chat.id, current_target_thread, current_text, user.id)
    logger.info(f"Translation completed in chat_id={chat.id} (is_edit={is_edit})")


async def ignore_reaction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """메시지 이모지 반응(Reaction) 표시는 번역을 수행하지 않고 안전하게 무시"""
    return


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
            if glossary_manager.is_enabled():
                logger.info("Running scheduled glossary sync...")
                await asyncio.to_thread(glossary_manager.sync)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning(f"Periodic glossary sync error: {e}")


async def periodic_db_cleanup():
    """백그라운드에서 24시간마다 오래된 번역 이력 레코드 자동 정리 (DB 용량 최적화)"""
    while True:
        try:
            await asyncio.sleep(86400)
            logger.info("Running scheduled DB cleanup for old message translations...")
            await asyncio.to_thread(db.cleanup_old_message_translations, 14)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning(f"Periodic DB cleanup error: {e}")


async def post_init(application):
    """봇 기동 직후 초기 용어집 동기화, DB 정리 및 주기적 태스크 등록"""
    # 1. 기동 시 14일 경과 오래된 번역 캐시 정리 및 24시간 주기 정리 등록
    asyncio.create_task(asyncio.to_thread(db.cleanup_old_message_translations, 14))
    asyncio.create_task(periodic_db_cleanup())

    # 2. 용어집 동기화
    if glossary_manager.is_enabled():
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
    app.add_handler(CommandHandler("pause", cmd_pause))
    app.add_handler(CommandHandler("resume", cmd_resume))
    app.add_handler(CommandHandler("set_lang", cmd_set_lang))
    app.add_handler(CommandHandler("sync_glossary", cmd_sync_glossary))
    app.add_handler(CommandHandler("allow_group", cmd_allow_group))
    app.add_handler(CommandHandler("topic", cmd_topic))
    app.add_handler(CommandHandler("lang", cmd_lang))
    app.add_handler(CommandHandler("translate", cmd_translate))
    app.add_handler(ChatMemberHandler(track_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(CallbackQueryHandler(handle_callback_query))

    # 반응(Reaction) 표시 전용 무시 핸들러 등록 (텔레그램 Bot API 7.0+)
    if HAS_REACTION_HANDLER:
        app.add_handler(MessageReactionHandler(ignore_reaction))

    message_filter = (filters.TEXT | filters.CAPTION) & ~filters.COMMAND
    app.add_handler(MessageHandler(message_filter, handle_message))
    app.add_handler(MessageHandler(filters.UpdateType.EDITED_MESSAGE & message_filter, handle_message))

    app.add_error_handler(global_error_handler)

    app.run_polling()


if __name__ == "__main__":
    main()

