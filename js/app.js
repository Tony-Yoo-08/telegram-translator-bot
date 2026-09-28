/* ==========================================================================
   해외선교 총괄 관제 메인 애플리케이션 진입점 (App Controller)
   ========================================================================== */

import { TRIBES_CONFIG, CATEGORY_CONFIG, INITIAL_TERRITORIES, INITIAL_TALENTS, getCategoryByMembers } from './data.js';
import { initMapEngine, setTribeFilter, setCategoryFilter, setSearchFilter, addTerritoryData, getTerritories } from './map.js';
import { initTalentsEngine, setLanguageFilter, setStatusFilter, setTalentSearch, addNewTalent, getTalents } from './talents.js';
import { checkIsAuthenticated, login, logout, getCurrentUser } from './auth.js';

document.addEventListener('DOMContentLoaded', () => {
  // 1. 보안 인증 확인
  initAuthGate();

  // 2. 12지파 필터 바 렌더링
  renderTribeFilterBar();

  // 3. 지도 엔진 초기화
  initMapEngine(INITIAL_TERRITORIES, (selectedTerritory) => {
    openTerritoryDrawer(selectedTerritory);
  });

  // 4. 바돌로매 인재 현황판 초기화
  initTalentsEngine(INITIAL_TALENTS, 'talentsGalleryGrid', (selectedTalent) => {
    openTalentDetailModal(selectedTalent);
  });

  // 5. 상단 지표(통계) 업데이트
  updateGlobalStats();

  // 6. 이벤트 리스너 등록
  bindGlobalEvents();
});

/**
 * 보안 로그인 게이트 초기화
 */
function initAuthGate() {
  const loginModal = document.getElementById('loginModal');
  const userBadge = document.getElementById('currentUserBadge');

  if (!checkIsAuthenticated()) {
    loginModal.classList.add('open');
  } else {
    loginModal.classList.remove('open');
    if (userBadge) {
      userBadge.textContent = getCurrentUser();
    }
  }

  // 로그인 폼 제출
  const loginForm = document.getElementById('loginForm');
  if (loginForm) {
    loginForm.addEventListener('submit', (e) => {
      e.preventDefault();
      const user = document.getElementById('loginUser').value;
      const pass = document.getElementById('loginPass').value;
      const errorMsg = document.getElementById('loginErrorMsg');

      const result = login(user, pass);
      if (result.success) {
        loginModal.classList.remove('open');
        if (userBadge) userBadge.textContent = getCurrentUser();
        // 지도 크기 재계산
        setTimeout(() => window.dispatchEvent(new Event('resize')), 300);
      } else {
        errorMsg.textContent = result.message;
        errorMsg.style.display = 'block';
      }
    });
  }

  // 로그아웃 버튼
  const logoutBtn = document.getElementById('logoutBtn');
  if (logoutBtn) {
    logoutBtn.addEventListener('click', () => {
      if (confirm('시스템에서 로그아웃 하시겠습니까?')) {
        logout();
      }
    });
  }
}

/**
 * 12지파 색상표 기반 가로형 필터 칩 렌더링
 */
function renderTribeFilterBar() {
  const container = document.getElementById('tribeFilterBar');
  if (!container) return;

  let html = `
    <button class="tribe-chip active" data-tribe="ALL">
      <span style="font-size: 13px;">🌐</span> 전체 지파
    </button>
  `;

  Object.values(TRIBES_CONFIG).forEach(t => {
    html += `
      <button class="tribe-chip" data-tribe="${t.id}" title="${t.gem} (${t.pantone})">
        <span class="tribe-gem-dot" style="background-color: ${t.color}; color: ${t.color};"></span>
        <span style="color: ${t.id === 8 ? '#86cab6; font-weight:800;' : ''}">${t.name}</span>
        <span style="font-size: 10px; opacity: 0.65;">${t.gem}</span>
      </button>
    `;
  });

  container.innerHTML = html;

  container.querySelectorAll('.tribe-chip').forEach(chip => {
    chip.addEventListener('click', (e) => {
      container.querySelectorAll('.tribe-chip').forEach(c => c.classList.remove('active'));
      chip.classList.add('active');

      const tribeId = chip.getAttribute('data-tribe');
      const parsedId = tribeId === 'ALL' ? null : parseInt(tribeId, 10);
      setTribeFilter(parsedId, (item) => openTerritoryDrawer(item));
      updateGlobalStats();
    });
  });
}

/**
 * 상단 핵심 지표 업데이트
 */
function updateGlobalStats() {
  const territories = getTerritories();
  const talents = getTalents();

  let churches = 0;
  let branches = 0;
  let pioneers = 0;
  let totalMembers = 0;

  territories.forEach(t => {
    totalMembers += t.members;
    if (t.members >= 300) churches++;
    else if (t.members >= 50) branches++;
    else pioneers++;
  });

  const elTotal = document.getElementById('statTotalTerritories');
  const elChurch = document.getElementById('statChurches');
  const elBranch = document.getElementById('statBranches');
  const elPioneer = document.getElementById('statPioneers');
  const elTalents = document.getElementById('statTalents');

  if (elTotal) elTotal.textContent = territories.length;
  if (elChurch) elChurch.textContent = churches;
  if (elBranch) elBranch.textContent = branches;
  if (elPioneer) elPioneer.textContent = pioneers;
  if (elTalents) elTalents.textContent = talents.length;
}

/**
 * 전역 이벤트 바인딩 (탭 전환, 검색, 모달 열기/닫기)
 */
function bindGlobalEvents() {
  // 탭 전환
  const tabMap = document.getElementById('tabMapBtn');
  const tabTalents = document.getElementById('tabTalentsBtn');
  const viewMap = document.getElementById('mapViewSection');
  const viewTalents = document.getElementById('talentViewSection');

  if (tabMap && tabTalents) {
    tabMap.addEventListener('click', () => {
      tabMap.classList.add('active');
      tabTalents.classList.remove('active');
      viewMap.style.display = 'flex';
      viewTalents.style.display = 'none';
      setTimeout(() => window.dispatchEvent(new Event('resize')), 100);
    });

    tabTalents.addEventListener('click', () => {
      tabTalents.classList.add('active');
      tabMap.classList.remove('active');
      viewMap.style.display = 'none';
      viewTalents.style.display = 'flex';
    });
  }

  // 지경 지도 등급 필터 (전체, 교회 300+, 지역 50+, 개척지 0)
  document.querySelectorAll('.cat-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      document.querySelectorAll('.cat-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const cat = btn.getAttribute('data-cat');
      setCategoryFilter(cat === 'ALL' ? null : cat, (item) => openTerritoryDrawer(item));
    });
  });

  // 지도 도시/국가 실시간 검색
  const mapSearchInput = document.getElementById('mapSearchInput');
  if (mapSearchInput) {
    mapSearchInput.addEventListener('input', (e) => {
      setSearchFilter(e.target.value, (item) => openTerritoryDrawer(item));
    });
  }

  // 지경 상세 드로어 닫기
  const closeDrawerBtn = document.getElementById('closeDrawerBtn');
  if (closeDrawerBtn) {
    closeDrawerBtn.addEventListener('click', () => {
      document.getElementById('territoryDrawer').classList.remove('open');
    });
  }

  // 인재 현황판 - 언어 필터 칩
  document.querySelectorAll('.talent-lang-pill').forEach(pill => {
    pill.addEventListener('click', () => {
      document.querySelectorAll('.talent-lang-pill').forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      const lang = pill.getAttribute('data-lang');
      setLanguageFilter(lang, 'talentsGalleryGrid', (talent) => openTalentDetailModal(talent));
    });
  });

  // 인재 현황판 - 상태 필터 칩
  document.querySelectorAll('.talent-status-pill-btn').forEach(pill => {
    pill.addEventListener('click', () => {
      document.querySelectorAll('.talent-status-pill-btn').forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      const status = pill.getAttribute('data-status');
      setStatusFilter(status, 'talentsGalleryGrid', (talent) => openTalentDetailModal(talent));
    });
  });

  // 인재 검색창
  const talentSearchInput = document.getElementById('talentSearchInput');
  if (talentSearchInput) {
    talentSearchInput.addEventListener('input', (e) => {
      setTalentSearch(e.target.value, 'talentsGalleryGrid', (talent) => openTalentDetailModal(talent));
    });
  }

  // 신규 지경 추가 모달 제어
  const openAddTerritoryBtn = document.getElementById('openAddTerritoryBtn');
  const addTerritoryModal = document.getElementById('addTerritoryModal');
  const closeAddTerritoryBtn = document.getElementById('closeAddTerritoryBtn');
  const cancelAddTerritoryBtn = document.getElementById('cancelAddTerritoryBtn');

  if (openAddTerritoryBtn && addTerritoryModal) {
    openAddTerritoryBtn.addEventListener('click', () => {
      populateTribeSelect();
      addTerritoryModal.classList.add('open');
    });
    closeAddTerritoryBtn.addEventListener('click', () => addTerritoryModal.classList.remove('open'));
    cancelAddTerritoryBtn.addEventListener('click', () => addTerritoryModal.classList.remove('open'));
  }

  // 신규 지경 폼 제출
  const addTerritoryForm = document.getElementById('addTerritoryForm');
  if (addTerritoryForm) {
    addTerritoryForm.addEventListener('submit', (e) => {
      e.preventDefault();
      const tribeId = parseInt(document.getElementById('newTribeId').value, 10);
      const country = document.getElementById('newCountry').value.trim();
      const city = document.getElementById('newCity').value.trim();
      const category = document.getElementById('newCategory')?.value || 'PIONEER';
      const unitType = document.querySelector('input[name="newTerritoryUnit"]:checked')?.value || 'CITY';
      const members = parseInt(document.getElementById('newMembers').value, 10) || 0;
      const lat = parseFloat(document.getElementById('newLat').value);
      const lng = parseFloat(document.getElementById('newLng').value);
      const leader = document.getElementById('newLeader').value.trim();
      const notes = document.getElementById('newNotes').value.trim();

      const newTerritory = {
        id: `TR-${Date.now()}`,
        tribeId,
        country,
        city,
        unitType,
        category,
        members,
        lat,
        lng,
        leader: leader || '지경 책임자',
        establishedYear: new Date().getFullYear(),
        notes: notes || (unitType === 'STATE' ? '신규 주 단위 지경 등록' : '신규 지경 등록'),
        updatedAt: new Date().toISOString().split('T')[0]
      };

      addTerritoryData(newTerritory, (item) => openTerritoryDrawer(item));
      updateGlobalStats();
      addTerritoryModal.classList.remove('open');
      addTerritoryForm.reset();
      openTerritoryDrawer(newTerritory);
    });
  }

  // 신규 인재 추가 모달 제어
  const openAddTalentBtn = document.getElementById('openAddTalentBtn');
  const addTalentModal = document.getElementById('addTalentModal');
  const closeAddTalentBtn = document.getElementById('closeAddTalentBtn');
  const cancelAddTalentBtn = document.getElementById('cancelAddTalentBtn');

  if (openAddTalentBtn && addTalentModal) {
    openAddTalentBtn.addEventListener('click', () => addTalentModal.classList.add('open'));
  }
  if (closeAddTalentBtn && addTalentModal) {
    closeAddTalentBtn.addEventListener('click', () => addTalentModal.classList.remove('open'));
  }
  if (cancelAddTalentBtn && addTalentModal) {
    cancelAddTalentBtn.addEventListener('click', () => addTalentModal.classList.remove('open'));
  }

  // 신규 인재 폼 제출
  const addTalentForm = document.getElementById('addTalentForm');
  if (addTalentForm) {
    addTalentForm.addEventListener('submit', (e) => {
      e.preventDefault();
      const name = document.getElementById('newTalentName').value.trim();
      const gender = document.getElementById('newTalentGender').value;
      const age = parseInt(document.getElementById('newTalentAge').value, 10);
      const department = document.getElementById('newTalentDept').value;
      const role = document.getElementById('newTalentRole').value.trim();
      const primaryLanguage = document.getElementById('newTalentPrimaryLang').value;
      const langLevel = document.getElementById('newTalentLangLevel').value.trim();
      const status = document.getElementById('newTalentStatus').value;
      const targetCities = document.getElementById('newTalentCities').value.split(',').map(s => s.trim()).filter(Boolean);
      const specialties = document.getElementById('newTalentSpecialties').value.split(',').map(s => s.trim()).filter(Boolean);
      const contact = document.getElementById('newTalentContact').value.trim();
      const memo = document.getElementById('newTalentMemo').value.trim();

      const statusMap = {
        READY: '즉시 파견 가능',
        DISPATCHED: '현지 파견중',
        TRAINING: '사역 연수중',
        STANDBY: '국내 사역 (언어 지원)'
      };

      const newTalent = {
        id: `TAL-${Date.now()}`,
        name,
        gender,
        age,
        department,
        role: role || '성도',
        photo: 'https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?auto=format&fit=crop&q=80&w=300',
        status,
        statusLabel: statusMap[status],
        primaryLanguage,
        languages: [{ name: primaryLanguage, level: langLevel || '회화 가능' }],
        targetCountries: ['해외 전체'],
        targetCities: targetCities.length > 0 ? targetCities : ['희망지 미정'],
        specialties: specialties.length > 0 ? specialties : ['언어소통'],
        contact: contact || '-',
        memo: memo || '신규 인재 등록',
        experience: '등록 완료'
      };

      addNewTalent(newTalent, 'talentsGalleryGrid', (t) => openTalentDetailModal(t));
      updateGlobalStats();
      addTalentModal.classList.remove('open');
      addTalentForm.reset();
      openTalentDetailModal(newTalent);
    });
  }

  // 모달 외부 클릭 닫기
  window.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal-overlay') && !e.target.classList.contains('login-gate-modal')) {
      e.target.classList.remove('open');
    }
  });
}

/**
 * 지경 추가 시 12지파 셀렉트 박스 채우기
 */
function populateTribeSelect() {
  const select = document.getElementById('newTribeId');
  if (!select || select.children.length > 0) return;

  Object.values(TRIBES_CONFIG).forEach(t => {
    const opt = document.createElement('option');
    opt.value = t.id;
    opt.textContent = `${t.name}지파 (${t.gem} - ${t.pantone})`;
    if (t.id === 8) opt.selected = true; // 바돌로매 기본 선택
    select.appendChild(opt);
  });
}

/**
 * 지경 상세 정보 슬라이드 드로어 열기
 */
function openTerritoryDrawer(item) {
  const drawer = document.getElementById('territoryDrawer');
  if (!drawer) return;

  const tribe = TRIBES_CONFIG[item.tribeId] || { name: '지파', color: '#86cab6', textColor: '#fff' };
  const cat = getCategoryByMembers(item.members);

  document.getElementById('drawerTribeBadge').style.backgroundColor = tribe.color;
  document.getElementById('drawerTribeBadge').style.color = tribe.textColor;
  document.getElementById('drawerTribeBadge').textContent = `${tribe.name}지파`;

  document.getElementById('drawerCategoryBadge').className = `talent-status-pill ${cat.badgeClass}`;
  document.getElementById('drawerCategoryBadge').textContent = cat.name;

  const isState = item.unitType === 'STATE';
  const unitBadge = document.getElementById('drawerUnitBadge');
  if (unitBadge) {
    unitBadge.style.display = 'inline-flex';
    if (isState) {
      unitBadge.textContent = '🗺️ 주·광역 단위 (State)';
      unitBadge.style.background = 'rgba(99, 102, 241, 0.18)';
      unitBadge.style.color = '#a5b4fc';
      unitBadge.style.border = '1px solid rgba(99, 102, 241, 0.45)';
    } else {
      unitBadge.textContent = '🏙️ 도시 단위 (City)';
      unitBadge.style.background = 'rgba(148, 163, 184, 0.12)';
      unitBadge.style.color = 'var(--text-dim)';
      unitBadge.style.border = '1px solid var(--border-subtle)';
    }
  }

  const unitSuffix = isState ? ' [주단위 관할]' : '';
  document.getElementById('drawerCityTitle').textContent = `${item.country} ${item.city}${unitSuffix}`;
  document.getElementById('drawerMembersCount').textContent = `${item.members.toLocaleString()}명`;
  document.getElementById('drawerCategoryName').textContent = `${cat.name} (${cat.desc})`;
  document.getElementById('drawerLeader').textContent = item.leader || '미정';
  document.getElementById('drawerEstYear').textContent = item.establishedYear ? `${item.establishedYear}년` : '-';
  document.getElementById('drawerAddress').textContent = item.address || `${item.country} ${item.city}`;
  document.getElementById('drawerNotes').textContent = item.notes || '기록된 특이사항이 없습니다.';

  drawer.classList.add('open');
}

/**
 * 인재 상세 모달 열기
 */
function openTalentDetailModal(talent) {
  const modal = document.getElementById('talentDetailModal');
  if (!modal) return;

  document.getElementById('detailTalentName').textContent = talent.name;
  document.getElementById('detailTalentRole').textContent = `[${talent.role}] ${talent.department} · ${talent.gender} ${talent.age}세`;
  document.getElementById('detailTalentAvatar').src = talent.photo;
  document.getElementById('detailTalentStatus').textContent = talent.statusLabel;

  // 언어 렌더링
  const langContainer = document.getElementById('detailTalentLanguages');
  langContainer.innerHTML = talent.languages.map(l => `
    <div style="background: rgba(255,255,255,0.05); border: 1px solid var(--border-subtle); padding: 0.5rem 0.75rem; border-radius: 6px;">
      <div style="font-weight: 700; color: #fff; font-size: 0.85rem;">${l.name} <span style="color: var(--primary); font-size: 0.8rem;">[${l.level}]</span></div>
      ${l.exam ? `<div style="font-size: 0.74rem; color: var(--text-dim); margin-top: 2px;">공인시험: ${l.exam}</div>` : ''}
    </div>
  `).join('');

  // 희망 지역
  document.getElementById('detailTalentCities').textContent = talent.targetCities.join(', ') + ` (${talent.targetCountries.join(', ')})`;

  // 특기
  document.getElementById('detailTalentSpecialties').textContent = talent.specialties.join(', ');

  // 경력 및 비고
  document.getElementById('detailTalentExp').textContent = talent.experience || '경력 정보 없음';
  document.getElementById('detailTalentMemo').textContent = talent.memo || '메모 없음';
  document.getElementById('detailTalentContact').textContent = talent.contact || '연락처 미등록';

  modal.classList.add('open');

  document.getElementById('closeTalentDetailBtn').onclick = () => modal.classList.remove('open');
}
