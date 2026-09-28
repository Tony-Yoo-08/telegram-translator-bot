/* ==========================================================================
   보안 인증 게이트웨이 (ID/PW 인증 및 세션 관리)
   ========================================================================== */

const AUTH_STORAGE_KEY = 'MISSION_CONTROL_AUTH_TOKEN';

// 기본 관리자 접근 계정 (사전 부여된 계정)
const AUTHORIZED_CREDENTIALS = [
  { id: 'admin', pw: 'mission2026!', label: '총괄 관제 (부장/총무/서무 공용)' },
  { id: 'head', pw: 'head2026!', label: '중앙 부장' },
  { id: 'affairs', pw: 'affairs2026!', label: '총무' },
  { id: 'sec', pw: 'sec2026!', label: '서무' }
];

export function checkIsAuthenticated() {
  const token = sessionStorage.getItem(AUTH_STORAGE_KEY);
  return token !== null && token.length > 0;
}

export function login(username, password) {
  const trimmedUser = username.trim();
  const trimmedPw = password.trim();

  const found = AUTHORIZED_CREDENTIALS.find(c => c.id === trimmedUser && c.pw === trimmedPw);
  if (found) {
    const token = btoa(`${trimmedUser}:${Date.now()}`);
    sessionStorage.setItem(AUTH_STORAGE_KEY, token);
    sessionStorage.setItem('CURRENT_USER_LABEL', found.label);
    return { success: true, user: found };
  }

  return { success: false, message: '아이디 또는 비밀번호가 올바르지 않습니다.' };
}

export function logout() {
  sessionStorage.removeItem(AUTH_STORAGE_KEY);
  sessionStorage.removeItem('CURRENT_USER_LABEL');
  window.location.reload();
}

export function getCurrentUser() {
  return sessionStorage.getItem('CURRENT_USER_LABEL') || '임원진';
}
