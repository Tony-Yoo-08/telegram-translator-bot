import os
import sqlite3
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / "auth_store.db"
EMERGENCY_ADMIN_ID = os.getenv("EMERGENCY_ADMIN_ID", "").strip()
AUTO_APPROVE_GROUPS = os.getenv("AUTO_APPROVE_GROUPS", "true").lower() in ["true", "1", "yes"]


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """데이터베이스 및 테이블 초기화 (S4 원자적 저장소 준수)"""
    with get_connection() as conn:
        cursor = conn.cursor()
        # 사용자 테이블: user_id, role ('admin'|'member'|'pending'|'rejected'), username, created_at
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                role TEXT NOT NULL,
                username TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # 그룹 테이블: chat_id, title, is_allowed, lang_mode, is_enabled, is_forum, topic_mode
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS groups (
                chat_id INTEGER PRIMARY KEY,
                title TEXT,
                is_allowed INTEGER DEFAULT 1,
                lang_mode TEXT DEFAULT 'all',
                is_enabled INTEGER DEFAULT 1,
                is_forum INTEGER DEFAULT 0,
                topic_mode TEXT DEFAULT 'selective',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # 토픽별 설정 테이블: chat_id, thread_id, is_enabled
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS group_topics (
                chat_id INTEGER,
                thread_id INTEGER,
                is_enabled INTEGER DEFAULT 1,
                PRIMARY KEY (chat_id, thread_id)
            )
        """)
        # 시스템 플래그 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_flags (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        # S5: .env 비상 관리자 자동 부트스트랩 (서버 재기동 시 데이터 보존)
        if EMERGENCY_ADMIN_ID:
            try:
                e_id = int(EMERGENCY_ADMIN_ID)
                cursor.execute("""
                    INSERT INTO users (user_id, role, username)
                    VALUES (?, 'admin', 'MasterAdmin')
                    ON CONFLICT(user_id) DO UPDATE SET role = 'admin'
                """, (e_id,))
                cursor.execute("""
                    INSERT INTO system_flags (key, value)
                    VALUES ('admin_initialized', 'true')
                    ON CONFLICT(key) DO UPDATE SET value = 'true'
                """)
            except ValueError:
                pass
        conn.commit()


# --- 사용자 및 관리자 관리 ---

def is_bootstrap_done() -> bool:
    """S5: 첫 관리자 부트스트랩 완료 여부 확인"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM system_flags WHERE key = 'admin_initialized'")
        row = cursor.fetchone()
        return bool(row and row["value"] == "true")


def complete_bootstrap():
    """S5: 첫 관리자 등록 후 영구 플래그 설정"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO system_flags (key, value)
            VALUES ('admin_initialized', 'true')
            ON CONFLICT(key) DO UPDATE SET value = 'true'
        """)
        conn.commit()


def get_user_role(user_id: int) -> Optional[str]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT role FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return row["role"] if row else None


def set_user_role(user_id: int, role: str, username: str = ""):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (user_id, role, username)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET role = excluded.role, username = excluded.username
        """, (user_id, role, username))
        conn.commit()


def get_admin_ids() -> List[int]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE role = 'admin'")
        ids = [row["user_id"] for row in cursor.fetchall()]
        if EMERGENCY_ADMIN_ID:
            try:
                e_id = int(EMERGENCY_ADMIN_ID)
                if e_id not in ids:
                    ids.append(e_id)
            except ValueError:
                pass
        return ids


def count_admins() -> int:
    """S5: 관리자 수 (lockout 방지용)"""
    return len(get_admin_ids())


# --- 그룹 및 원격 중앙 관리 ---

def get_all_groups() -> List[Dict[str, Any]]:
    """중앙 관리자용: 봇이 연결된 모든 그룹 대화방 목록 조회"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT chat_id, title, is_allowed, lang_mode, is_enabled, is_forum, topic_mode, created_at
            FROM groups ORDER BY created_at DESC
        """)
        return [dict(row) for row in cursor.fetchall()]


def is_group_registered(chat_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM groups WHERE chat_id = ?", (chat_id,))
        return cursor.fetchone() is not None


def is_group_allowed(chat_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT is_allowed FROM groups WHERE chat_id = ?", (chat_id,))
        row = cursor.fetchone()
        if row is not None:
            return bool(row["is_allowed"] == 1)
        return AUTO_APPROVE_GROUPS


def register_group(chat_id: int, title: str = "", is_forum: bool = False):
    """신규 그룹 등록 (포럼인 경우 기본적으로 모든 토픽이 침묵인 selective 모드로 등록)"""
    default_allowed = 1 if AUTO_APPROVE_GROUPS else 0
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO groups (chat_id, title, is_allowed, is_forum, topic_mode)
            VALUES (?, ?, ?, ?, 'selective')
            ON CONFLICT(chat_id) DO UPDATE SET title = excluded.title, is_forum = excluded.is_forum
        """, (chat_id, title, default_allowed, 1 if is_forum else 0))
        conn.commit()


# 하위 호환성 유지
register_group_pending = register_group


def set_group_allowed(chat_id: int, allowed: bool, title: str = "", is_forum: Optional[bool] = None):
    with get_connection() as conn:
        cursor = conn.cursor()
        if is_forum is not None:
            cursor.execute("""
                INSERT INTO groups (chat_id, is_allowed, title, is_forum, topic_mode)
                VALUES (?, ?, ?, ?, 'selective')
                ON CONFLICT(chat_id) DO UPDATE SET 
                    is_allowed = excluded.is_allowed, 
                    title = excluded.title,
                    is_forum = excluded.is_forum
            """, (chat_id, 1 if allowed else 0, title, 1 if is_forum else 0))
        else:
            cursor.execute("""
                UPDATE groups SET is_allowed = ? WHERE chat_id = ?
            """, (1 if allowed else 0, chat_id))
        conn.commit()


def delete_group(chat_id: int):
    """그룹 차단/퇴장 시 데이터 정리"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM groups WHERE chat_id = ?", (chat_id,))
        cursor.execute("DELETE FROM group_topics WHERE chat_id = ?", (chat_id,))
        conn.commit()


def get_group_config(chat_id: int) -> Dict[str, Any]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT is_allowed, lang_mode, is_enabled, is_forum, topic_mode 
            FROM groups WHERE chat_id = ?
        """, (chat_id,))
        row = cursor.fetchone()
        if row:
            return {
                "is_allowed": bool(row["is_allowed"]),
                "lang_mode": row["lang_mode"] or "all",
                "is_enabled": bool(row["is_enabled"]),
                "is_forum": bool(row["is_forum"]),
                "topic_mode": row["topic_mode"] or "selective"
            }
        return {
            "is_allowed": AUTO_APPROVE_GROUPS,
            "lang_mode": "all",
            "is_enabled": True,
            "is_forum": False,
            "topic_mode": "selective"
        }


def update_group_config(chat_id: int, lang_mode: Optional[str] = None, is_enabled: Optional[bool] = None, topic_mode: Optional[str] = None):
    with get_connection() as conn:
        cursor = conn.cursor()
        if lang_mode is not None:
            cursor.execute("UPDATE groups SET lang_mode = ? WHERE chat_id = ?", (lang_mode, chat_id))
        if is_enabled is not None:
            cursor.execute("UPDATE groups SET is_enabled = ? WHERE chat_id = ?", (1 if is_enabled else 0, chat_id))
        if topic_mode is not None:
            cursor.execute("UPDATE groups SET topic_mode = ? WHERE chat_id = ?", (topic_mode, chat_id))
        conn.commit()


# --- 토픽(주제)별 제어 함수 ---

def is_topic_translation_enabled(chat_id: int, thread_id: Optional[int], is_forum: bool) -> bool:
    conf = get_group_config(chat_id)
    if not conf.get("is_enabled", True):
        return False

    if not is_forum:
        return True

    effective_thread = thread_id if thread_id is not None else 1
    topic_mode = conf.get("topic_mode", "selective")

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT is_enabled FROM group_topics 
            WHERE chat_id = ? AND thread_id = ?
        """, (chat_id, effective_thread))
        row = cursor.fetchone()

        if topic_mode == "all":
            return not (row and row["is_enabled"] == 0)
        else:
            return bool(row and row["is_enabled"] == 1)


def enable_topic(chat_id: int, thread_id: int):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO group_topics (chat_id, thread_id, is_enabled)
            VALUES (?, ?, 1)
            ON CONFLICT(chat_id, thread_id) DO UPDATE SET is_enabled = 1
        """, (chat_id, thread_id))
        cursor.execute("UPDATE groups SET topic_mode = 'selective' WHERE chat_id = ?", (chat_id,))
        conn.commit()


def disable_topic(chat_id: int, thread_id: int):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO group_topics (chat_id, thread_id, is_enabled)
            VALUES (?, ?, 0)
            ON CONFLICT(chat_id, thread_id) DO UPDATE SET is_enabled = 0
        """, (chat_id, thread_id))
        cursor.execute("UPDATE groups SET topic_mode = 'selective' WHERE chat_id = ?", (chat_id,))
        conn.commit()


def enable_all_topics(chat_id: int):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE groups SET topic_mode = 'all' WHERE chat_id = ?", (chat_id,))
        conn.commit()
