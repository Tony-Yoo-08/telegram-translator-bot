/* ==========================================================================
   12지파 해외지경판 지도 엔진 (Leaflet + CartoDB Dark Matter - 워터마크 0%)
   ========================================================================== */

import { TRIBES_CONFIG, CATEGORY_CONFIG, getCategoryByMembers } from './data.js';

let mapInstance = null;
let currentMarkers = [];
let boundaryLayerGroup = null;
let missionRouteLayerGroup = null;
let allTerritories = [];
let selectedTribeId = null; // null = 전체
let selectedCategory = null; // null = 전체
let searchQuery = '';
let isBoundaryEnabled = true;

function generateCityBoundaryPolygon(lat, lng, cityName, gradeKey, isState = false) {
  const baseRadius = isState
    ? (gradeKey === 'CHURCH' ? 0.65 : (gradeKey === 'BRANCH' ? 0.50 : 0.38))
    : (gradeKey === 'CHURCH' ? 0.135 : (gradeKey === 'BRANCH' ? 0.095 : 0.068));
  let seed = 0;
  const cleanName = (cityName || 'city').trim().toLowerCase();
  for (let i = 0; i < cleanName.length; i++) {
    seed = (seed * 31 + cleanName.charCodeAt(i)) & 0xFFFFFFFF;
  }

  const points = [];
  const numPoints = 18;
  const cosLat = Math.cos(lat * Math.PI / 180) || 1;

  for (let i = 0; i < numPoints; i++) {
    const angle = (i / numPoints) * 2 * Math.PI;
    const wobble1 = Math.sin(angle * 3 + (seed % 17)) * 0.22;
    const wobble2 = Math.cos(angle * 2 - (seed % 13)) * 0.18;
    const wobble3 = Math.sin(angle * 5 + (seed % 7)) * 0.08;
    const r = baseRadius * (1.0 + wobble1 + wobble2 + wobble3);

    const latOffset = r * Math.cos(angle);
    const lngOffset = (r / cosLat) * Math.sin(angle);
    points.push([Number((lat + latOffset).toFixed(5)), Number((lng + lngOffset).toFixed(5))]);
  }
  return points;
}

function renderCityBoundaries(filtered, onSelectTerritory) {
  if (!mapInstance || !boundaryLayerGroup) return;
  boundaryLayerGroup.clearLayers();
  if (missionRouteLayerGroup) missionRouteLayerGroup.clearLayers();

  if (!isBoundaryEnabled) return;

  if (selectedTribeId !== null && filtered.length > 1) {
    const tribe = TRIBES_CONFIG[selectedTribeId] || { color: '#86cab6', name: '지파' };
    const latlngs = filtered.map(t => [t.lat, t.lng]);
    const polyline = L.polyline(latlngs, {
      color: tribe.color,
      weight: 2.2,
      opacity: 0.75,
      dashArray: '6, 8'
    });
    polyline.bindTooltip(`<strong>[${tribe.name || ''}지파]</strong> 선교 도시 연결망`, { sticky: true, className: 'custom-clean-tooltip' });
    missionRouteLayerGroup.addLayer(polyline);
  }

  filtered.forEach(item => {
    const tribe = TRIBES_CONFIG[item.tribeId] || { name: '지파', color: '#86cab6', textColor: '#fff' };
    const cat = getCategoryByMembers(item);
    const isState = item.unitType === 'STATE';
    const polygonPoints = generateCityBoundaryPolygon(item.lat, item.lng, item.city, cat.key, isState);

    const layer = L.polygon(polygonPoints, {
      color: tribe.color,
      weight: isState ? 3.0 : 2.5,
      opacity: 0.9,
      dashArray: isState ? '8, 6' : '5, 4',
      fillColor: tribe.color,
      fillOpacity: isState ? 0.16 : 0.22,
      lineJoin: 'round'
    });

    const hasMembers = (item.members !== undefined && item.members !== null && item.members > 0);
    const memberText = hasMembers ? `${item.members.toLocaleString()}명` : (item.category ? '성도 수 미상 (등급 등록)' : '0명');

    layer.bindTooltip(`
      <div style="font-family: inherit; font-size: 12px; line-height: 1.4; color: #fff;">
        <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:${tribe.color}; margin-right:4px;"></span>
        <strong>[${tribe.name}지파]</strong> ${item.city} 관할 지경 ${isState ? '<span class="badge-state-tag">주단위 관할</span>' : ''}<br>
        <span style="color: ${cat.color}; font-weight:700;">${cat.name}</span> (${memberText})
      </div>
    `, { sticky: true, direction: 'top', className: 'custom-clean-tooltip', opacity: 0.95 });

    layer.on('mouseover', function () {
      this.setStyle({ weight: 3.8, opacity: 1, fillOpacity: 0.42, color: '#ffffff' });
    });
    layer.on('mouseout', function () {
      this.setStyle({ weight: 2.5, opacity: 0.9, fillOpacity: 0.22, color: tribe.color });
    });
    layer.on('click', () => {
      if (onSelectTerritory) onSelectTerritory(item);
      mapInstance.flyTo([item.lat, item.lng], Math.max(mapInstance.getZoom(), 7), { duration: 1.2 });
    });

    boundaryLayerGroup.addLayer(layer);
  });
}

export function initMapEngine(territories, onSelectTerritory) {
  allTerritories = [...territories];

  // 지도 인스턴스 초기화 (기본 전 세계 뷰)
  mapInstance = L.map('missionMap', {
    center: [28.0, 15.0],
    zoom: 3,
    minZoom: 2,
    maxZoom: 18,
    zoomControl: false, // 기본 줌 컨트롤 숨김 (커스텀 배치)
    attributionControl: false // 상용 워터마크 및 불필요한 로고 완전 제거 (깨끗한 화면)
  });

  // 우측 하단에 미려한 줌 컨트롤 추가
  L.control.zoom({ position: 'bottomright' }).addTo(mapInstance);

  // 워터마크 0% 고화질 Esri 다크 캔버스 레이어 (Base + 국경/도시명 Reference 레이어)
  const baseLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
    maxNativeZoom: 16,
    maxZoom: 19,
    attribution: 'Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ'
  });
  const refLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}', {
    maxNativeZoom: 16,
    maxZoom: 19,
    pane: 'overlayPane'
  });
  L.layerGroup([baseLayer, refLayer]).addTo(mapInstance);

  boundaryLayerGroup = L.layerGroup().addTo(mapInstance);
  missionRouteLayerGroup = L.layerGroup().addTo(mapInstance);

  // 초기 마커 렌더링
  renderMarkers(onSelectTerritory);
}

/**
 * 12지파 및 등급별 필터링된 마커를 지도상에 렌더링
 */
export function renderMarkers(onSelectTerritory) {
  if (!mapInstance) return;

  // 기존 마커 전체 제거
  currentMarkers.forEach(m => mapInstance.removeLayer(m));
  currentMarkers = [];

  // 필터 조건 적용
  const filtered = allTerritories.filter(item => {
    // 지파 필터
    if (selectedTribeId !== null && item.tribeId !== selectedTribeId) {
      return false;
    }

    // 등급 필터 (개척지, 지역, 교회)
    if (selectedCategory !== null) {
      const cat = getCategoryByMembers(item);
      if (cat.key !== selectedCategory) return false;
    }

    // 검색어 필터 (국가, 도시, 사역자)
    if (searchQuery.trim() !== '') {
      const q = searchQuery.toLowerCase();
      const match = item.country.toLowerCase().includes(q) ||
                    item.city.toLowerCase().includes(q) ||
                    (item.leader && item.leader.toLowerCase().includes(q));
      if (!match) return false;
    }

    return true;
  });

  // 도시별 지파 고유 색상 행정 경계선 및 영역 채색
  renderCityBoundaries(filtered, onSelectTerritory);

  // 마커 생성 및 바인딩
  filtered.forEach(item => {
    const tribe = TRIBES_CONFIG[item.tribeId] || { name: '지파', color: '#86cab6', textColor: '#fff' };
    const cat = getCategoryByMembers(item);
    const hasMembers = (item.members !== undefined && item.members !== null && item.members > 0);
    const memberText = hasMembers ? `${item.members.toLocaleString()}명` : (item.category ? '성도 수 미상 (등급 등록)' : '0명');

    const isState = item.unitType === 'STATE';
    const unitBadgeHtml = isState ? `<div class="marker-unit-badge" title="주/광역 단위 관할 지경">주</div>` : '';
    const statePulseHtml = isState ? `<div class="marker-pulse-state"></div>` : '';

    // 커스텀 SVG 마커 HTML 생성
    const markerHtml = `
      <div class="custom-city-marker ${isState ? 'marker-state-mode' : ''}" title="${tribe.name}지파 - ${item.country} ${item.city} ${isState ? '(주단위 관할)' : ''}">
        ${statePulseHtml}
        ${cat.key === 'CHURCH' ? `<div class="marker-pulse" style="background: ${tribe.color};"></div>` : ''}
        ${unitBadgeHtml}
        <div class="marker-inner" style="background: ${tribe.color}; border-color: ${isState ? '#818cf8' : cat.color};">
          <span style="font-size: 11px; font-weight: 800; color: ${tribe.textColor};">
            ${tribe.name.substring(0, 1)}
          </span>
          <div class="marker-badge-category" style="background: ${cat.color};" title="${cat.name} (${memberText})"></div>
        </div>
      </div>
    `;

    const customIcon = L.divIcon({
      html: markerHtml,
      className: 'custom-leaflet-icon',
      iconSize: [32, 32],
      iconAnchor: [16, 16]
    });

    const marker = L.marker([item.lat, item.lng], { icon: customIcon });

    // 툴팁 바인딩
    marker.bindTooltip(`
      <div style="font-family: inherit; font-size: 12px; line-height: 1.4; color: #fff;">
        <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:${tribe.color}; margin-right:4px;"></span>
        <strong>[${tribe.name}지파]</strong> ${item.country} · ${item.city} ${isState ? '<span class="badge-state-tag">주단위 관할</span>' : ''}<br>
        <span style="color: ${cat.color}; font-weight:700;">${cat.name}</span> (${memberText})
      </div>
    `, {
      direction: 'top',
      offset: [0, -14],
      className: 'custom-clean-tooltip',
      opacity: 0.95
    });

    // 클릭 시 상세 정보 열기 콜백 실행
    marker.on('click', () => {
      if (onSelectTerritory) {
        onSelectTerritory(item);
      }
      mapInstance.flyTo([item.lat, item.lng], Math.max(mapInstance.getZoom(), 6), {
        duration: 1.2
      });
    });

    marker.addTo(mapInstance);
    currentMarkers.push(marker);
  });
}

/**
 * 지파 필터 변경
 */
export function setTribeFilter(tribeId, onSelectTerritory) {
  selectedTribeId = tribeId;
  renderMarkers(onSelectTerritory);

  // 특정 지파 선택 시 해당 지파의 첫 번째 도시로 부드럽게 이동
  if (tribeId !== null) {
    const target = allTerritories.find(t => t.tribeId === tribeId);
    if (target && mapInstance) {
      mapInstance.flyTo([target.lat, target.lng], 5, { duration: 1.2 });
    }
  }
}

/**
 * 등급(교회/지역/개척지) 필터 변경
 */
export function setCategoryFilter(categoryKey, onSelectTerritory) {
  selectedCategory = categoryKey;
  renderMarkers(onSelectTerritory);
}

/**
 * 검색어 필터 적용
 */
export function setSearchFilter(query, onSelectTerritory) {
  searchQuery = query;
  renderMarkers(onSelectTerritory);

  // 검색 결과가 1건일 경우 해당 위치로 포커스
  if (query.trim() !== '') {
    const matched = allTerritories.filter(t => 
      t.country.toLowerCase().includes(query.toLowerCase()) ||
      t.city.toLowerCase().includes(query.toLowerCase())
    );
    if (matched.length === 1 && mapInstance) {
      mapInstance.flyTo([matched[0].lat, matched[0].lng], 7, { duration: 1.2 });
    }
  }
}

/**
 * 신규 지경 데이터 추가
 */
export function addTerritoryData(newTerritory, onSelectTerritory) {
  allTerritories.unshift(newTerritory);
  renderMarkers(onSelectTerritory);
  if (mapInstance) {
    mapInstance.flyTo([newTerritory.lat, newTerritory.lng], 7, { duration: 1.2 });
  }
}

/**
 * 기존 지경 데이터 수정
 */
export function updateTerritoryData(updatedTerritory, onSelectTerritory) {
  const index = allTerritories.findIndex(t => t.id === updatedTerritory.id);
  if (index !== -1) {
    allTerritories[index] = { ...updatedTerritory };
    renderMarkers(onSelectTerritory);
  }
}

/**
 * 지경 데이터 삭제
 */
export function deleteTerritoryData(id, onSelectTerritory) {
  allTerritories = allTerritories.filter(t => t.id !== id);
  renderMarkers(onSelectTerritory);
}

/**
 * 전체 지경 데이터 반환 (통계 산출용)
 */
export function getTerritories() {
  return allTerritories;
}
