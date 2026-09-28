/* ==========================================================================
   Supabase 실시간 클라우드 데이터베이스 연동 어댑터
   (클라우드 다중 기기 실시간 동기화 필요 시 URL과 Anon Key만 입력하면 즉시 활성화)
   ========================================================================== */

export const SUPABASE_CONFIG = {
  url: 'https://upwsgyyllushlrwhowel.supabase.co',
  anonKey: 'sb_publishable_b5AzAj6pMhj782MaLLS5eQ_QFmWxHJK',
  enabled: true
};

/**
 * 실시간 변경사항 구독 (Supabase 활성화 시)
 */
export function subscribeToRealtimeChanges(onTerritoryChange, onTalentChange) {
  if (!SUPABASE_CONFIG.enabled || !window.supabase) {
    console.log('[Notice] Supabase 실시간 연동이 비활성화 상태입니다. 로컬 세션 및 메모리 모드로 안전하게 작동합니다.');
    return;
  }

  const client = window.supabase.createClient(SUPABASE_CONFIG.url, SUPABASE_CONFIG.anonKey);

  // 지경 변경 구독
  client.channel('public:territories')
    .on('postgres_changes', { event: '*', schema: 'public', table: 'territories' }, payload => {
      if (onTerritoryChange) onTerritoryChange(payload);
    })
    .subscribe();

  // 인재 변경 구독
  client.channel('public:talents')
    .on('postgres_changes', { event: '*', schema: 'public', table: 'talents' }, payload => {
      if (onTalentChange) onTalentChange(payload);
    })
    .subscribe();
}
