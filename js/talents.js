/* ==========================================================================
   바돌로매지파 해외 언어 인재 현황판 (Card Gallery View & Management)
   ========================================================================== */

let allTalents = [];
let currentLangFilter = 'ALL';
let currentStatusFilter = 'ALL';
let talentSearchQuery = '';

export function initTalentsEngine(initialData, containerId, onOpenDetailModal) {
  allTalents = [...initialData];
  renderTalentGallery(containerId, onOpenDetailModal);
}

/**
 * 인재 카드 갤러리 그리드 렌더링
 */
export function renderTalentGallery(containerId, onOpenDetailModal) {
  const container = document.getElementById(containerId);
  if (!container) return;

  // 필터링 적용
  const filtered = allTalents.filter(talent => {
    // 언어 필터
    if (currentLangFilter !== 'ALL') {
      const hasLang = talent.languages.some(l => l.name.includes(currentLangFilter)) || 
                      talent.primaryLanguage.includes(currentLangFilter);
      if (!hasLang) return false;
    }

    // 파견 상태 필터
    if (currentStatusFilter !== 'ALL') {
      if (talent.status !== currentStatusFilter) return false;
    }

    // 검색어 필터
    if (talentSearchQuery.trim() !== '') {
      const q = talentSearchQuery.toLowerCase();
      const matchName = talent.name.toLowerCase().includes(q);
      const matchDept = talent.department.toLowerCase().includes(q);
      const matchSpecialty = talent.specialties.some(s => s.toLowerCase().includes(q));
      const matchCity = talent.targetCities.some(c => c.toLowerCase().includes(q)) || 
                        talent.targetCountries.some(c => c.toLowerCase().includes(q));
      if (!matchName && !matchDept && !matchSpecialty && !matchCity) return false;
    }

    return true;
  });

  if (filtered.length === 0) {
    container.innerHTML = `
      <div style="grid-column: 1 / -1; text-align: center; padding: 4rem 1rem; color: var(--text-dim);">
        <div style="font-size: 2.5rem; margin-bottom: 0.75rem;">🔍</div>
        <h4 style="color: #fff; font-size: 1.1rem; margin-bottom: 0.35rem;">조건에 맞는 인재가 없습니다.</h4>
        <p style="font-size: 0.85rem;">필터 조건을 변경하거나 검색어를 초기화해보세요.</p>
      </div>
    `;
    return;
  }

  // 카드 HTML 생성
  container.innerHTML = filtered.map(talent => {
    const statusClass = getStatusClass(talent.status);

    return `
      <div class="talent-card" data-id="${talent.id}">
        <!-- Card Header: Profile & Status -->
        <div class="talent-card-header">
          <img src="${talent.photo}" alt="${talent.name}" class="talent-avatar" onerror="this.src='https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?auto=format&fit=crop&q=80&w=200'">
          <div class="talent-basic-info">
            <div class="talent-name-wrap">
              <span class="talent-name">${talent.name}</span>
              <span style="font-size: 0.76rem; color: var(--primary); font-weight: 700;">[${talent.role}]</span>
            </div>
            <div class="talent-age-dept">${talent.department} · ${talent.gender} ${talent.age}세</div>
            <div class="talent-status-pill ${statusClass}">
              <span class="status-dot"></span>
              ${talent.statusLabel}
            </div>
          </div>
        </div>

        <!-- Card Body: Languages & Target Territories -->
        <div class="talent-card-body">
          <!-- 언어 역량 -->
          <div>
            <div class="field-group-title">구사 가능 언어</div>
            <div class="lang-badge-group">
              ${talent.languages.map(l => `
                <span class="lang-chip ${l.name === talent.primaryLanguage ? 'primary-lang' : ''}" title="${l.exam || ''}">
                  <strong>${l.name}</strong> ${l.level.split(' ')[0]}
                </span>
              `).join('')}
            </div>
          </div>

          <!-- 희망 파견 지경 -->
          <div>
            <div class="field-group-title">희망 파견 국가 및 도시</div>
            <div class="target-city-group">
              ${talent.targetCities.map(c => `
                <span class="city-tag">📍 ${c}</span>
              `).join('')}
              ${talent.targetCountries.map(cnt => `
                <span class="city-tag" style="background: rgba(255,255,200,0.03); color: var(--text-dim);">${cnt}</span>
              `).join('')}
            </div>
          </div>

          <!-- 핵심 특기 및 전공 -->
          <div>
            <div class="field-group-title">핵심 역량 / 특기</div>
            <div style="display: flex; flex-wrap: wrap; gap: 0.25rem;">
              ${talent.specialties.map(s => `
                <span style="font-size: 0.74rem; color: #cbd5e1; background: rgba(255,255,255,0.04); padding: 0.15rem 0.45rem; border-radius: 4px;">
                  #${s}
                </span>
              `).join('')}
            </div>
          </div>
        </div>

        <!-- Card Footer: Quick Actions -->
        <div class="talent-card-footer">
          <span style="font-size: 0.75rem; color: var(--text-dim);">
            ${talent.contact ? `📞 ${talent.contact}` : '연락처 비공개'}
          </span>
          <button class="btn-secondary btn-detail-action" style="padding: 0.35rem 0.75rem; font-size: 0.78rem;" data-id="${talent.id}">
            상세 정보 보기 ➔
          </button>
        </div>
      </div>
    `;
  }).join('');

  // 클릭 이벤트 바인딩
  container.querySelectorAll('.btn-detail-action').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const id = e.currentTarget.getAttribute('data-id');
      const item = allTalents.find(t => t.id === id);
      if (item && onOpenDetailModal) {
        onOpenDetailModal(item);
      }
    });
  });
}

function getStatusClass(status) {
  switch (status) {
    case 'READY': return 'status-ready';
    case 'DISPATCHED': return 'status-dispatched';
    case 'TRAINING': return 'status-training';
    case 'STANDBY': default: return 'status-standby';
  }
}

/**
 * 언어 필터 설정
 */
export function setLanguageFilter(lang, containerId, onOpenDetailModal) {
  currentLangFilter = lang;
  renderTalentGallery(containerId, onOpenDetailModal);
}

/**
 * 상태 필터 설정
 */
export function setStatusFilter(status, containerId, onOpenDetailModal) {
  currentStatusFilter = status;
  renderTalentGallery(containerId, onOpenDetailModal);
}

/**
 * 검색어 필터 설정
 */
export function setTalentSearch(query, containerId, onOpenDetailModal) {
  talentSearchQuery = query;
  renderTalentGallery(containerId, onOpenDetailModal);
}

/**
 * 신규 인재 추가
 */
export function addNewTalent(newTalent, containerId, onOpenDetailModal) {
  allTalents.unshift(newTalent);
  renderTalentGallery(containerId, onOpenDetailModal);
}

/**
 * 인재 정보 수정
 */
export function updateTalent(updatedTalent, containerId, onOpenDetailModal) {
  const idx = allTalents.findIndex(t => t.id === updatedTalent.id);
  if (idx !== -1) {
    allTalents[idx] = updatedTalent;
    renderTalentGallery(containerId, onOpenDetailModal);
  }
}

/**
 * 인재 정보 삭제
 */
export function deleteTalent(id, containerId, onOpenDetailModal) {
  allTalents = allTalents.filter(t => t.id !== id);
  renderTalentGallery(containerId, onOpenDetailModal);
}

/**
 * 전체 인재 데이터 반환 (통계용)
 */
export function getTalents() {
  return allTalents;
}
