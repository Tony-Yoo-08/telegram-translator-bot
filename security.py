import hmac
import time
import os
import logging
from typing import Dict, List, Tuple
from db import get_user_role, get_admin_ids

logger = logging.getLogger(__name__)

# S5: .env 비상 관리자 ID (설정 시 DB 손상/부트스트랩 초기화와 무관하게 영구 관리자로 인정)
EMERGENCY_ADMIN_ID = os.getenv("EMERGENCY_ADMIN_ID", "").strip()

# S10: 레이트 리밋 메모리 저장소
# user_id -> [timestamp, ...]
_user_request_times: Dict[int, List[float]] = {}
# user_id -> (failed_count, blocked_until)
_failed_auth_attempts: Dict[int, Tuple[int, float]] = {}


def verify_payload(input_payload: str, expected_payload: str) -> bool:
    """
    S4: hmac.compare_digest를 사용한 타이밍 공격 방지 payload 대조
    """
    if not input_payload or not expected_payload:
        return False
    return hmac.compare_digest(input_payload.strip(), expected_payload.strip())


def is_admin(user_id: int) -> bool:
    """
    S5: 관리자 여부 확인 (DB 등록 관리자 또는 .env 비상 관리자)
    """
    if EMERGENCY_ADMIN_ID and str(user_id) == EMERGENCY_ADMIN_ID:
        return True
    return get_user_role(user_id) == "admin"


def is_approved_member(user_id: int) -> bool:
    """
    S5: 승인된 멤버 또는 관리자 여부 확인
    """
    if is_admin(user_id):
        return True
    return get_user_role(user_id) == "member"


def check_rate_limit(user_id: int, max_requests: int = 15, window_seconds: int = 30) -> bool:
    """
    S10: 과도한 요청 차단 (30초 동안 15건 초과 시 차단)
    Returns: True(허용), False(차단)
    """
    now = time.time()
    history = _user_request_times.setdefault(user_id, [])
    # 윈도우 이전 기록 정리
    _user_request_times[user_id] = [t for t in history if now - t < window_seconds]
    
    if len(_user_request_times[user_id]) >= max_requests:
        logger.warning("S10: 레이트 리밋 초과 감지")
        return False

    _user_request_times[user_id].append(now)
    return True


def check_auth_abuse(user_id: int) -> bool:
    """
    S10: payload 무차별 대입 차단 (10분 내 5회 실패 시 10분 차단)
    Returns: True(차단됨), False(정상)
    """
    now = time.time()
    if user_id in _failed_auth_attempts:
        count, blocked_until = _failed_auth_attempts[user_id]
        if now < blocked_until:
            return True
        elif now >= blocked_until and count >= 5:
            # 차단 시간 만료 시 초기화
            del _failed_auth_attempts[user_id]
    return False


def record_failed_auth(user_id: int):
    """S10: 인증 실패 기록"""
    now = time.time()
    count, _ = _failed_auth_attempts.get(user_id, (0, 0.0))
    count += 1
    blocked_until = now + 600.0 if count >= 5 else 0.0  # 5회 이상 실패 시 10분 차단
    _failed_auth_attempts[user_id] = (count, blocked_until)
    if count >= 5:
        logger.warning("S10: payload 무차별 시도로 인한 사용자 차단 활성화")
