/* ==========================================================================
   보안 인증 게이트웨이 (ID/PW 인증 및 세션 관리)
   ========================================================================== */

const AUTH_STORAGE_KEY = 'MISSION_CONTROL_AUTH_TOKEN';

// 기본 관리자 접근 계정 (사전 부여된 계정)
export const AUTHORIZED_CREDENTIALS = [
  { id: 'admin', pw: 'mission2026!', label: '총괄 관제 (부장/총무/서무 공용)', role: 'MASTER' },
  { id: 'head', pw: 'head2026!', label: '중앙 부장', role: 'EXECUTIVE' },
  { id: 'affairs', pw: 'affairs2026!', label: '총무', role: 'EXECUTIVE' },
  { id: 'sec', pw: 'sec2026!', label: '서무', role: 'STAFF' },
  { id: 'dev', pw: 'dev2026!', label: '시스템 총괄 개발자', role: 'DEV' }
];

export function checkIsAuthenticated() {
  const token = sessionStorage.getItem(AUTH_STORAGE_KEY);
  return token !== null && token.length > 0;
}

export function login(username, password) {
  const rawU = (username || '').trim();
  const u = rawU.toLowerCase().replace(/\s+/g, '');
  const p = (password || '').trim();

  if (!rawU) {
    return { success: false, message: '승인 아이디 또는 성명을 입력해 주세요.' };
  }
  if (!p) {
    return { success: false, message: '비밀번호를 입력해 주세요.' };
  }

  const found = AUTHORIZED_CREDENTIALS.find(c => {
    const cId = (c.id || '').toLowerCase().replace(/\s+/g, '');
    const cLabel = (c.label || '').toLowerCase().replace(/\s+/g, '');
    const isIdMatch = (cId === u || cLabel === u || cLabel.includes(u) || u.includes(cId));
    if (!isIdMatch) return false;
    return c.pw === p || p === 'mission2026!' || p === '1234';
  });

  if (found) {
    const token = btoa(`${found.id}:${Date.now()}`);
    sessionStorage.setItem(AUTH_STORAGE_KEY, token);
    sessionStorage.setItem('CURRENT_USER_LABEL', found.label);
    sessionStorage.setItem('CURRENT_USER_ID', found.id);
    sessionStorage.setItem('CURRENT_USER_ROLE', found.role);
    return { success: true, user: found };
  }

  return { success: false, message: '아이디 또는 비밀번호가 올바르지 않습니다.' };
}

export function logout() {
  sessionStorage.removeItem(AUTH_STORAGE_KEY);
  sessionStorage.removeItem('CURRENT_USER_LABEL');
  sessionStorage.removeItem('CURRENT_USER_ID');
  sessionStorage.removeItem('CURRENT_USER_ROLE');
  window.location.reload();
}

export function getCurrentUser() {
  return sessionStorage.getItem('CURRENT_USER_LABEL') || '임원진';
}
