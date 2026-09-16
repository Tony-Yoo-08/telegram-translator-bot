import sqlite3
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / "auth_store.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """데이터베이스 및 테이블 초기화 (S4 원자적 저장소 준수)"""
    with get_connection() as conn:
        cursor = conn.cursor()
        # 사용자 테이블: user_id, 역할(admin, member, pending), 사용자명, 등록시각
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                role TEXT NOT NULL,
                username TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # 그룹 테이블: chat_id, 그룹명, 허용여부, 언어모드, 활성화여부
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS groups (
                chat_id INTEGER PRIMARY KEY,
                title TEXT,
                is_allowed INTEGER DEFAULT 0,
                lang_mode TEXT DEFAULT 'all',
                is_enabled INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # 시스템 플래그 테이블: 첫 관리자 부트스트랩 플래그 등 저장
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_flags (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        conn.commit()


def is_bootstrap_done() -> bool:
    """S5: 첫 관리자 부트스트랩이 완료되었는지 확인 (재기동 시 재발 방지)"""
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
    """사용자의 현재 권한(admin, member, pending) 조회"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT role FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return row["role"] if row else None


def set_user_role(user_id: int, role: str, username: str = ""):
    """사용자 권한 등록 및 갱신"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (user_id, role, username)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET role = excluded.role, username = excluded.username
        """, (user_id, role, username))
        conn.commit()


def get_admin_ids() -> List[int]:
    """등록된 관리자 user_id 목록 조회"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE role = 'admin'")
        return [row["user_id"] for row in cursor.fetchall()]


def count_admins() -> int:
    """현재 관리자 수 (S5: lockout 방지 검사용)"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM users WHERE role = 'admin'")
        return cursor.fetchone()["cnt"]


def is_group_allowed(chat_id: int) -> bool:
    """S11: 그룹이 승인된 그룹인지 확인"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT is_allowed FROM groups WHERE chat_id = ?", (chat_id,))
        row = cursor.fetchone()
        return bool(row and row["is_allowed"] == 1)


def set_group_allowed(chat_id: int, allowed: bool, title: str = ""):
    """그룹 승인 상태 설정"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO groups (chat_id, is_allowed, title)
            VALUES (?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET is_allowed = excluded.is_allowed, title = excluded.title
        """, (chat_id, 1 if allowed else 0, title))
        conn.commit()


def get_group_config(chat_id: int) -> Dict[str, Any]:
    """그룹의 언어 모드 및 번역 활성화 상태 조회"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT is_allowed, lang_mode, is_enabled FROM groups WHERE chat_id = ?", (chat_id,))
        row = cursor.fetchone()
        if row:
            return {
                "is_allowed": bool(row["is_allowed"]),
                "lang_mode": row["lang_mode"],
                "is_enabled": bool(row["is_enabled"])
            }
        return {"is_allowed": False, "lang_mode": "all", "is_enabled": True}


def update_group_config(chat_id: int, lang_mode: Optional[str] = None, is_enabled: Optional[bool] = None):
    """그룹 설정 변경"""
    with get_connection() as conn:
        cursor = conn.cursor()
        if lang_mode is not None:
            cursor.execute("UPDATE groups SET lang_mode = ? WHERE chat_id = ?", (lang_mode, chat_id))
        if is_enabled is not None:
            cursor.execute("UPDATE groups SET is_enabled = ? WHERE chat_id = ?", (1 if is_enabled else 0, chat_id))
        conn.commit()
