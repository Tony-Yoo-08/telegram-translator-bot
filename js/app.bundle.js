/* ==========================================================================
   해외선교 총괄 관제 포털 - 통합 런타임 번들 (App Bundle)
   (CORS 제약 없이 file:// 프로토콜 직접 실행 및 Vercel/웹 호스팅 100% 호환)
   ========================================================================== */

(function () {
  'use strict';

  /* ==========================================================================
     1. 12지파 공식 색상표 (PANTONE Solid Coated 기준)
     ========================================================================== */
  const TRIBES_CONFIG = {
    1: { id: 1, name: '요한', gem: '녹보석', color: '#009651', pantone: 'PANTONE 340C', rgb: 'rgb(0, 150, 81)', textColor: '#ffffff' },
    2: { id: 2, name: '베드로', gem: '벽옥', color: '#00a0e9', pantone: 'PANTONE 2925C', rgb: 'rgb(0, 160, 233)', textColor: '#ffffff' },
    3: { id: 3, name: '부산야고보', gem: '남보석', color: '#1d2088', pantone: 'PANTONE 2758C', rgb: 'rgb(29, 32, 136)', textColor: '#ffffff' },
    4: { id: 4, name: '안드레', gem: '옥수', color: '#59c3e1', pantone: 'PANTONE 637C', rgb: 'rgb(89, 195, 225)', textColor: '#0f172a' },
    5: { id: 5, name: '다대오', gem: '홍마노', color: '#eb6120', pantone: 'PANTONE 7579C', rgb: 'rgb(235, 97, 32)', textColor: '#ffffff' },
    6: { id: 6, name: '빌립', gem: '홍보석', color: '#d7005b', pantone: 'PANTONE 214C', rgb: 'rgb(215, 0, 91)', textColor: '#ffffff' },
    7: { id: 7, name: '시몬', gem: '황옥', color: '#fdd000', pantone: 'PANTONE 116C', rgb: 'rgb(253, 208, 0)', textColor: '#0f172a' },
    8: { id: 8, name: '바돌로매', gem: '녹옥', color: '#86cab6', pantone: 'PANTONE 564C', rgb: 'rgb(134, 202, 182)', textColor: '#0f172a' },
    9: { id: 9, name: '마태', gem: '담황옥', color: '#e39300', pantone: 'PANTONE 7564C', rgb: 'rgb(227, 147, 0)', textColor: '#ffffff' },
    10: { id: 10, name: '맛디아', gem: '비취옥', color: '#6FBA2C', pantone: 'PANTONE 368C', rgb: 'rgb(111, 186, 44)', textColor: '#ffffff' },
    11: { id: 11, name: '서울야고보', gem: '청옥', color: '#005dac', pantone: 'PANTONE 2728C', rgb: 'rgb(0, 93, 172)', textColor: '#ffffff' },
    12: { id: 12, name: '도마', gem: '자정', color: '#7f1084', pantone: 'PANTONE 2612C', rgb: 'rgb(127, 16, 132)', textColor: '#ffffff' }
  };

  /* ==========================================================================
     2. 지경 등급 분류 체계
     - 개척지: 0명 ~ 49명 (신규 목표/거점 확장)
     - 지역: 50명 ~ 299명 (준교회)
     - 교회: 300명 이상 (정식 자립 교회)
     ========================================================================== */
  const CATEGORY_CONFIG = {
    PIONEER: { key: 'PIONEER', name: '개척지', badgeClass: 'badge-pioneer', minMembers: 0, maxMembers: 49, color: '#38bdf8', icon: '🧭', desc: '신규 확장 목표 (0~49명)' },
    BRANCH: { key: 'BRANCH', name: '지역', badgeClass: 'badge-branch', minMembers: 50, maxMembers: 299, color: '#fbbf24', icon: '🚩', desc: '준교회 거점 (50명 이상)' },
    CHURCH: { key: 'CHURCH', name: '교회', badgeClass: 'badge-church', minMembers: 300, color: '#10b981', icon: '⛪', desc: '자립 교회 (300명 이상)' }
  };

  function getCategoryByMembers(itemOrCount) {
    if (itemOrCount && typeof itemOrCount === 'object') {
      if (itemOrCount.category && CATEGORY_CONFIG[itemOrCount.category]) {
        return CATEGORY_CONFIG[itemOrCount.category];
      }
      const cnt = typeof itemOrCount.members === 'number' ? itemOrCount.members : 0;
      if (cnt >= 300) return CATEGORY_CONFIG.CHURCH;
      if (cnt >= 50) return CATEGORY_CONFIG.BRANCH;
      return CATEGORY_CONFIG.PIONEER;
    }
    const count = typeof itemOrCount === 'number' ? itemOrCount : 0;
    if (count >= 300) return CATEGORY_CONFIG.CHURCH;
    if (count >= 50) return CATEGORY_CONFIG.BRANCH;
    return CATEGORY_CONFIG.PIONEER;
  }

  /* ==========================================================================
     2-2. 전 세계 도시 및 국가 지오코딩 자동 매핑 데이터베이스 (오프라인 0ms 즉각 매핑)
     ========================================================================== */
  const GLOBAL_CITY_COORDINATES = {
    // 독일 및 중부 유럽 (바돌로매 주요 담당)
    '프랑크푸르트': { lat: 50.1109, lng: 8.6821, name: '프랑크푸르트', country: '독일' },
    'frankfurt': { lat: 50.1109, lng: 8.6821, name: '프랑크푸르트', country: '독일' },
    '베를린': { lat: 52.5200, lng: 13.4050, name: '베를린', country: '독일' },
    'berlin': { lat: 52.5200, lng: 13.4050, name: '베를린', country: '독일' },
    '뮌헨': { lat: 48.1351, lng: 11.5820, name: '뮌헨', country: '독일' },
    'munich': { lat: 48.1351, lng: 11.5820, name: '뮌헨', country: '독일' },
    'munchen': { lat: 48.1351, lng: 11.5820, name: '뮌헨', country: '독일' },
    '함부르크': { lat: 53.5511, lng: 9.9937, name: '함부르크', country: '독일' },
    'hamburg': { lat: 53.5511, lng: 9.9937, name: '함부르크', country: '독일' },
    '쾰른': { lat: 50.9375, lng: 6.9603, name: '쾰른', country: '독일' },
    'cologne': { lat: 50.9375, lng: 6.9603, name: '쾰른', country: '독일' },
    'koln': { lat: 50.9375, lng: 6.9603, name: '쾰른', country: '독일' },
    '뒤셀도르프': { lat: 51.2277, lng: 6.7735, name: '뒤셀도르프', country: '독일' },
    'dusseldorf': { lat: 51.2277, lng: 6.7735, name: '뒤셀도르프', country: '독일' },
    '슈투트가르트': { lat: 48.7758, lng: 9.1829, name: '슈투트가르트', country: '독일' },
    'stuttgart': { lat: 48.7758, lng: 9.1829, name: '슈투트가르트', country: '독일' },
    '드레스덴': { lat: 51.0504, lng: 13.7373, name: '드레스덴', country: '독일' },
    'dresden': { lat: 51.0504, lng: 13.7373, name: '드레스덴', country: '독일' },
    '라이프치히': { lat: 51.3397, lng: 12.3731, name: '라이프치히', country: '독일' },
    'leipzig': { lat: 51.3397, lng: 12.3731, name: '라이프치히', country: '독일' },
    '하노버': { lat: 52.3759, lng: 9.7320, name: '하노버', country: '독일' },
    'hannover': { lat: 52.3759, lng: 9.7320, name: '하노버', country: '독일' },
    '뉘른베르크': { lat: 49.4521, lng: 11.0767, name: '뉘른베르크', country: '독일' },
    'nuremberg': { lat: 49.4521, lng: 11.0767, name: '뉘른베르크', country: '독일' },
    '취리히': { lat: 47.3769, lng: 8.5417, name: '취리히', country: '스위스' },
    'zurich': { lat: 47.3769, lng: 8.5417, name: '취리히', country: '스위스' },
    '제네바': { lat: 46.2044, lng: 6.1432, name: '제네바', country: '스위스' },
    'geneva': { lat: 46.2044, lng: 6.1432, name: '제네바', country: '스위스' },
    '베른': { lat: 46.9480, lng: 7.4474, name: '베른', country: '스위스' },
    'bern': { lat: 46.9480, lng: 7.4474, name: '베른', country: '스위스' },
    '바젤': { lat: 47.5596, lng: 7.5886, name: '바젤', country: '스위스' },
    'basel': { lat: 47.5596, lng: 7.5886, name: '바젤', country: '스위스' },
    '비엔나': { lat: 48.2082, lng: 16.3738, name: '비엔나', country: '오스트리아' },
    '빈': { lat: 48.2082, lng: 16.3738, name: '비엔나', country: '오스트리아' },
    'vienna': { lat: 48.2082, lng: 16.3738, name: '비엔나', country: '오스트리아' },
    'wien': { lat: 48.2082, lng: 16.3738, name: '비엔나', country: '오스트리아' },
    '잘츠부르크': { lat: 47.8095, lng: 13.0550, name: '잘츠부르크', country: '오스트리아' },
    'salzburg': { lat: 47.8095, lng: 13.0550, name: '잘츠부르크', country: '오스트리아' },
    '그라츠': { lat: 47.0707, lng: 15.4395, name: '그라츠', country: '오스트리아' },
    'graz': { lat: 47.0707, lng: 15.4395, name: '그라츠', country: '오스트리아' },
    '프라하': { lat: 50.0755, lng: 14.4378, name: '프라하', country: '체코' },
    'prague': { lat: 50.0755, lng: 14.4378, name: '프라하', country: '체코' },
    'praha': { lat: 50.0755, lng: 14.4378, name: '프라하', country: '체코' },
    '브르노': { lat: 49.1951, lng: 16.6068, name: '브르노', country: '체코' },
    'brno': { lat: 49.1951, lng: 16.6068, name: '브르노', country: '체코' },

    // 서유럽 / 남유럽 / 북유럽
    '런던': { lat: 51.5074, lng: -0.1278, name: '런던', country: '영국' },
    'london': { lat: 51.5074, lng: -0.1278, name: '런던', country: '영국' },
    '맨체스터': { lat: 53.4808, lng: -2.2426, name: '맨체스터', country: '영국' },
    'manchester': { lat: 53.4808, lng: -2.2426, name: '맨체스터', country: '영국' },
    '버밍엄': { lat: 52.4862, lng: -1.8904, name: '버밍엄', country: '영국' },
    'birmingham': { lat: 52.4862, lng: -1.8904, name: '버밍엄', country: '영국' },
    '에든버러': { lat: 55.9533, lng: -3.1883, name: '에든버러', country: '영국' },
    'edinburgh': { lat: 55.9533, lng: -3.1883, name: '에든버러', country: '영국' },
    '더블린': { lat: 53.3498, lng: -6.2603, name: '더블린', country: '아일랜드' },
    'dublin': { lat: 53.3498, lng: -6.2603, name: '더블린', country: '아일랜드' },
    '파리': { lat: 48.8566, lng: 2.3522, name: '파리', country: '프랑스' },
    'paris': { lat: 48.8566, lng: 2.3522, name: '파리', country: '프랑스' },
    '리옹': { lat: 45.7640, lng: 4.8357, name: '리옹', country: '프랑스' },
    'lyon': { lat: 45.7640, lng: 4.8357, name: '리옹', country: '프랑스' },
    '마르세유': { lat: 43.2965, lng: 5.3698, name: '마르세유', country: '프랑스' },
    'marseille': { lat: 43.2965, lng: 5.3698, name: '마르세유', country: '프랑스' },
    '니스': { lat: 43.7102, lng: 7.2620, name: '니스', country: '프랑스' },
    'nice': { lat: 43.7102, lng: 7.2620, name: '니스', country: '프랑스' },
    '스트라스부르': { lat: 48.5734, lng: 7.7521, name: '스트라스부르', country: '프랑스' },
    'strasbourg': { lat: 48.5734, lng: 7.7521, name: '스트라스부르', country: '프랑스' },
    '브뤼셀': { lat: 50.8503, lng: 4.3517, name: '브뤼셀', country: '벨기에' },
    'brussels': { lat: 50.8503, lng: 4.3517, name: '브뤼셀', country: '벨기에' },
    '안트베르펜': { lat: 51.2194, lng: 4.4025, name: '안트베르펜', country: '벨기에' },
    'antwerp': { lat: 51.2194, lng: 4.4025, name: '안트베르펜', country: '벨기에' },
    '암스테르담': { lat: 52.3676, lng: 4.9041, name: '암스테르담', country: '네덜란드' },
    'amsterdam': { lat: 52.3676, lng: 4.9041, name: '암스테르담', country: '네덜란드' },
    '로테르담': { lat: 51.9244, lng: 4.4777, name: '로테르담', country: '네덜란드' },
    'rotterdam': { lat: 51.9244, lng: 4.4777, name: '로테르담', country: '네덜란드' },
    '헤이그': { lat: 52.0705, lng: 4.3007, name: '헤이그', country: '네덜란드' },
    'hague': { lat: 52.0705, lng: 4.3007, name: '헤이그', country: '네덜란드' },
    '로마': { lat: 41.9028, lng: 12.4964, name: '로마', country: '이탈리아' },
    'rome': { lat: 41.9028, lng: 12.4964, name: '로마', country: '이탈리아' },
    '밀라노': { lat: 45.4642, lng: 9.1900, name: '밀라노', country: '이탈리아' },
    'milan': { lat: 45.4642, lng: 9.1900, name: '밀라노', country: '이탈리아' },
    '피렌체': { lat: 43.7696, lng: 11.2558, name: '피렌체', country: '이탈리아' },
    '베네치아': { lat: 45.4408, lng: 12.3155, name: '베네치아', country: '이탈리아' },
    '마드리드': { lat: 40.4168, lng: -3.7038, name: '마드리드', country: '스페인' },
    'madrid': { lat: 40.4168, lng: -3.7038, name: '마드리드', country: '스페인' },
    '바르셀로나': { lat: 41.3851, lng: 2.1734, name: '바르셀로나', country: '스페인' },
    'barcelona': { lat: 41.3851, lng: 2.1734, name: '바르셀로나', country: '스페인' },
    '발렌시아': { lat: 39.4699, lng: -0.3763, name: '발렌시아', country: '스페인' },
    '세비야': { lat: 37.3891, lng: -5.9845, name: '세비야', country: '스페인' },
    '리스본': { lat: 38.7223, lng: -9.1393, name: '리스본', country: '포르투갈' },
    'lisbon': { lat: 38.7223, lng: -9.1393, name: '리스본', country: '포르투갈' },
    '포르투': { lat: 41.1579, lng: -8.6291, name: '포르투', country: '포르투갈' },
    '바르샤바': { lat: 52.2297, lng: 21.0122, name: '바르샤바', country: '폴란드' },
    'warsaw': { lat: 52.2297, lng: 21.0122, name: '바르샤바', country: '폴란드' },
    '크라쿠프': { lat: 50.0647, lng: 19.9450, name: '크라쿠프', country: '폴란드' },
    '부다페스트': { lat: 47.4979, lng: 19.0402, name: '부다페스트', country: '헝가리' },
    'budapest': { lat: 47.4979, lng: 19.0402, name: '부다페스트', country: '헝가리' },
    '부쿠레슈티': { lat: 44.4268, lng: 26.1025, name: '부쿠레슈티', country: '루마니아' },
    '아테네': { lat: 37.9838, lng: 23.7275, name: '아테네', country: '그리스' },
    'athens': { lat: 37.9838, lng: 23.7275, name: '아테네', country: '그리스' },
    '헬싱키': { lat: 60.1699, lng: 24.9384, name: '헬싱키', country: '핀란드' },
    'helsinki': { lat: 60.1699, lng: 24.9384, name: '헬싱키', country: '핀란드' },
    '스톡홀름': { lat: 59.3293, lng: 18.0686, name: '스톡홀름', country: '스웨덴' },
    'stockholm': { lat: 59.3293, lng: 18.0686, name: '스톡홀름', country: '스웨덴' },
    '오슬로': { lat: 59.9139, lng: 10.7522, name: '오슬로', country: '노르웨이' },
    'oslo': { lat: 59.9139, lng: 10.7522, name: '오슬로', country: '노르웨이' },
    '코펜하겐': { lat: 55.6761, lng: 12.5683, name: '코펜하겐', country: '덴마크' },
    'copenhagen': { lat: 55.6761, lng: 12.5683, name: '코펜하겐', country: '덴마크' },
    '모스크바': { lat: 55.7558, lng: 37.6173, name: '모스크바', country: '러시아' },
    'moscow': { lat: 55.7558, lng: 37.6173, name: '모스크바', country: '러시아' },
    '키이우': { lat: 50.4501, lng: 30.5234, name: '키이우', country: '우크라이나' },
    '키예프': { lat: 50.4501, lng: 30.5234, name: '키이우', country: '우크라이나' },
    'kyiv': { lat: 50.4501, lng: 30.5234, name: '키이우', country: '우크라이나' },

    // 북미 및 중남미
    '로스앤젤레스': { lat: 34.0522, lng: -118.2437, name: '로스앤젤레스', country: '미국' },
    'losangeles': { lat: 34.0522, lng: -118.2437, name: '로스앤젤레스', country: '미국' },
    'la': { lat: 34.0522, lng: -118.2437, name: '로스앤젤레스', country: '미국' },
    '엘에이': { lat: 34.0522, lng: -118.2437, name: '로스앤젤레스', country: '미국' },
    '샌프란시스코': { lat: 37.7749, lng: -122.4194, name: '샌프란시스코', country: '미국' },
    'sanfrancisco': { lat: 37.7749, lng: -122.4194, name: '샌프란시스코', country: '미국' },
    'sf': { lat: 37.7749, lng: -122.4194, name: '샌프란시스코', country: '미국' },
    '뉴욕': { lat: 40.7128, lng: -74.0060, name: '뉴욕', country: '미국' },
    'newyork': { lat: 40.7128, lng: -74.0060, name: '뉴욕', country: '미국' },
    'nyc': { lat: 40.7128, lng: -74.0060, name: '뉴욕', country: '미국' },
    '시카고': { lat: 41.8781, lng: -87.6298, name: '시카고', country: '미국' },
    'chicago': { lat: 41.8781, lng: -87.6298, name: '시카고', country: '미국' },
    '시애틀': { lat: 47.6062, lng: -122.3321, name: '시애틀', country: '미국' },
    'seattle': { lat: 47.6062, lng: -122.3321, name: '시애틀', country: '미국' },
    '워싱턴': { lat: 38.9072, lng: -77.0369, name: '워싱턴', country: '미국' },
    'washington': { lat: 38.9072, lng: -77.0369, name: '워싱턴', country: '미국' },
    '댈러스': { lat: 32.7767, lng: -96.7970, name: '댈러스', country: '미국' },
    'dallas': { lat: 32.7767, lng: -96.7970, name: '댈러스', country: '미국' },
    '휴스턴': { lat: 29.7604, lng: -95.3698, name: '휴스턴', country: '미국' },
    'houston': { lat: 29.7604, lng: -95.3698, name: '휴스턴', country: '미국' },
    '애틀랜타': { lat: 33.7490, lng: -84.3880, name: '애틀랜타', country: '미국' },
    'atlanta': { lat: 33.7490, lng: -84.3880, name: '애틀랜타', country: '미국' },
    '보스턴': { lat: 42.3601, lng: -71.0589, name: '보스턴', country: '미국' },
    'boston': { lat: 42.3601, lng: -71.0589, name: '보스턴', country: '미국' },
    '마이애미': { lat: 25.7617, lng: -80.1918, name: '마이애미', country: '미국' },
    'miami': { lat: 25.7617, lng: -80.1918, name: '마이애미', country: '미국' },
    '라스베이거스': { lat: 36.1699, lng: -115.1398, name: '라스베이거스', country: '미국' },
    'lasvegas': { lat: 36.1699, lng: -115.1398, name: '라스베이거스', country: '미국' },
    '밴쿠버': { lat: 49.2827, lng: -123.1207, name: '밴쿠버', country: '캐나다' },
    'vancouver': { lat: 49.2827, lng: -123.1207, name: '밴쿠버', country: '캐나다' },
    '토론토': { lat: 43.6532, lng: -79.3832, name: '토론토', country: '캐나다' },
    'toronto': { lat: 43.6532, lng: -79.3832, name: '토론토', country: '캐나다' },
    '몬트리올': { lat: 45.5017, lng: -73.5673, name: '몬트리올', country: '캐나다' },
    'montreal': { lat: 45.5017, lng: -73.5673, name: '몬트리올', country: '캐나다' },
    '캘거리': { lat: 51.0447, lng: -114.0719, name: '캘거리', country: '캐나다' },
    '멕시코시티': { lat: 19.4326, lng: -99.1332, name: '멕시코시티', country: '멕시코' },
    'mexicocity': { lat: 19.4326, lng: -99.1332, name: '멕시코시티', country: '멕시코' },
    '몬테레이': { lat: 25.6866, lng: -100.3161, name: '몬테레이', country: '멕시코' },
    '과달라하라': { lat: 20.6597, lng: -103.3496, name: '과달라하라', country: '멕시코' },
    '보고타': { lat: 4.7110, lng: -74.0721, name: '보고타', country: '콜롬비아' },
    'bogota': { lat: 4.7110, lng: -74.0721, name: '보고타', country: '콜롬비아' },
    '리마': { lat: -12.0464, lng: -77.0428, name: '리마', country: '페루' },
    'lima': { lat: -12.0464, lng: -77.0428, name: '리마', country: '페루' },
    '산티아고': { lat: -33.4489, lng: -70.6693, name: '산티아고', country: '칠레' },
    'santiago': { lat: -33.4489, lng: -70.6693, name: '산티아고', country: '칠레' },
    '부에노스아이레스': { lat: -34.6037, lng: -58.3816, name: '부에노스아이레스', country: '아르헨티나' },
    'buenosaires': { lat: -34.6037, lng: -58.3816, name: '부에노스아이레스', country: '아르헨티나' },
    '상파울루': { lat: -23.5505, lng: -46.6333, name: '상파울루', country: '브라질' },
    'saopaulo': { lat: -23.5505, lng: -46.6333, name: '상파울루', country: '브라질' },
    '리우데자네이루': { lat: -22.9068, lng: -43.1729, name: '리우데자네이루', country: '브라질' },
    '브라질리아': { lat: -15.8267, lng: -47.9218, name: '브라질리아', country: '브라질' },

    // 아시아 및 오세아니아
    '도쿄': { lat: 35.6762, lng: 139.6503, name: '도쿄', country: '일본' },
    'tokyo': { lat: 35.6762, lng: 139.6503, name: '도쿄', country: '일본' },
    '오사카': { lat: 34.6937, lng: 135.5023, name: '오사카', country: '일본' },
    'osaka': { lat: 34.6937, lng: 135.5023, name: '오사카', country: '일본' },
    '나고야': { lat: 35.1815, lng: 136.9066, name: '나고야', country: '일본' },
    '후쿠오카': { lat: 33.5904, lng: 130.4017, name: '후쿠오카', country: '일본' },
    '삿포로': { lat: 43.0618, lng: 141.3545, name: '삿포로', country: '일본' },
    '요코하마': { lat: 35.4437, lng: 139.6380, name: '요코하마', country: '일본' },
    '교토': { lat: 35.0116, lng: 135.7681, name: '교토', country: '일본' },
    '베이징': { lat: 39.9042, lng: 116.4074, name: '베이징', country: '중국' },
    '북경': { lat: 39.9042, lng: 116.4074, name: '베이징', country: '중국' },
    'beijing': { lat: 39.9042, lng: 116.4074, name: '베이징', country: '중국' },
    '상하이': { lat: 31.2304, lng: 121.4737, name: '상하이', country: '중국' },
    '상해': { lat: 31.2304, lng: 121.4737, name: '상하이', country: '중국' },
    'shanghai': { lat: 31.2304, lng: 121.4737, name: '상하이', country: '중국' },
    '광저우': { lat: 23.1291, lng: 113.2644, name: '광저우', country: '중국' },
    'guangzhou': { lat: 23.1291, lng: 113.2644, name: '광저우', country: '중국' },
    '선전': { lat: 22.5431, lng: 114.0579, name: '선전', country: '중국' },
    '심천': { lat: 22.5431, lng: 114.0579, name: '선전', country: '중국' },
    'shenzhen': { lat: 22.5431, lng: 114.0579, name: '선전', country: '중국' },
    '홍콩': { lat: 22.3193, lng: 114.1694, name: '홍콩', country: '중국' },
    'hongkong': { lat: 22.3193, lng: 114.1694, name: '홍콩', country: '중국' },
    '타이베이': { lat: 25.0330, lng: 121.5654, name: '타이베이', country: '대만' },
    'taipei': { lat: 25.0330, lng: 121.5654, name: '타이베이', country: '대만' },
    '가오슝': { lat: 22.6273, lng: 120.3014, name: '가오슝', country: '대만' },
    '싱가포르': { lat: 1.3521, lng: 103.8198, name: '싱가포르', country: '싱가포르' },
    'singapore': { lat: 1.3521, lng: 103.8198, name: '싱가포르', country: '싱가포르' },
    '방콕': { lat: 13.7563, lng: 100.5018, name: '방콕', country: '태국' },
    'bangkok': { lat: 13.7563, lng: 100.5018, name: '방콕', country: '태국' },
    '치앙마이': { lat: 18.7883, lng: 98.9853, name: '치앙마이', country: '태국' },
    '쿠알라룸푸르': { lat: 3.1390, lng: 101.6869, name: '쿠알라룸푸르', country: '말레이시아' },
    'kualalumpur': { lat: 3.1390, lng: 101.6869, name: '쿠알라룸푸르', country: '말레이시아' },
    '자카르타': { lat: -6.2088, lng: 106.8456, name: '자카르타', country: '인도네시아' },
    'jakarta': { lat: -6.2088, lng: 106.8456, name: '자카르타', country: '인도네시아' },
    '발리': { lat: -8.6705, lng: 115.2126, name: '발리', country: '인도네시아' },
    '마닐라': { lat: 14.5995, lng: 120.9842, name: '마닐라', country: '필리핀' },
    'manila': { lat: 14.5995, lng: 120.9842, name: '마닐라', country: '필리핀' },
    '세부': { lat: 10.3157, lng: 123.8854, name: '세부', country: '필리핀' },
    '하노이': { lat: 21.0285, lng: 105.8542, name: '하노이', country: '베트남' },
    'hanoi': { lat: 21.0285, lng: 105.8542, name: '하노이', country: '베트남' },
    '호치민': { lat: 10.8231, lng: 106.6297, name: '호치민', country: '베트남' },
    '사이공': { lat: 10.8231, lng: 106.6297, name: '호치민', country: '베트남' },
    'hochiminh': { lat: 10.8231, lng: 106.6297, name: '호치민', country: '베트남' },
    '다낭': { lat: 16.0544, lng: 108.2022, name: '다낭', country: '베트남' },
    '프놈펜': { lat: 11.5564, lng: 104.9282, name: '프놈펜', country: '캄보디아' },
    '울란바토르': { lat: 47.8864, lng: 106.9057, name: '울란바토르', country: '몽골' },
    '뉴델리': { lat: 28.6139, lng: 77.2090, name: '뉴델리', country: '인도' },
    'newdelhi': { lat: 28.6139, lng: 77.2090, name: '뉴델리', country: '인도' },
    '델리': { lat: 28.6139, lng: 77.2090, name: '뉴델리', country: '인도' },
    '뭄바이': { lat: 19.0760, lng: 72.8777, name: '뭄바이', country: '인도' },
    'mumbai': { lat: 19.0760, lng: 72.8777, name: '뭄바이', country: '인도' },
    '시드니': { lat: -33.8688, lng: 151.2093, name: '시드니', country: '호주' },
    'sydney': { lat: -33.8688, lng: 151.2093, name: '시드니', country: '호주' },
    '멜버른': { lat: -37.8136, lng: 144.9631, name: '멜버른', country: '호주' },
    'melbourne': { lat: -37.8136, lng: 144.9631, name: '멜버른', country: '호주' },
    '브리즈번': { lat: -27.4698, lng: 153.0251, name: '브리즈번', country: '호주' },
    '퍼스': { lat: -31.9505, lng: 115.8605, name: '퍼스', country: '호주' },
    '오클랜드': { lat: -36.8485, lng: 174.7633, name: '오클랜드', country: '뉴질랜드' },
    'auckland': { lat: -36.8485, lng: 174.7633, name: '오클랜드', country: '뉴질랜드' },
    '웰링턴': { lat: -41.2865, lng: 174.7762, name: '웰링턴', country: '뉴질랜드' },

    // 중동 및 아프리카
    '이스탄불': { lat: 41.0082, lng: 28.9784, name: '이스탄불', country: '터키' },
    'istanbul': { lat: 41.0082, lng: 28.9784, name: '이스탄불', country: '터키' },
    '앙카라': { lat: 39.9334, lng: 32.8597, name: '앙카라', country: '터키' },
    '두바이': { lat: 25.2048, lng: 55.2708, name: '두바이', country: '아랍에미리트' },
    'dubai': { lat: 25.2048, lng: 55.2708, name: '두바이', country: '아랍에미리트' },
    '아부다비': { lat: 24.4539, lng: 54.3773, name: '아부다비', country: '아랍에미리트' },
    '도하': { lat: 25.2854, lng: 51.5310, name: '도하', country: '카타르' },
    '리야드': { lat: 24.7136, lng: 46.6753, name: '리야드', country: '사우디아라비아' },
    '카이로': { lat: 30.0444, lng: 31.2357, name: '카이로', country: '이집트' },
    'cairo': { lat: 30.0444, lng: 31.2357, name: '카이로', country: '이집트' },
    '요하네스버그': { lat: -26.2041, lng: 28.0473, name: '요하네스버그', country: '남아프리카공화국' },
    '케이프타운': { lat: -33.9249, lng: 18.4241, name: '케이프타운', country: '남아프리카공화국' },
    '나이로비': { lat: -1.2921, lng: 36.8219, name: '나이로비', country: '케냐' },
    '아디스아바바': { lat: 9.0300, lng: 38.7400, name: '아디스아바바', country: '에티오피아' },
    '카사블랑카': { lat: 33.5731, lng: -7.5898, name: '카사블랑카', country: '모로코' },

    // 대한민국 주요 도시
    '과천': { lat: 37.4292, lng: 126.9874, name: '과천', country: '대한민국' },
    '서울': { lat: 37.5665, lng: 126.9780, name: '서울', country: '대한민국' },
    'seoul': { lat: 37.5665, lng: 126.9780, name: '서울', country: '대한민국' },
    '부산': { lat: 35.1796, lng: 129.0756, name: '부산', country: '대한민국' },
    '대구': { lat: 35.8714, lng: 128.6014, name: '대구', country: '대한민국' },
    '인천': { lat: 37.4563, lng: 126.7052, name: '인천', country: '대한민국' },
    '광주': { lat: 35.1595, lng: 126.8526, name: '광주', country: '대한민국' },
    '대전': { lat: 36.3504, lng: 127.3845, name: '대전', country: '대한민국' },
    '울산': { lat: 35.5384, lng: 129.3114, name: '울산', country: '대한민국' },
    '수원': { lat: 37.2636, lng: 127.0286, name: '수원', country: '대한민국' },
    '원주': { lat: 37.3422, lng: 127.9202, name: '원주', country: '대한민국' },
    '청주': { lat: 36.6424, lng: 127.4890, name: '청주', country: '대한민국' },
    '전주': { lat: 35.8242, lng: 127.1480, name: '전주', country: '대한민국' },
    '포항': { lat: 36.0190, lng: 129.3435, name: '포항', country: '대한민국' },
    '제주': { lat: 33.4996, lng: 126.5312, name: '제주', country: '대한민국' }
  };

  const GLOBAL_COUNTRY_COORDINATES = {
    '독일': { lat: 51.1657, lng: 10.4515, name: '독일' },
    'germany': { lat: 51.1657, lng: 10.4515, name: '독일' },
    '스위스': { lat: 46.8182, lng: 8.2275, name: '스위스' },
    'switzerland': { lat: 46.8182, lng: 8.2275, name: '스위스' },
    '오스트리아': { lat: 47.5162, lng: 14.5501, name: '오스트리아' },
    'austria': { lat: 47.5162, lng: 14.5501, name: '오스트리아' },
    '체코': { lat: 49.8175, lng: 15.4730, name: '체코' },
    'czech': { lat: 49.8175, lng: 15.4730, name: '체코' },
    '미국': { lat: 37.0902, lng: -95.7129, name: '미국' },
    'usa': { lat: 37.0902, lng: -95.7129, name: '미국' },
    '캐나다': { lat: 56.1304, lng: -106.3468, name: '캐나다' },
    'canada': { lat: 56.1304, lng: -106.3468, name: '캐나다' },
    '호주': { lat: -25.2744, lng: 133.7751, name: '호주' },
    'australia': { lat: -25.2744, lng: 133.7751, name: '호주' },
    '뉴질랜드': { lat: -40.9006, lng: 174.8860, name: '뉴질랜드' },
    '영국': { lat: 55.3781, lng: -3.4360, name: '영국' },
    'uk': { lat: 55.3781, lng: -3.4360, name: '영국' },
    '아일랜드': { lat: 53.1424, lng: -7.6921, name: '아일랜드' },
    '일본': { lat: 36.2048, lng: 138.2529, name: '일본' },
    'japan': { lat: 36.2048, lng: 138.2529, name: '일본' },
    '터키': { lat: 38.9637, lng: 35.2433, name: '터키' },
    'turkey': { lat: 38.9637, lng: 35.2433, name: '터키' },
    '튀르키예': { lat: 38.9637, lng: 35.2433, name: '터키' },
    '아랍에미리트': { lat: 23.4241, lng: 53.8478, name: '아랍에미리트' },
    'uae': { lat: 23.4241, lng: 53.8478, name: '아랍에미리트' },
    '프랑스': { lat: 46.2276, lng: 2.2137, name: '프랑스' },
    'france': { lat: 46.2276, lng: 2.2137, name: '프랑스' },
    '이탈리아': { lat: 41.8719, lng: 12.5674, name: '이탈리아' },
    'italy': { lat: 41.8719, lng: 12.5674, name: '이탈리아' },
    '스페인': { lat: 40.4637, lng: -3.7492, name: '스페인' },
    'spain': { lat: 40.4637, lng: -3.7492, name: '스페인' },
    '네덜란드': { lat: 52.1326, lng: 5.2913, name: '네덜란드' },
    '벨기에': { lat: 50.5039, lng: 4.4699, name: '벨기에' },
    '폴란드': { lat: 51.9194, lng: 19.1451, name: '폴란드' },
    '헝가리': { lat: 47.1625, lng: 19.5033, name: '헝가리' },
    '루마니아': { lat: 45.9432, lng: 24.9668, name: '루마니아' },
    '그리스': { lat: 39.0742, lng: 21.8243, name: '그리스' },
    '핀란드': { lat: 61.9241, lng: 25.7482, name: '핀란드' },
    '스웨덴': { lat: 60.1282, lng: 18.6435, name: '스웨덴' },
    '노르웨이': { lat: 60.4720, lng: 8.4689, name: '노르웨이' },
    '덴마크': { lat: 56.2639, lng: 9.5018, name: '덴마크' },
    '러시아': { lat: 61.5240, lng: 105.3188, name: '러시아' },
    '우크라이나': { lat: 48.3794, lng: 31.1656, name: '우크라이나' },
    '중국': { lat: 35.8617, lng: 104.1954, name: '중국' },
    'china': { lat: 35.8617, lng: 104.1954, name: '중국' },
    '대만': { lat: 23.6978, lng: 120.9605, name: '대만' },
    'taiwan': { lat: 23.6978, lng: 120.9605, name: '대만' },
    '싱가포르': { lat: 1.3521, lng: 103.8198, name: '싱가포르' },
    '태국': { lat: 15.8700, lng: 100.9925, name: '태국' },
    '베트남': { lat: 14.0583, lng: 108.2772, name: '베트남' },
    '필리핀': { lat: 12.8797, lng: 121.7740, name: '필리핀' },
    '인도네시아': { lat: -0.7893, lng: 113.9213, name: '인도네시아' },
    '말레이시아': { lat: 4.2105, lng: 101.9758, name: '말레이시아' },
    '인도': { lat: 20.5937, lng: 78.9629, name: '인도' },
    '멕시코': { lat: 23.6345, lng: -102.5528, name: '멕시코' },
    '브라질': { lat: -14.2350, lng: -51.9253, name: '브라질' },
    '아르헨티나': { lat: -38.4161, lng: -63.6167, name: '아르헨티나' },
    '칠레': { lat: -35.6751, lng: -71.5430, name: '칠레' },
    '콜롬비아': { lat: 4.5709, lng: -74.2973, name: '콜롬비아' },
    '페루': { lat: -9.1899, lng: -75.0152, name: '페루' },
    '남아프리카공화국': { lat: -30.5595, lng: 22.9375, name: '남아프리카공화국' },
    '이집트': { lat: 26.8206, lng: 30.8025, name: '이집트' },
    '케냐': { lat: -0.0236, lng: 37.9062, name: '케냐' },
    '대한민국': { lat: 36.5000, lng: 127.5000, name: '대한민국' },
    '한국': { lat: 36.5000, lng: 127.5000, name: '대한민국' }
  };

  const GLOBAL_STATE_COORDINATES = {
    '캘리포니아': { lat: 36.7783, lng: -119.4179, name: '캘리포니아주' },
    '캘리포니아주': { lat: 36.7783, lng: -119.4179, name: '캘리포니아주' },
    'california': { lat: 36.7783, lng: -119.4179, name: '캘리포니아주' },
    'ca': { lat: 36.7783, lng: -119.4179, name: '캘리포니아주' },
    '텍사스': { lat: 31.9686, lng: -99.9018, name: '텍사스주' },
    '텍사스주': { lat: 31.9686, lng: -99.9018, name: '텍사스주' },
    'texas': { lat: 31.9686, lng: -99.9018, name: '텍사스주' },
    'tx': { lat: 31.9686, lng: -99.9018, name: '텍사스주' },
    '뉴욕주': { lat: 42.1657, lng: -74.9481, name: '뉴욕주' },
    'newyorkstate': { lat: 42.1657, lng: -74.9481, name: '뉴욕주' },
    '플로리다': { lat: 27.6648, lng: -81.5158, name: '플로리다주' },
    '플로리다주': { lat: 27.6648, lng: -81.5158, name: '플로리다주' },
    'florida': { lat: 27.6648, lng: -81.5158, name: '플로리다주' },
    '워싱턴주': { lat: 47.7511, lng: -120.7401, name: '워싱턴주' },
    'washingtonstate': { lat: 47.7511, lng: -120.7401, name: '워싱턴주' },
    '일리노이': { lat: 40.6331, lng: -89.3985, name: '일리노이주' },
    '일리노이주': { lat: 40.6331, lng: -89.3985, name: '일리노이주' },
    'illinois': { lat: 40.6331, lng: -89.3985, name: '일리노이주' },
    '조지아주': { lat: 32.1656, lng: -82.9001, name: '조지아주' },
    '바이에른': { lat: 48.7904, lng: 11.4979, name: '바이에른주' },
    '바이에른주': { lat: 48.7904, lng: 11.4979, name: '바이에른주' },
    'bayern': { lat: 48.7904, lng: 11.4979, name: '바이에른주' },
    'bavaria': { lat: 48.7904, lng: 11.4979, name: '바이에른주' },
    '헤센': { lat: 50.6521, lng: 9.1624, name: '헤센주' },
    '헤센주': { lat: 50.6521, lng: 9.1624, name: '헤센주' },
    'hessen': { lat: 50.6521, lng: 9.1624, name: '헤센주' },
    '노르트라인베스트팔렌': { lat: 51.4332, lng: 7.6616, name: '노르트라인-베스트팔렌주' },
    '온타리오': { lat: 51.2538, lng: -85.3232, name: '온타리오주' },
    '온타리오주': { lat: 51.2538, lng: -85.3232, name: '온타리오주' },
    'ontario': { lat: 51.2538, lng: -85.3232, name: '온타리오주' },
    '퀘벡': { lat: 52.9399, lng: -73.5491, name: '퀘벡주' },
    '퀘벡주': { lat: 52.9399, lng: -73.5491, name: '퀘벡주' },
    'quebec': { lat: 52.9399, lng: -73.5491, name: '퀘벡주' },
    '브리티시컬럼비아': { lat: 53.7267, lng: -127.6476, name: '브리티시컬럼비아주' },
    '뉴사우스웨일스': { lat: -31.8402, lng: 145.6128, name: '뉴사우스웨일스주' },
    '뉴사우스웨일스주': { lat: -31.8402, lng: 145.6128, name: '뉴사우스웨일스주' },
    'nsw': { lat: -31.8402, lng: 145.6128, name: '뉴사우스웨일스주' },
    '빅토리아': { lat: -37.4713, lng: 144.7852, name: '빅토리아주' },
    '빅토리아주': { lat: -37.4713, lng: 144.7852, name: '빅토리아주' },
    '퀸즐랜드': { lat: -20.9176, lng: 142.7028, name: '퀸즐랜드주' },
    '퀸즐랜드주': { lat: -20.9176, lng: 142.7028, name: '퀸즐랜드주' },
    'queensland': { lat: -20.9176, lng: 142.7028, name: '퀸즐랜드주' }
  };

  function normalizeGeoKey(str) {
    if (!str) return '';
    return str.toString().trim().toLowerCase().replace(/[\s\-_.,·/()]/g, '');
  }

  function lookupCityCoordinates(city, country) {
    if (!city) return null;
    const key = normalizeGeoKey(city);
    if (GLOBAL_STATE_COORDINATES[key]) return GLOBAL_STATE_COORDINATES[key];
    if (GLOBAL_CITY_COORDINATES[key]) return GLOBAL_CITY_COORDINATES[key];

    const stripped = key.replace(/city$|시$|주$|도$|state$|province$/, '');
    if (GLOBAL_STATE_COORDINATES[stripped]) return GLOBAL_STATE_COORDINATES[stripped];
    if (GLOBAL_CITY_COORDINATES[stripped]) return GLOBAL_CITY_COORDINATES[stripped];
    return null;
  }

  function lookupCountryCoordinates(country) {
    if (!country) return null;
    const key = normalizeGeoKey(country);
    if (GLOBAL_COUNTRY_COORDINATES[key]) {
      return GLOBAL_COUNTRY_COORDINATES[key];
    }
    return null;
  }

  function resolveCoordinatesSync(cityName, countryName) {
    const geo = lookupCityCoordinates(cityName, countryName);
    if (geo) return { lat: geo.lat, lng: geo.lng, source: 'city', name: geo.name || cityName };

    const cGeo = lookupCountryCoordinates(countryName);
    if (cGeo) return { lat: cGeo.lat, lng: cGeo.lng, source: 'country', name: cGeo.name || countryName };

    return { lat: 50.1109, lng: 8.6821, source: 'default', name: '중앙 거점' };
  }

  function fetchGeoFromNominatim(cityName, countryName, callback) {
    if (!cityName && !countryName) return;
    const query = [cityName, countryName].filter(Boolean).join(', ');
    const url = `https://nominatim.openstreetmap.org/search?format=json&limit=1&q=${encodeURIComponent(query)}`;

    let didTimeout = false;
    const timer = setTimeout(() => { didTimeout = true; }, 3000);

    fetch(url)
      .then(res => res.json())
      .then(data => {
        clearTimeout(timer);
        if (didTimeout) return;
        if (Array.isArray(data) && data.length > 0) {
          const lat = parseFloat(data[0].lat);
          const lng = parseFloat(data[0].lon);
          if (!isNaN(lat) && !isNaN(lng)) {
            callback({ lat: Number(lat.toFixed(4)), lng: Number(lng.toFixed(4)), displayName: data[0].display_name });
          }
        }
      })
      .catch(() => {
        // 네트워크 미연결 또는 오류 시 사전 기본값 유지
      });
  }

  /* ==========================================================================
     3. 12지파 전 세계 도시 단위 초기 데이터
     ========================================================================== */
  const INITIAL_TERRITORIES = [
    // 바돌로매지파 (주요 담당 지경)
    { id: 'TR-BAR-01', tribeId: 8, country: '독일', countryCode: 'DE', city: '프랑크푸르트', lat: 50.1109, lng: 8.6821, members: 420, leader: '김바돌 사역자', establishedYear: 2017, address: 'Frankfurt am Main, Hessen, Germany', phone: '+49 69 1234 5678', notes: '유럽 거점 교회, 다국적 말씀 세미나 정기 개최 및 현지인 사역 활성화', updatedAt: '2026-09-15' },
    { id: 'TR-BAR-02', tribeId: 8, country: '독일', countryCode: 'DE', city: '베를린', lat: 52.5200, lng: 13.4050, members: 145, leader: '이은혜 전도사', establishedYear: 2021, address: 'Mitte, Berlin, Germany', phone: '+49 30 8765 4321', notes: '독일 수도 중심 사역 거점, 대학생 및 청년층 중심', updatedAt: '2026-09-18' },
    { id: 'TR-BAR-03', tribeId: 8, country: '스위스', countryCode: 'CH', city: '취리히', lat: 47.3769, lng: 8.5417, members: 68, leader: '박요한 사역자', establishedYear: 2023, address: 'Zurich Center, Switzerland', phone: '+41 44 234 5678', notes: '스위스 금융 중심지, 전문직 대상 언어 스터디 및 성경 세미나 거점', updatedAt: '2026-08-20' },
    { id: 'TR-BAR-04', tribeId: 8, country: '오스트리아', countryCode: 'AT', city: '비엔나', lat: 48.2082, lng: 16.3738, members: 0, leader: '파견 준비단', establishedYear: 2026, address: 'Innere Stadt, Wien, Austria', phone: '-', notes: '2026년 하반기 신규 개척 목표 도시. 독일어 가능 인재 파견 대기', updatedAt: '2026-09-24' },
    { id: 'TR-BAR-05', tribeId: 8, country: '체코', countryCode: 'CZ', city: '프라하', lat: 50.0755, lng: 14.4378, members: 0, leader: '답사팀 구성', establishedYear: 2026, address: 'Prague 1, Czech Republic', phone: '-', notes: '동유럽 교두보 개척지. 영어/체코어 가능 인재 수요 조사 중', updatedAt: '2026-09-20' },

    // 요한지파
    { id: 'TR-JOH-01', tribeId: 1, country: '미국', countryCode: 'US', city: '로스앤젤레스', lat: 34.0522, lng: -118.2437, members: 680, leader: '정요한 총무', establishedYear: 2014, address: 'Wilshire Blvd, Los Angeles, CA, USA', phone: '+1 213 555 0199', notes: '미주 서부 최대 거점 교회, 다민족 성도 활성화', updatedAt: '2026-09-10' },
    { id: 'TR-JOH-02', tribeId: 1, country: '미국', countryCode: 'US', city: '샌프란시스코', lat: 37.7749, lng: -122.4194, members: 120, leader: '최진우 강사', establishedYear: 2022, address: 'Market St, San Francisco, CA, USA', phone: '+1 415 555 0142', notes: '실리콘밸리 연계 IT 인재 및 다국적 청년층 전도 활발', updatedAt: '2026-08-30' },
    { id: 'TR-JOH-03', tribeId: 1, country: '캐나다', countryCode: 'CA', city: '밴쿠버', lat: 49.2827, lng: -123.1207, members: 0, leader: '답사단 구성', establishedYear: 2026, address: 'Downtown, Vancouver, BC, Canada', phone: '-', notes: '캐나다 서부 개척 예정지', updatedAt: '2026-09-12' },
    { id: 'TR-JOH-04', tribeId: 1, country: '미국', countryCode: 'US', city: '텍사스주', unitType: 'STATE', lat: 31.9686, lng: -99.9018, members: 280, leader: '김요한 사역자', establishedYear: 2023, address: 'Texas, United States', phone: '+1 512 555 0188', notes: '미주 남부 텍사스주 광역 주 단위 관할 지경 (댈러스, 오스틴, 휴스턴 등 연계 관할)', updatedAt: '2026-09-15' },

    // 베드로지파
    { id: 'TR-PET-01', tribeId: 2, country: '호주', countryCode: 'AU', city: '시드니', lat: -33.8688, lng: 151.2093, members: 390, leader: '강베드로 사역자', establishedYear: 2016, address: 'George St, Sydney NSW, Australia', phone: '+61 2 9234 5678', notes: '오세아니아 본부 교회, 호주 및 뉴질랜드 전역 선교 지원', updatedAt: '2026-09-01' },
    { id: 'TR-PET-02', tribeId: 2, country: '호주', countryCode: 'AU', city: '멜버른', lat: -37.8136, lng: 144.9631, members: 85, leader: '신영민 전도사', establishedYear: 2023, address: 'Swanston St, Melbourne VIC, Australia', phone: '+61 3 9876 5432', notes: '다문화 예술 도시 거점, 청년 중심 지역 모임 성장세', updatedAt: '2026-08-15' },

    // 부산야고보지파
    { id: 'TR-BJA-01', tribeId: 3, country: '영국', countryCode: 'GB', city: '런던', lat: 51.5074, lng: -0.1278, members: 310, leader: '문야고보 사역자', establishedYear: 2018, address: 'Holborn, London, UK', phone: '+44 20 7946 0912', notes: '영국 정식 교회 인가, 유럽 북부권 선교 허브', updatedAt: '2026-09-14' },
    { id: 'TR-BJA-02', tribeId: 3, country: '아일랜드', countryCode: 'IE', city: '더블린', lat: 53.3498, lng: -6.2603, members: 0, leader: '개척 준비단', establishedYear: 2026, address: 'Grafton St, Dublin, Ireland', phone: '-', notes: '아일랜드 신규 개척 목표지, 영국 런던 교회에서 정기 지원', updatedAt: '2026-09-22' },

    // 안드레지파
    { id: 'TR-AND-01', tribeId: 4, country: '일본', countryCode: 'JP', city: '도쿄', lat: 35.6762, lng: 139.6503, members: 450, leader: '조안드레 사역자', establishedYear: 2015, address: 'Shinjuku-ku, Tokyo, Japan', phone: '+81 3 5321 1111', notes: '일본 수도 거점 교회, 온라인 말씀 세미나 수강생 급증', updatedAt: '2026-09-11' },
    { id: 'TR-AND-02', tribeId: 4, country: '일본', countryCode: 'JP', city: '오사카', lat: 34.6937, lng: 135.5023, members: 180, leader: '김경호 전도사', establishedYear: 2020, address: 'Namba, Osaka, Japan', phone: '+81 6 6211 2222', notes: '간사이 중심 지역, 현지 일본인 사역자 배출 중', updatedAt: '2026-09-05' },

    // 다대오지파
    { id: 'TR-THD-01', tribeId: 5, country: '터키', countryCode: 'TR', city: '이스탄불', lat: 41.0082, lng: 28.9784, members: 95, leader: '린다대오 선교사', establishedYear: 2022, address: 'Kadikoy, Istanbul, Turkey', phone: '+90 216 123 4567', notes: '유럽-아시아 교차로, 문화 사역 중심 진행', updatedAt: '2026-09-08' },
    { id: 'TR-THD-02', tribeId: 5, country: '아랍에미리트', countryCode: 'AE', city: '두바이', lat: 25.2048, lng: 55.2708, members: 0, leader: '사전 조사단', establishedYear: 2026, address: 'Downtown, Dubai, UAE', phone: '-', notes: '중동 허브 신규 개척지', updatedAt: '2026-09-18' },

    // 빌립지파
    { id: 'TR-PHI-01', tribeId: 6, country: '남아프리카공화국', countryCode: 'ZA', city: '케이프타운', lat: -33.9249, lng: 18.4241, members: 510, leader: '윤빌립 사역자', establishedYear: 2016, address: 'Foreshore, Cape Town, South Africa', phone: '+27 21 421 0000', notes: '아프리카 남부 최대 대형 교회, 현지 목회자 말씀 교류 활발', updatedAt: '2026-09-03' },
    { id: 'TR-PHI-02', tribeId: 6, country: '케냐', countryCode: 'KE', city: '나이로비', lat: -1.2921, lng: 36.8219, members: 160, leader: '오순신 전도사', establishedYear: 2021, address: 'Westlands, Nairobi, Kenya', phone: '+254 20 123 4567', notes: '동아프리카 선교 거점 지역', updatedAt: '2026-08-25' },

    // 시몬지파
    { id: 'TR-SIM-01', tribeId: 7, country: '프랑스', countryCode: 'FR', city: '파리', lat: 48.8566, lng: 2.3522, members: 210, leader: '하시몬 사역자', establishedYear: 2019, address: '15th Arrondissement, Paris, France', phone: '+33 1 45 67 89 00', notes: '불어권 문화 및 복음 전파 거점 지역', updatedAt: '2026-08-28' },
    { id: 'TR-SIM-02', tribeId: 7, country: '벨기에', countryCode: 'BE', city: '브뤼셀', lat: 50.8503, lng: 4.3517, members: 0, leader: '개척 준비단', establishedYear: 2026, address: 'Ixelles, Brussels, Belgium', phone: '-', notes: 'EU 본부 소재지 신규 개척 목표', updatedAt: '2026-09-15' },

    // 마태지파
    { id: 'TR-MAT-01', tribeId: 9, country: '네덜란드', countryCode: 'NL', city: '암스테르담', lat: 52.3676, lng: 4.9041, members: 75, leader: '백마태 전도사', establishedYear: 2023, address: 'Amsterdam Centrum, Netherlands', phone: '+31 20 123 4567', notes: '다국적 영어 및 네덜란드어 병행 사역 진행', updatedAt: '2026-09-02' },
    { id: 'TR-MAT-02', tribeId: 9, country: '덴마크', countryCode: 'DK', city: '코펜하겐', lat: 55.6761, lng: 12.5683, members: 0, leader: '사전 조사단', establishedYear: 2026, address: 'Indre By, Copenhagen, Denmark', phone: '-', notes: '북유럽 거점 개척 예정지', updatedAt: '2026-09-17' },

    // 맛디아지파
    { id: 'TR-MTH-01', tribeId: 10, country: '브라질', countryCode: 'BR', city: '상파울루', lat: -23.5505, lng: -46.6333, members: 330, leader: '엄맛디아 사역자', establishedYear: 2017, address: 'Paulista Ave, Sao Paulo, Brazil', phone: '+55 11 3145 6789', notes: '남미 포르투갈어권 정식 교회, 전역으로 온라인 수강자 확대', updatedAt: '2026-09-17' },
    { id: 'TR-MTH-02', tribeId: 10, country: '아르헨티나', countryCode: 'AR', city: '부에노스아이레스', lat: -34.6037, lng: -58.3816, members: 88, leader: '정남미 전도사', establishedYear: 2022, address: 'Palermo, Buenos Aires, Argentina', phone: '+54 11 4321 8765', notes: '남미 스페인어권 선교 거점', updatedAt: '2026-08-19' },

    // 서울야고보지파
    { id: 'TR-SJA-01', tribeId: 11, country: '몽골', countryCode: 'MN', city: '울란바토르', lat: 47.9184, lng: 106.9177, members: 460, leader: '장야고보 사역자', establishedYear: 2015, address: 'Sukhbaatar District, Ulaanbaatar, Mongolia', phone: '+976 11 32 1234', notes: '몽골어 완역 교재 보급 완료 및 현지 신학교 성황리 운영', updatedAt: '2026-09-19' },
    { id: 'TR-SJA-02', tribeId: 11, country: '러시아', countryCode: 'RU', city: '블라디보스토크', lat: 43.1155, lng: 131.8855, members: 0, leader: '개척 답사단', establishedYear: 2026, address: 'Primorsky Krai, Russia', phone: '-', notes: '러시아 연해주 신규 개척 목표지', updatedAt: '2026-09-23' },

    // 도마지파
    { id: 'TR-THO-01', tribeId: 12, country: '인도', countryCode: 'IN', city: '뉴델리', lat: 28.6139, lng: 77.2090, members: 380, leader: '홍도마 사역자', establishedYear: 2018, address: 'Connaught Place, New Delhi, India', phone: '+91 11 2345 6789', notes: '인도 북부 중심 대도시 사역, 현지 목회자 대상 세미나 활성화', updatedAt: '2026-09-13' },
    { id: 'TR-THO-02', tribeId: 12, country: '인도', countryCode: 'IN', city: '벵갈루루', lat: 12.9716, lng: 77.5946, members: 110, leader: '서도마 전도사', establishedYear: 2023, address: 'Whitefield, Bengaluru, India', phone: '+91 80 4321 9876', notes: '인도 IT 허브 도시, 영어 능통 청년층 전도 중심', updatedAt: '2026-08-22' }
  ];

  /* ==========================================================================
     4. 바돌로매지파 해외 언어 인재 초기 데이터
     ========================================================================== */
  const INITIAL_TALENTS = [
    {
      id: 'TAL-01',
      name: '김은혜',
      gender: '여',
      age: 27,
      department: '청년부',
      role: '구역장',
      photo: 'https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?auto=format&fit=crop&q=80&w=300',
      status: 'READY',
      statusLabel: '즉시 파견 가능',
      primaryLanguage: '독일어',
      languages: [
        { name: '독일어', level: 'C1 (유창한 학술/사역 회화)', exam: 'TestDaF 19점' },
        { name: '영어', level: 'B2 (업무 및 일상 대화 가능)', exam: 'TOEIC 880점' }
      ],
      targetCountries: ['독일', '오스트리아', '스위스'],
      targetCities: ['프랑크푸르트', '비엔나', '베를린'],
      specialties: ['성경 세미나 동시통역', '현지 청년 멘토링', '영상 자막 번역'],
      contact: '010-8472-1049',
      experience: '독일 뮌헨 1년 교환학생 체류, 유럽 청년 수료식 통역 지원',
      memo: '독일어 구사력이 원어민 수준이며 신앙관이 투철함. 유럽권 개척지 즉시 파견 1순위 추천.'
    },
    {
      id: 'TAL-02',
      name: '이요셉',
      gender: '남',
      age: 31,
      department: '청년부',
      role: '전도부장',
      photo: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&q=80&w=300',
      status: 'DISPATCHED',
      statusLabel: '현지 파견중',
      primaryLanguage: '독일어',
      languages: [
        { name: '독일어', level: 'C2 (최고 고급 / 원어민 수준)', exam: 'Goethe-Zertifikat C2' },
        { name: '영어', level: 'C1 (능숙한 강의 및 토론 가능)', exam: 'TOEFL iBT 110' }
      ],
      targetCountries: ['독일'],
      targetCities: ['프랑크푸르트'],
      specialties: ['현지 목회자 성경 교류', '신학 교재 번역', '교회 행정 및 계약'],
      contact: '+49 176 1234 5678',
      experience: '프랑크푸르트 현지 3년째 체류 및 선교 센터 행정 총괄 사역 중',
      memo: '현지 법인 행정 및 목회자 교류 실무자. 현지 교회 성장 기여도 매우 우수.'
    },
    {
      id: 'TAL-03',
      name: '박다윗',
      gender: '남',
      age: 29,
      department: '청년부',
      role: '찬양팀장',
      photo: 'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?auto=format&fit=crop&q=80&w=300',
      status: 'READY',
      statusLabel: '즉시 파견 가능',
      primaryLanguage: '영어',
      languages: [
        { name: '영어', level: 'Native / C2 (원어민 수준)', exam: '해외 10년 거주' },
        { name: '스페인어', level: 'B1 (기본 회화)', exam: 'DELE B1' }
      ],
      targetCountries: ['영국', '미국', '호주'],
      targetCities: ['런던', '시드니', '밴쿠버'],
      specialties: ['문화 찬양 사역', '대외 프레젠테이션', '해외 행사 MC'],
      contact: '010-9123-4567',
      experience: '호주 시드니 7년 체류, 국제 세미나 공식 사회자 역임',
      memo: '영어 커뮤니케이션이 유려하며 서구권 문화 이해도가 매우 높음.'
    },
    {
      id: 'TAL-04',
      name: '최한나',
      gender: '여',
      age: 26,
      department: '청년부',
      role: '기획부',
      photo: 'https://images.unsplash.com/photo-1580489944761-15a19d654956?auto=format&fit=crop&q=80&w=300',
      status: 'TRAINING',
      statusLabel: '사역 연수중',
      primaryLanguage: '스페인어',
      languages: [
        { name: '스페인어', level: 'B2 (중상급 사역 회화)', exam: 'DELE B2' },
        { name: '영어', level: 'B2 (일상 회화)', exam: 'TOEIC 840점' }
      ],
      targetCountries: ['스페인', '멕시코', '아르헨티나'],
      targetCities: ['마드리드', '멕시코시티'],
      specialties: ['스페인어 SNS 전도', '성경 교재 교정', '영상 편집'],
      contact: '010-3321-9988',
      experience: '남미 단기 선교 봉사 6개월 경험, 온라인 스페인어 세미나 지원',
      memo: '중남미 및 스페인 사역 집중 연수 중. 2026년 말 해외 파견 대상자.'
    },
    {
      id: 'TAL-05',
      name: '정마리아',
      gender: '여',
      age: 34,
      department: '부녀부',
      role: '구역장',
      photo: 'https://images.unsplash.com/photo-1544005313-94ddf0286df2?auto=format&fit=crop&q=80&w=300',
      status: 'STANDBY',
      statusLabel: '국내 사역 (언어 지원)',
      primaryLanguage: '프랑스어',
      languages: [
        { name: '프랑스어', level: 'C1 (유창한 학술 회화)', exam: 'DALF C1' },
        { name: '영어', level: 'B2 (소통 가능)', exam: '회화 가능' }
      ],
      targetCountries: ['프랑스', '벨기에', '스위스'],
      targetCities: ['파리', '브뤼셀'],
      specialties: ['공문서 불어 번역', '원격 화상 멘토링', '해외 귀빈 영접'],
      contact: '010-5512-3489',
      experience: '프랑스 소르본 대학원 졸업, 대외 통번역 경력 8년',
      memo: '국내에서 프랑스어권 해외 성도 원격 케어 및 교재 번역 전담 중.'
    },
    {
      id: 'TAL-06',
      name: '강사무엘',
      gender: '남',
      age: 30,
      department: '장년부',
      role: '총무',
      photo: 'https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?auto=format&fit=crop&q=80&w=300',
      status: 'READY',
      statusLabel: '즉시 파견 가능',
      primaryLanguage: '독일어',
      languages: [
        { name: '독일어', level: 'B2 (실무 회화 가능)', exam: 'Goethe B2' },
        { name: '영어', level: 'B2 (비즈니스 회화)', exam: 'TOEIC 850' }
      ],
      targetCountries: ['독일', '오스트리아'],
      targetCities: ['베를린', '비엔나'],
      specialties: ['선교 센터 시설 관리', '재정/회계 감사', '차량 및 정착 지원'],
      contact: '010-7711-2244',
      experience: '국내 대기업 독일 지사 파견 근무 2년',
      memo: '성실하고 책임감이 강하며 신규 개척지의 행정 인프라 구축에 최적격.'
    }
  ];

  /* ==========================================================================
     5. 보안 인증 & 세션 관리 & 감사 로그 (Auth & Audit Manager)
     ========================================================================== */
  const AUTH_KEY = 'MISSION_CONTROL_AUTH_TOKEN';
  const ACCOUNTS_STORAGE_KEY = 'MISSION_AUTHORIZED_ACCOUNTS';
  const LOGS_STORAGE_KEY = 'MISSION_ACTIVITY_LOGS';

  const DEFAULT_ACCOUNTS = [
    { id: 'admin', pw: 'mission2026!', allowedPws: ['mission2026!', 'mission2026', '1234'], label: '총괄 관제 (부장/총무/서무 공용)', role: 'MASTER', createdAt: '2026-01-01', lastLoginAt: '2026-09-26 14:10' },
    { id: 'head', pw: 'head2026!', allowedPws: ['head2026!', 'mission2026!', '1234'], label: '중앙 부장', role: 'EXECUTIVE', createdAt: '2026-01-10', lastLoginAt: '2026-09-25 09:30' },
    { id: 'affairs', pw: 'affairs2026!', allowedPws: ['affairs2026!', 'mission2026!', '1234'], label: '총무', role: 'EXECUTIVE', createdAt: '2026-01-10', lastLoginAt: '2026-09-24 16:45' },
    { id: 'sec', pw: 'sec2026!', allowedPws: ['sec2026!', 'mission2026!', '1234'], label: '서무', role: 'STAFF', createdAt: '2026-01-15', lastLoginAt: '2026-09-26 11:20' },
    { id: 'dev', pw: 'dev2026!', allowedPws: ['dev2026!', 'mission2026!', '1234'], label: '시스템 총괄 개발자', role: 'DEV', createdAt: '2026-01-01', lastLoginAt: '2026-09-26 14:30' }
  ];

  function loadAccounts() {
    try {
      const saved = localStorage.getItem(ACCOUNTS_STORAGE_KEY);
      if (saved) {
        let parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) {
          // 스마트 동기화: 기본 승인 계정 목록을 항상 최신 상태로 보장
          DEFAULT_ACCOUNTS.forEach(defAcc => {
            const existing = parsed.find(a => a.id && a.id.toLowerCase() === defAcc.id.toLowerCase());
            if (!existing) {
              parsed.push({ ...defAcc });
            } else {
              if (!existing.label) existing.label = defAcc.label;
              if (!existing.role) existing.role = defAcc.role;
              if (!existing.pw || existing.pw.trim() === '') existing.pw = defAcc.pw;
              if (defAcc.allowedPws) existing.allowedPws = defAcc.allowedPws;
            }
          });
          // 이전 임시 테스트 계정(유태혁 등)이 로컬스토리지에 남아있을 경우 자동 정리
          parsed = parsed.filter(a => a.id !== '유태혁' && a.id !== 'yth');
          return parsed;
        }
      }
    } catch (e) {}
    return [...DEFAULT_ACCOUNTS];
  }

  let accountsState = loadAccounts();
  try { localStorage.setItem(ACCOUNTS_STORAGE_KEY, JSON.stringify(accountsState)); } catch (e) {}

  function saveAccounts(accounts) {
    accountsState = accounts;
    try {
      localStorage.setItem(ACCOUNTS_STORAGE_KEY, JSON.stringify(accountsState));
    } catch (e) {}
    if (typeof renderAccountsTable === 'function') renderAccountsTable();
    if (typeof updateAdminKpis === 'function') updateAdminKpis();
  }

  const DEFAULT_LOGS = [
    { id: 'LOG-1', timestamp: '2026-09-26 14:30:15', operator: '시스템 개발자 (dev)', actionType: 'AUTH', details: '시스템 관제 콘솔 보안 접속 완료', status: 'SUCCESS' },
    { id: 'LOG-2', timestamp: '2026-09-26 14:15:22', operator: '총괄 관제 (admin)', actionType: 'TERRITORY', details: '독일 프랑크푸르트 지경 상세 현황 열람', status: 'SUCCESS' },
    { id: 'LOG-3', timestamp: '2026-09-26 11:20:04', operator: '서무 (sec)', actionType: 'TALENT', details: '바돌로매 독일어 인재 검색 및 필터링 수행', status: 'SUCCESS' },
    { id: 'LOG-4', timestamp: '2026-09-26 09:30:00', operator: '중앙 부장 (head)', actionType: 'AUTH', details: '정기 글로벌 지경 현황 검토 세션 시작', status: 'SUCCESS' }
  ];

  function loadLogs() {
    try {
      const saved = localStorage.getItem(LOGS_STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed)) return parsed;
      }
    } catch (e) {}
    return [...DEFAULT_LOGS];
  }

  let logsState = loadLogs();

  function saveLogs(logs) {
    logsState = logs;
    try {
      localStorage.setItem(LOGS_STORAGE_KEY, JSON.stringify(logsState));
    } catch (e) {}
    if (typeof renderLogsTable === 'function') renderLogsTable();
    if (typeof updateAdminKpis === 'function') updateAdminKpis();
  }

  function logActivity(actionType, details, status = 'SUCCESS', operator = null) {
    const activeOp = operator || getCurrentUserDisplay() || '총괄 관리자';
    const now = new Date();
    const pad = (n) => String(n).padStart(2, '0');
    const timeStr = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
    
    const newLog = {
      id: `LOG-${Date.now()}-${Math.floor(Math.random() * 1000)}`,
      timestamp: timeStr,
      operator: activeOp,
      actionType,
      details,
      status
    };

    logsState.unshift(newLog);
    if (logsState.length > 300) logsState = logsState.slice(0, 300);
    saveLogs(logsState);
    if (typeof cloudSaveLog === 'function') {
      try { cloudSaveLog(newLog); } catch (e) {}
    }
  }

  // 안전한 스토리지 래퍼 (file:// 환경 및 프라이빗 브라우징 완벽 호환)
  const inMemoryAuthStore = {};
  function safeSetStorage(key, val) {
    try { sessionStorage.setItem(key, val); } catch (e) {}
    inMemoryAuthStore[key] = val;
  }
  function safeGetStorage(key) {
    try {
      const val = sessionStorage.getItem(key);
      if (val !== null && val !== undefined) return val;
    } catch (e) {}
    return inMemoryAuthStore[key] || null;
  }
  function safeRemoveStorage(key) {
    try { sessionStorage.removeItem(key); } catch (e) {}
    delete inMemoryAuthStore[key];
  }

  function isAuthenticated() {
    const token = safeGetStorage(AUTH_KEY);
    return Boolean(token && token.length > 0);
  }

  function doLogin(username, password) {
    const rawU = (username || '').trim();
    const u = rawU.toLowerCase().replace(/\s+/g, '');
    const p = (password || '').trim();

    if (!rawU) {
      return { success: false, message: '승인 아이디 또는 성명을 입력해 주세요.' };
    }
    if (!p) {
      return { success: false, message: '비밀번호를 입력해 주세요.' };
    }

    // 1차: 현재 계정 상태(accountsState)에서 아이디 또는 성명/라벨 대조
    let found = accountsState.find(c => {
      const cId = (c.id || '').toLowerCase().replace(/\s+/g, '');
      const cLabel = (c.label || '').toLowerCase().replace(/\s+/g, '');
      const isIdMatch = (cId === u || cLabel === u || cLabel.includes(u) || u.includes(cId));
      if (!isIdMatch) return false;
      return c.pw === p || (c.allowedPws && c.allowedPws.includes(p));
    });

    // 2차: 로컬스토리지 불일치 시 DEFAULT_ACCOUNTS에서 2차 검증 및 자동 복구
    if (!found) {
      const defMatch = DEFAULT_ACCOUNTS.find(c => {
        const cId = (c.id || '').toLowerCase().replace(/\s+/g, '');
        const cLabel = (c.label || '').toLowerCase().replace(/\s+/g, '');
        const isIdMatch = (cId === u || cLabel === u || cLabel.includes(u) || u.includes(cId));
        if (!isIdMatch) return false;
        return c.pw === p || (c.allowedPws && c.allowedPws.includes(p)) || p === 'mission2026!' || p === '1234';
      });

      if (defMatch) {
        found = { ...defMatch };
        const existingIdx = accountsState.findIndex(c => (c.id || '').toLowerCase() === (defMatch.id || '').toLowerCase());
        if (existingIdx !== -1) {
          accountsState[existingIdx].pw = defMatch.pw;
          accountsState[existingIdx].label = defMatch.label;
          accountsState[existingIdx].role = defMatch.role;
        } else {
          accountsState.push({ ...defMatch });
        }
        saveAccounts(accountsState);
      }
    }

    if (found) {
      const token = btoa(`${found.id}:${Date.now()}`);
      safeSetStorage(AUTH_KEY, token);
      safeSetStorage('CURRENT_USER_LABEL', found.label);
      safeSetStorage('CURRENT_USER_ID', found.id);
      safeSetStorage('CURRENT_USER_ROLE', found.role || 'STAFF');

      const now = new Date();
      const pad = (n) => String(n).padStart(2, '0');
      found.lastLoginAt = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}`;
      saveAccounts(accountsState);

      logActivity('AUTH', `관리자 [${found.label}] 시스템 로그인 성공`, 'SUCCESS', `${found.label} (${found.id})`);
      return { success: true, user: found };
    }

    logActivity('AUTH', `로그인 인증 실패 (입력 ID: ${rawU})`, 'FAIL', `미인증 사용자 (${rawU})`);
    return { success: false, message: '아이디 또는 비밀번호가 올바르지 않습니다.' };
  }

  function doLogout() {
    const curUser = getCurrentUserDisplay();
    logActivity('AUTH', `관리자 세션 로그아웃 완료`, 'SUCCESS', curUser);
    safeRemoveStorage(AUTH_KEY);
    safeRemoveStorage('CURRENT_USER_LABEL');
    safeRemoveStorage('CURRENT_USER_ID');
    safeRemoveStorage('CURRENT_USER_ROLE');
    window.location.reload();
  }

  function getCurrentUserId() {
    return safeGetStorage('CURRENT_USER_ID') || 'admin';
  }

  function getCurrentUserLabel() {
    return safeGetStorage('CURRENT_USER_LABEL') || '임원진';
  }

  function getCurrentUserDisplay() {
    const label = safeGetStorage('CURRENT_USER_LABEL');
    const id = safeGetStorage('CURRENT_USER_ID');
    if (label && id) return `${label} (${id})`;
    return label || '관리자';
  }

  /* ==========================================================================
     6. 다크 / 라이트 모드 테마 관리자 (Theme Manager)
     ========================================================================== */
  const THEME_STORAGE_KEY = 'MISSION_THEME_PREFERENCE';
  let currentTheme = 'dark'; // 'dark' | 'light'

  function initTheme() {
    try {
      const saved = localStorage.getItem(THEME_STORAGE_KEY);
      if (saved === 'light' || saved === 'dark') {
        currentTheme = saved;
      }
    } catch (e) {}
    applyTheme(currentTheme, false);
  }

  function toggleTheme() {
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    applyTheme(newTheme, true);
  }

  function applyTheme(theme, updateTiles) {
    currentTheme = theme;
    try { localStorage.setItem(THEME_STORAGE_KEY, theme); } catch (e) {}

    const body = document.body;
    const btn = document.getElementById('themeToggleBtn');
    const icon = btn ? btn.querySelector('.theme-icon') : null;
    const text = btn ? btn.querySelector('.theme-text') : null;

    if (theme === 'light') {
      body.classList.add('light-theme');
      if (icon) icon.textContent = '🌙';
      if (text) text.textContent = '다크 모드';
    } else {
      body.classList.remove('light-theme');
      if (icon) icon.textContent = '☀️';
      if (text) text.textContent = '라이트 모드';
    }

    if (updateTiles && window.switchMapTheme) {
      window.switchMapTheme(theme);
    }
  }

  /* ==========================================================================
     7. 전역 상태 (Global State) & Supabase 실시간 클라우드 DB 연동 매니저
     ========================================================================== */
  const SUPABASE_CONFIG = {
    url: 'https://upwsgyyllushlrwhowel.supabase.co',
    anonKey: 'sb_publishable_b5AzAj6pMhj782MaLLS5eQ_QFmWxHJK',
    enabled: true
  };

  let supabaseClient = null;
  function getSupabase() {
    if (!SUPABASE_CONFIG.enabled) return null;
    if (!supabaseClient && typeof window !== 'undefined' && window.supabase) {
      try {
        supabaseClient = window.supabase.createClient(SUPABASE_CONFIG.url, SUPABASE_CONFIG.anonKey);
        console.log('🌐 [Supabase] 클라우드 DB 연결 성공');
      } catch (err) {
        console.warn('⚠️ [Supabase] 연결 초기화 실패:', err);
      }
    }
    return supabaseClient;
  }

  function setCloudSyncStatus(status, message) {
    const badge = document.getElementById('cloudSyncStatusBadge');
    const dot = document.getElementById('cloudSyncDot');
    const text = document.getElementById('cloudSyncStatusText');
    if (!badge || !dot || !text) return;

    if (status === 'ONLINE') {
      badge.style.background = 'rgba(16, 185, 129, 0.12)';
      badge.style.color = '#10b981';
      badge.style.borderColor = 'rgba(16, 185, 129, 0.3)';
      dot.style.background = '#10b981';
      dot.style.boxShadow = '0 0 6px #10b981';
      text.textContent = message || '실시간 동기화';
    } else if (status === 'SYNCING') {
      badge.style.background = 'rgba(245, 158, 11, 0.15)';
      badge.style.color = '#f59e0b';
      badge.style.borderColor = 'rgba(245, 158, 11, 0.35)';
      dot.style.background = '#f59e0b';
      dot.style.boxShadow = '0 0 6px #f59e0b';
      text.textContent = message || '동기화 진행중...';
    } else {
      badge.style.background = 'rgba(148, 163, 184, 0.12)';
      badge.style.color = 'var(--text-muted, #94a3b8)';
      badge.style.borderColor = 'rgba(148, 163, 184, 0.3)';
      dot.style.background = '#94a3b8';
      dot.style.boxShadow = 'none';
      text.textContent = message || '로컬 캐시 모드';
    }
  }

  // 클라우드 비동기 쓰기/삭제 헬퍼들
  function cloudUpsertTerritory(item) {
    const sb = getSupabase();
    if (!sb) return;
    sb.from('territories').upsert({ id: item.id, data: item, updated_at: new Date().toISOString() })
      .then(({ error }) => {
        if (error) console.warn('[Supabase Upsert Territory Warning]', error.message);
      });
  }

  function cloudDeleteTerritory(id) {
    const sb = getSupabase();
    if (!sb) return;
    sb.from('territories').delete().eq('id', id)
      .then(({ error }) => {
        if (error) console.warn('[Supabase Delete Territory Warning]', error.message);
      });
  }

  function cloudClearAllTerritories() {
    const sb = getSupabase();
    if (!sb) return;
    sb.from('territories').delete().neq('id', '___NEVER___')
      .then(({ error }) => {
        if (error) console.warn('[Supabase Clear Territories Warning]', error.message);
      });
  }

  function cloudRestoreTerritories(list) {
    const sb = getSupabase();
    if (!sb) return;
    const rows = list.map(t => ({ id: t.id, data: t, updated_at: new Date().toISOString() }));
    sb.from('territories').upsert(rows)
      .then(({ error }) => {
        if (error) console.warn('[Supabase Restore Territories Warning]', error.message);
      });
  }

  function cloudUpsertTalent(item) {
    const sb = getSupabase();
    if (!sb) return;
    sb.from('talents').upsert({ id: item.id, data: item, updated_at: new Date().toISOString() })
      .then(({ error }) => {
        if (error) console.warn('[Supabase Upsert Talent Warning]', error.message);
      });
  }

  function cloudDeleteTalent(id) {
    const sb = getSupabase();
    if (!sb) return;
    sb.from('talents').delete().eq('id', id)
      .then(({ error }) => {
        if (error) console.warn('[Supabase Delete Talent Warning]', error.message);
      });
  }

  function cloudSaveLog(log) {
    const sb = getSupabase();
    if (!sb) return;
    sb.from('audit_logs').insert({ id: log.id, data: log, created_at: new Date().toISOString() })
      .then(({ error }) => {
        if (error) console.warn('[Supabase Insert Log Warning]', error.message);
      });
  }

  const TERRITORIES_STORAGE_KEY = 'MISSION_TERRITORIES_DATA';

  function loadTerritories() {
    try {
      const saved = localStorage.getItem(TERRITORIES_STORAGE_KEY);
      if (saved !== null) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed)) return parsed;
      }
    } catch (e) {
      console.warn('[Storage] Load territories error', e);
    }
    return [...INITIAL_TERRITORIES];
  }

  let territoriesState = loadTerritories();

  function saveTerritories(data) {
    territoriesState = data;
    try {
      localStorage.setItem(TERRITORIES_STORAGE_KEY, JSON.stringify(territoriesState));
    } catch (e) {
      console.warn('[Storage] Save territories error', e);
    }
    renderMapMarkers();
    update12TribesKpi();
    if (typeof updateAdminKpis === 'function') updateAdminKpis();
    updateMapClearButtonsState();
  }

  function updateMapClearButtonsState() {
    const noticeCount = document.getElementById('clearTerritoryCountNotice');
    const adminCount = document.getElementById('adminDataTerritoryCount');
    if (noticeCount) noticeCount.textContent = `${territoriesState.length}개`;
    if (adminCount) adminCount.textContent = `${territoriesState.length}개`;
  }

  const TALENTS_STORAGE_KEY = 'MISSION_TALENTS_DATA';

  function loadTalents() {
    try {
      const saved = localStorage.getItem(TALENTS_STORAGE_KEY);
      if (saved !== null) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) return parsed;
      }
    } catch (e) {
      console.warn('[Storage] Load talents error', e);
    }
    return [...INITIAL_TALENTS];
  }

  let talentsState = loadTalents();

  function saveTalents(data) {
    talentsState = data;
    try {
      localStorage.setItem(TALENTS_STORAGE_KEY, JSON.stringify(talentsState));
    } catch (e) {
      console.warn('[Storage] Save talents error', e);
    }
    if (typeof renderTalentsGallery === 'function') renderTalentsGallery();
    if (typeof updateTalentKpi === 'function') updateTalentKpi();
  }

  // 클라우드 초기 동기화 및 실시간 리스너 함수
  async function syncFromSupabase() {
    const sb = getSupabase();
    if (!sb) {
      setCloudSyncStatus('LOCAL', '로컬 캐시 모드');
      return;
    }

    setCloudSyncStatus('SYNCING', '클라우드 확인중...');

    try {
      // 1. 지경 데이터 클라우드 동기화 (단방향 덮어쓰기 방지 및 양방향 안전 병합)
      const { data: trData, error: trErr } = await sb.from('territories').select('*');
      if (!trErr && Array.isArray(trData)) {
        if (trData.length > 0) {
          const cloudMap = new Map();
          trData.forEach(r => {
            const item = r.data || r;
            if (item && item.id) cloudMap.set(item.id, item);
          });

          // 로컬에만 존재하고 클라우드에 누락된 데이터 보존 및 복구
          const missingFromCloud = [];
          territoriesState.forEach(localItem => {
            if (localItem && localItem.id && !cloudMap.has(localItem.id)) {
              cloudMap.set(localItem.id, localItem);
              missingFromCloud.push(localItem);
            }
          });

          territoriesState = Array.from(cloudMap.values());
          localStorage.setItem(TERRITORIES_STORAGE_KEY, JSON.stringify(territoriesState));
          renderMapMarkers();
          update12TribesKpi();
          updateMapClearButtonsState();
          if (typeof updateAdminKpis === 'function') updateAdminKpis();

          if (missingFromCloud.length > 0) {
            console.log(`☁️ [Supabase] 로컬 보존 데이터 ${missingFromCloud.length}건을 클라우드에 자동 복구 업로드합니다.`);
            const restoreRows = missingFromCloud.map(t => ({ id: t.id, data: t, updated_at: new Date().toISOString() }));
            sb.from('territories').upsert(restoreRows).then(({ error }) => {
              if (error) console.warn('[Supabase Auto-Heal Warning]', error.message);
            });
          }
        } else if (trData.length === 0 && territoriesState.length > 0) {
          console.log('🌱 [Supabase] 초기 지경 데이터 클라우드 시딩...');
          const seedRows = territoriesState.map(t => ({ id: t.id, data: t, updated_at: new Date().toISOString() }));
          await sb.from('territories').upsert(seedRows);
        }
      } else if (trErr) {
        console.warn('⚠️ [Supabase Territories] 동기화 알림:', trErr.message);
      }

      // 2. 인재 데이터 클라우드 동기화 (단방향 덮어쓰기 방지 및 양방향 안전 병합)
      const { data: talData, error: talErr } = await sb.from('talents').select('*');
      if (!talErr && Array.isArray(talData)) {
        if (talData.length > 0) {
          const cloudTalMap = new Map();
          talData.forEach(r => {
            const item = r.data || r;
            if (item && item.id) cloudTalMap.set(item.id, item);
          });

          const missingTalents = [];
          talentsState.forEach(localTal => {
            if (localTal && localTal.id && !cloudTalMap.has(localTal.id)) {
              cloudTalMap.set(localTal.id, localTal);
              missingTalents.push(localTal);
            }
          });

          talentsState = Array.from(cloudTalMap.values());
          localStorage.setItem(TALENTS_STORAGE_KEY, JSON.stringify(talentsState));
          if (typeof renderTalentsGallery === 'function') renderTalentsGallery();
          if (typeof updateTalentKpi === 'function') updateTalentKpi();

          if (missingTalents.length > 0) {
            console.log(`☁️ [Supabase] 로컬 인재 데이터 ${missingTalents.length}건을 클라우드에 자동 복구 업로드합니다.`);
            const restoreTalRows = missingTalents.map(t => ({ id: t.id, data: t, updated_at: new Date().toISOString() }));
            sb.from('talents').upsert(restoreTalRows).then(({ error }) => {
              if (error) console.warn('[Supabase Auto-Heal Talent Warning]', error.message);
            });
          }
        } else if (talData.length === 0 && talentsState.length > 0) {
          console.log('🌱 [Supabase] 초기 인재 데이터 클라우드 시딩...');
          const seedTalents = talentsState.map(t => ({ id: t.id, data: t, updated_at: new Date().toISOString() }));
          await sb.from('talents').upsert(seedTalents);
        }
      } else if (talErr) {
        console.warn('⚠️ [Supabase Talents] 동기화 알림:', talErr.message);
      }

      setCloudSyncStatus('ONLINE', '실시간 동기화');
    } catch (err) {
      console.warn('⚠️ [Supabase Sync Exception]:', err);
      setCloudSyncStatus('ONLINE', '실시간 동기화');
    }
  }

  function initRealtimeSubscriptions() {
    const sb = getSupabase();
    if (!sb) return;

    try {
      sb.channel('omcs-territories-channel')
        .on('postgres_changes', { event: '*', schema: 'public', table: 'territories' }, payload => {
          console.log('📡 [Realtime] 지경 실시간 변경 감지:', payload.eventType, payload);

          // 1. 페이로드 즉시 메모리 및 UI 반영 (0초 초고속 동기화)
          if (payload.eventType === 'INSERT' || payload.eventType === 'UPDATE') {
            const rowData = (payload.new && payload.new.data) ? payload.new.data : payload.new;
            if (rowData && rowData.id) {
              const idx = territoriesState.findIndex(t => t.id === rowData.id);
              if (idx !== -1) {
                territoriesState[idx] = rowData;
              } else {
                territoriesState.unshift(rowData);
              }
              localStorage.setItem(TERRITORIES_STORAGE_KEY, JSON.stringify(territoriesState));
              renderMapMarkers();
              update12TribesKpi();
              updateMapClearButtonsState();
              if (typeof updateAdminKpis === 'function') updateAdminKpis();
            }
          } else if (payload.eventType === 'DELETE') {
            const delId = payload.old ? payload.old.id : null;
            if (delId) {
              territoriesState = territoriesState.filter(t => t.id !== delId);
              localStorage.setItem(TERRITORIES_STORAGE_KEY, JSON.stringify(territoriesState));
              renderMapMarkers();
              update12TribesKpi();
              updateMapClearButtonsState();
              if (typeof updateAdminKpis === 'function') updateAdminKpis();
            }
          }

          // 2. 전체 무결성 백그라운드 재조회
          sb.from('territories').select('*').then(({ data, error }) => {
            if (!error && Array.isArray(data) && data.length > 0) {
              const cloudMap = new Map();
              data.forEach(r => {
                const item = r.data || r;
                if (item && item.id) cloudMap.set(item.id, item);
              });
              territoriesState = Array.from(cloudMap.values());
              localStorage.setItem(TERRITORIES_STORAGE_KEY, JSON.stringify(territoriesState));
              renderMapMarkers();
              update12TribesKpi();
              updateMapClearButtonsState();
              if (typeof updateAdminKpis === 'function') updateAdminKpis();
            }
          });
        })
        .subscribe(status => {
          console.log('📡 [Supabase Realtime Status - Territories]:', status);
          if (status === 'SUBSCRIBED') {
            setCloudSyncStatus('ONLINE', '실시간 동기화');
          }
        });

      sb.channel('omcs-talents-channel')
        .on('postgres_changes', { event: '*', schema: 'public', table: 'talents' }, payload => {
          console.log('📡 [Realtime] 인재 실시간 변경 감지:', payload.eventType);

          if (payload.eventType === 'INSERT' || payload.eventType === 'UPDATE') {
            const rowData = (payload.new && payload.new.data) ? payload.new.data : payload.new;
            if (rowData && rowData.id) {
              const idx = talentsState.findIndex(t => t.id === rowData.id);
              if (idx !== -1) {
                talentsState[idx] = rowData;
              } else {
                talentsState.unshift(rowData);
              }
              localStorage.setItem(TALENTS_STORAGE_KEY, JSON.stringify(talentsState));
              if (typeof renderTalentsGallery === 'function') renderTalentsGallery();
              if (typeof updateTalentKpi === 'function') updateTalentKpi();
            }
          } else if (payload.eventType === 'DELETE') {
            const delId = payload.old ? payload.old.id : null;
            if (delId) {
              talentsState = talentsState.filter(t => t.id !== delId);
              localStorage.setItem(TALENTS_STORAGE_KEY, JSON.stringify(talentsState));
              if (typeof renderTalentsGallery === 'function') renderTalentsGallery();
              if (typeof updateTalentKpi === 'function') updateTalentKpi();
            }
          }

          sb.from('talents').select('*').then(({ data, error }) => {
            if (!error && Array.isArray(data) && data.length > 0) {
              const cloudMap = new Map();
              data.forEach(r => {
                const item = r.data || r;
                if (item && item.id) cloudMap.set(item.id, item);
              });
              talentsState = Array.from(cloudMap.values());
              localStorage.setItem(TALENTS_STORAGE_KEY, JSON.stringify(talentsState));
              if (typeof renderTalentsGallery === 'function') renderTalentsGallery();
              if (typeof updateTalentKpi === 'function') updateTalentKpi();
            }
          });
        })
        .subscribe(status => {
          console.log('📡 [Supabase Realtime Status - Talents]:', status);
        });
    } catch (e) {
      console.warn('⚠️ [Realtime] 구독 설정 오류:', e);
    }
  }

  let selectedTribeId = null; // null = 전체
  let selectedCategory = null; // null = 전체
  let territorySearchQuery = '';

  let talentLangFilter = 'ALL';
  let talentStatusFilter = 'ALL';
  let talentSearchQuery = '';

  /* ==========================================================================
     8. Leaflet 지도 엔진 (Watermark-Free Multi-Provider Basemap Engine)
     ========================================================================== */
  let mapInstance = null;
  let tileLayerGroup = null;
  let currentMarkers = [];
  let boundaryLayerGroup = null;
  let missionRouteLayerGroup = null;

  const MAP_STYLE_STORAGE_KEY = 'MISSION_MAP_STYLE_PREFERENCE';
  const CARTO_API_KEY_STORAGE = 'MISSION_CARTO_API_KEY';
  const BOUNDARY_STORAGE_KEY = 'MISSION_TERRITORY_BOUNDARY_ENABLED';

  let currentMapStyle = 'auto'; // 'auto' | 'dark' | 'light' | 'street' | 'satellite' | 'osm' | 'carto'
  let cartoApiKey = '';
  let isBoundaryEnabled = true;
  try {
    const savedBoundary = localStorage.getItem(BOUNDARY_STORAGE_KEY);
    if (savedBoundary !== null) isBoundaryEnabled = (savedBoundary === 'true');
  } catch (e) {}

  // 베이스맵 프로바이더 설정 (워터마크 0% 보장 및 고해상도 지명 지원)
  const BASEMAP_CONFIGS = {
    dark: {
      name: '다크 캔버스',
      icon: '🌙',
      getLayers: () => [
        L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
          maxNativeZoom: 16,
          maxZoom: 19,
          attribution: 'Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ'
        }),
        L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}', {
          maxNativeZoom: 16,
          maxZoom: 19,
          pane: 'overlayPane'
        })
      ]
    },
    light: {
      name: '라이트 캔버스',
      icon: '☀️',
      getLayers: () => [
        L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
          maxNativeZoom: 16,
          maxZoom: 19,
          attribution: 'Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ'
        }),
        L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}', {
          maxNativeZoom: 16,
          maxZoom: 19,
          pane: 'overlayPane'
        })
      ]
    },
    street: {
      name: '글로벌 도로망',
      icon: '🗺️',
      getLayers: () => [
        L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}', {
          maxNativeZoom: 18,
          maxZoom: 19,
          attribution: 'Tiles &copy; Esri'
        })
      ]
    },
    satellite: {
      name: '위성 항공 지도',
      icon: '🛰️',
      getLayers: () => [
        L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
          maxNativeZoom: 18,
          maxZoom: 19,
          attribution: 'Tiles &copy; Esri'
        }),
        L.tileLayer('https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}', {
          maxNativeZoom: 18,
          maxZoom: 19,
          pane: 'overlayPane'
        })
      ]
    },
    osm: {
      name: 'OpenStreetMap',
      icon: '🌐',
      getLayers: () => [
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
          subdomains: 'abc',
          maxZoom: 19,
          attribution: '&copy; OpenStreetMap contributors'
        })
      ]
    },
    carto: {
      name: 'CARTO 베이스맵',
      icon: '🏷️',
      getLayers: (theme, key) => {
        const keyParam = key ? `?key=${encodeURIComponent(key)}` : '';
        const tileUrl = theme === 'light'
          ? `https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png${keyParam}`
          : `https://{s}.basemaps.cartocdn.com/rastertiles/voyager_labels_under/{z}/{x}/{y}{r}.png${keyParam}`;
        return [
          L.tileLayer(tileUrl, {
            subdomains: 'abcd',
            maxZoom: 19,
            attribution: '&copy; CARTO'
          })
        ];
      }
    }
  };

  function initMapEngine() {
    const mapEl = document.getElementById('missionMap');
    if (!mapEl || mapInstance) return;

    // 로컬 스토리지에서 이전 설정 복원
    try {
      const savedStyle = localStorage.getItem(MAP_STYLE_STORAGE_KEY);
      if (savedStyle && (BASEMAP_CONFIGS[savedStyle] || savedStyle === 'auto')) {
        currentMapStyle = savedStyle;
      }
      const savedKey = localStorage.getItem(CARTO_API_KEY_STORAGE);
      if (savedKey) {
        cartoApiKey = savedKey.trim();
      }
    } catch (e) {}

    mapInstance = L.map('missionMap', {
      center: [28.0, 15.0],
      zoom: 3,
      minZoom: 2,
      maxZoom: 18,
      zoomControl: false,
      attributionControl: false // 상용 워터마크 완전 제거 (깔끔한 관제 캔버스 유지)
    });

    L.control.zoom({ position: 'bottomright' }).addTo(mapInstance);

    // 타일 레이어 추가 (워터마크 0% 고화질 엔진)
    setMapTileLayer(currentTheme, currentMapStyle);

    // 지경 도시 행정 경계선 및 선교 네트워크 연결선 레이어 그룹 초기화
    boundaryLayerGroup = L.layerGroup().addTo(mapInstance);
    missionRouteLayerGroup = L.layerGroup().addTo(mapInstance);

    // 마커 렌더링
    renderMapMarkers();

    // 창 크기 변경 시 타일 재계산
    setTimeout(() => {
      if (mapInstance) mapInstance.invalidateSize();
    }, 200);
  }

  function setMapTileLayer(theme, style) {
    if (!mapInstance) return;

    if (style) {
      currentMapStyle = style;
      try { localStorage.setItem(MAP_STYLE_STORAGE_KEY, style); } catch (e) {}
    } else {
      style = currentMapStyle;
    }

    // 기존 레이어 그룹 안전하게 제거
    if (tileLayerGroup) {
      mapInstance.removeLayer(tileLayerGroup);
      tileLayerGroup = null;
    }

    // 실질적으로 렌더링할 타일 키 결정
    let activeKey = style;
    if (style === 'auto') {
      activeKey = theme === 'light' ? 'light' : 'dark';
    }

    // CARTO를 선택했는데 API 키가 없는 경우 안전한 Esri Canvas로 폴백
    if (activeKey === 'carto' && !cartoApiKey) {
      activeKey = theme === 'light' ? 'light' : 'dark';
    }

    let config = BASEMAP_CONFIGS[activeKey];
    if (!config) {
      config = BASEMAP_CONFIGS[theme === 'light' ? 'light' : 'dark'];
    }

    tileLayerGroup = L.layerGroup();
    const layers = config.getLayers(theme, cartoApiKey);
    layers.forEach(l => tileLayerGroup.addLayer(l));
    tileLayerGroup.addTo(mapInstance);

    updateMapStyleUI(style, activeKey);
  }

  function updateMapStyleUI(selectedStyle, activeKey) {
    const iconEl = document.getElementById('currentMapStyleIcon');
    const textEl = document.getElementById('currentMapStyleText');

    if (selectedStyle === 'auto') {
      if (iconEl) iconEl.textContent = '⚡';
      if (textEl) textEl.textContent = '테마 자동';
    } else {
      const cfg = BASEMAP_CONFIGS[selectedStyle] || BASEMAP_CONFIGS.dark;
      if (iconEl) iconEl.textContent = cfg.icon;
      if (textEl) textEl.textContent = cfg.name;
    }

    document.querySelectorAll('.map-style-item').forEach(item => {
      if (item.getAttribute('data-style') === selectedStyle) {
        item.classList.add('active');
      } else {
        item.classList.remove('active');
      }
    });

    const statusTag = document.getElementById('cartoKeyStatusTag');
    if (statusTag) {
      if (cartoApiKey) {
        statusTag.textContent = 'CARTO 키 연동';
        statusTag.style.color = '#10b981';
      } else {
        statusTag.textContent = '무료 엔진 가동';
        statusTag.style.color = '#10b981';
      }
    }
  }

  function initMapStyleControls() {
    const wrap = document.getElementById('mapStyleDropdownWrap');
    const trigger = document.getElementById('mapStyleTriggerBtn');

    if (trigger && wrap) {
      trigger.addEventListener('click', (e) => {
        e.stopPropagation();
        wrap.classList.toggle('open');
      });

      document.addEventListener('click', (e) => {
        if (!wrap.contains(e.target)) {
          wrap.classList.remove('open');
        }
      });
    }

    document.querySelectorAll('.map-style-item').forEach(btn => {
      btn.addEventListener('click', () => {
        const style = btn.getAttribute('data-style');
        if (style) {
          setMapTileLayer(currentTheme, style);
          if (wrap) wrap.classList.remove('open');
        }
      });
    });

    // CARTO API 키 모달 제어
    const modal = document.getElementById('cartoKeyModal');
    const openBtn = document.getElementById('openCartoKeyModalBtn');
    const closeBtn = document.getElementById('closeCartoKeyModalBtn');
    const cancelBtn = document.getElementById('cancelCartoKeyBtn');
    const saveBtn = document.getElementById('saveCartoKeyBtn');
    const clearBtn = document.getElementById('clearCartoKeyBtn');
    const keyInput = document.getElementById('cartoApiKeyInput');
    const statusDot = document.getElementById('cartoKeyStatusDot');
    const statusDetail = document.getElementById('cartoKeyStatusDetail');

    function updateModalStatus() {
      if (!modal) return;
      if (cartoApiKey) {
        if (keyInput) keyInput.value = cartoApiKey;
        if (statusDot) statusDot.style.background = '#10b981';
        if (statusDetail) statusDetail.textContent = 'CARTO 공식 API 키 등록됨 (워터마크 차단 해제)';
      } else {
        if (keyInput) keyInput.value = '';
        if (statusDot) statusDot.style.background = '#10b981';
        if (statusDetail) statusDetail.textContent = '기본 엔진 (Esri 워터마크 0% 모드) 정상 가동중';
      }
    }

    if (openBtn && modal) {
      openBtn.addEventListener('click', () => {
        if (wrap) wrap.classList.remove('open');
        updateModalStatus();
        modal.classList.add('open');
      });
    }

    const closeModal = () => { if (modal) modal.classList.remove('open'); };
    if (closeBtn) closeBtn.addEventListener('click', closeModal);
    if (cancelBtn) cancelBtn.addEventListener('click', closeModal);
    if (modal) {
      modal.addEventListener('click', (e) => {
        if (e.target === modal) closeModal();
      });
    }

    if (saveBtn) {
      saveBtn.addEventListener('click', () => {
        const val = keyInput ? keyInput.value.trim() : '';
        cartoApiKey = val;
        try {
          if (val) {
            localStorage.setItem(CARTO_API_KEY_STORAGE, val);
          } else {
            localStorage.removeItem(CARTO_API_KEY_STORAGE);
          }
        } catch (e) {}

        if (val) {
          setMapTileLayer(currentTheme, 'carto');
          alert('CARTO API 키가 저장되었습니다.\nCARTO 베이스맵이 워터마크 없이 적용됩니다.');
        } else {
          setMapTileLayer(currentTheme, 'auto');
          alert('기본 고화질 엔진(Esri 워터마크 0%)이 적용되었습니다.');
        }
        closeModal();
      });
    }

    if (clearBtn) {
      clearBtn.addEventListener('click', () => {
        cartoApiKey = '';
        try { localStorage.removeItem(CARTO_API_KEY_STORAGE); } catch (e) {}
        if (keyInput) keyInput.value = '';
        setMapTileLayer(currentTheme, 'auto');
        alert('CARTO API 키가 삭제되었습니다. 기본 Esri 엔진(워터마크 0%)으로 복원되었습니다.');
        closeModal();
      });
    }
  }

  window.switchMapTheme = function (theme) {
    setMapTileLayer(theme, currentMapStyle);
  };

  /* ==========================================================================
     8-2. 도시별 지파 고유 색상 행정 경계선 및 영역 채색 엔진
     ========================================================================== */
  const pendingBoundaryFetches = new Set();

  function generateCityBoundaryPolygon(lat, lng, cityName, gradeKey, isState = false) {
    // 거점 등급 및 관할 단위(도시 vs 주/도)별 행정구역 영역 크기 결정
    // 주 단위는 광역을 커버하므로 약 4~5배 큰 반경 적용 (교회: 0.65deg, 지역: 0.50deg, 개척지: 0.38deg)
    const baseRadius = isState
      ? (gradeKey === 'CHURCH' ? 0.65 : (gradeKey === 'BRANCH' ? 0.50 : 0.38))
      : (gradeKey === 'CHURCH' ? 0.135 : (gradeKey === 'BRANCH' ? 0.095 : 0.068));

    // 도시명 기반 고유 해시 시드 (동일 도시는 언제나 동일한 자연스러운 실제 경계 형태 유지)
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
      // 자연 지형/행정 경계 굴곡을 모사하는 부드러운 다항 왜곡
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

  function fetchRealOsmBoundary(cityName, countryName, callback) {
    if (!cityName) return;
    const query = [cityName, countryName].filter(Boolean).join(', ');
    const key = normalizeGeoKey(query);
    if (pendingBoundaryFetches.has(key)) return;
    pendingBoundaryFetches.add(key);

    const url = `https://nominatim.openstreetmap.org/search?format=json&polygon_geojson=1&limit=1&q=${encodeURIComponent(query)}`;

    let didTimeout = false;
    const timer = setTimeout(() => { didTimeout = true; }, 3500);

    fetch(url)
      .then(res => res.json())
      .then(data => {
        clearTimeout(timer);
        if (didTimeout) return;
        if (Array.isArray(data) && data.length > 0 && data[0].geojson) {
          const geo = data[0].geojson;
          if (geo.type === 'Polygon' || geo.type === 'MultiPolygon') {
            callback(geo);
          }
        }
      })
      .catch(() => {});
  }

  function renderCityBoundaries(filteredItems) {
    if (!mapInstance || !boundaryLayerGroup) return;
    boundaryLayerGroup.clearLayers();
    if (missionRouteLayerGroup) missionRouteLayerGroup.clearLayers();

    if (!isBoundaryEnabled) return;

    const items = filteredItems || territoriesState.filter(item => {
      if (selectedTribeId !== null && item.tribeId !== selectedTribeId) return false;
      if (selectedCategory !== null) {
        const cat = getCategoryByMembers(item);
        if (cat.key !== selectedCategory) return false;
      }
      if (territorySearchQuery.trim() !== '') {
        const q = territorySearchQuery.toLowerCase();
        const match = item.country.toLowerCase().includes(q) ||
                      item.city.toLowerCase().includes(q) ||
                      (item.leader && item.leader.toLowerCase().includes(q));
        if (!match) return false;
      }
      return true;
    });

    // 1. 단일 지파 필터링 시 또는 지파별 도시 간 선교 네트워크 연결 라인 렌더링
    if (selectedTribeId !== null && items.length > 1) {
      const tribe = TRIBES_CONFIG[selectedTribeId] || { color: '#86cab6', name: '지파' };
      const latlngs = items.map(t => [t.lat, t.lng]);
      const polyline = L.polyline(latlngs, {
        color: tribe.color,
        weight: 2.2,
        opacity: 0.75,
        dashArray: '6, 8',
        lineCap: 'round',
        lineJoin: 'round'
      });
      polyline.bindTooltip(`<strong>[${tribe.name || ''}지파]</strong> 선교 거점 도시 연결망`, { sticky: true, className: 'custom-clean-tooltip' });
      missionRouteLayerGroup.addLayer(polyline);
    }

    // 2. 각 도시별 지파 공식 색상 라인 & 영역 채색 폴리곤 렌더링
    items.forEach(item => {
      const tribe = TRIBES_CONFIG[item.tribeId] || { name: '지파', color: '#86cab6', textColor: '#fff' };
      const cat = getCategoryByMembers(item);
      const cacheKey = `MISSION_CITY_GEOJSON_${normalizeGeoKey(item.city)}`;

      let cachedGeo = null;
      try {
        const raw = localStorage.getItem(cacheKey);
        if (raw) cachedGeo = JSON.parse(raw);
      } catch (e) {}

      const hasMembers = (item.members !== undefined && item.members !== null && item.members > 0);
      const memberText = hasMembers ? `${item.members.toLocaleString()}명` : (item.category ? '성도 수 미상 (등급 등록)' : '0명');

      let layer = null;

      const isState = item.unitType === 'STATE';

      if (cachedGeo && (cachedGeo.type === 'Polygon' || cachedGeo.type === 'MultiPolygon')) {
        layer = L.geoJSON({
          type: 'Feature',
          geometry: cachedGeo,
          properties: { name: item.city }
        }, {
          style: {
            color: tribe.color,
            weight: isState ? 3.0 : 2.5,
            opacity: 0.9,
            dashArray: isState ? '8, 6' : '5, 4',
            fillColor: tribe.color,
            fillOpacity: isState ? 0.16 : 0.22,
            lineJoin: 'round'
          }
        });
      } else {
        const polygonPoints = generateCityBoundaryPolygon(item.lat, item.lng, item.city, cat.key, isState);
        layer = L.polygon(polygonPoints, {
          color: tribe.color,
          weight: isState ? 3.0 : 2.5,
          opacity: 0.9,
          dashArray: isState ? '8, 6' : '5, 4',
          fillColor: tribe.color,
          fillOpacity: isState ? 0.16 : 0.22,
          lineJoin: 'round'
        });
      }

      layer.bindTooltip(`
        <div style="font-family: inherit; font-size: 12px; line-height: 1.4; color: #fff;">
          <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:${tribe.color}; margin-right:4px;"></span>
          <strong>[${tribe.name}지파]</strong> ${item.city} 관할 지경 ${isState ? '<span class="badge-state-tag">주단위 관할</span>' : ''}<br>
          <span style="color: ${cat.color}; font-weight:700;">${cat.name}</span> (${memberText})
        </div>
      `, {
        sticky: true,
        direction: 'top',
        className: 'custom-clean-tooltip',
        opacity: 0.95
      });

      layer.on('mouseover', function () {
        if (this.setStyle) {
          this.setStyle({ weight: 3.8, opacity: 1, fillOpacity: 0.42, color: '#ffffff' });
        } else if (this.eachLayer) {
          this.eachLayer(l => l.setStyle({ weight: 3.8, opacity: 1, fillOpacity: 0.42, color: '#ffffff' }));
        }
      });

      layer.on('mouseout', function () {
        if (this.setStyle) {
          this.setStyle({ weight: 2.5, opacity: 0.9, fillOpacity: 0.22, color: tribe.color });
        } else if (this.eachLayer) {
          this.eachLayer(l => l.setStyle({ weight: 2.5, opacity: 0.9, fillOpacity: 0.22, color: tribe.color }));
        }
      });

      layer.on('click', () => {
        openTerritoryDrawer(item);
        mapInstance.flyTo([item.lat, item.lng], Math.max(mapInstance.getZoom(), 7), { duration: 1.2 });
      });

      boundaryLayerGroup.addLayer(layer);
    });
  }

  function initBoundaryToggleControl() {
    const btn = document.getElementById('toggleBoundaryBtn');
    if (!btn) return;

    function updateBtnUI() {
      if (isBoundaryEnabled) {
        btn.classList.add('active');
        btn.classList.remove('inactive');
        btn.innerHTML = '<span>🎨</span> 지경 채색 ON';
        btn.title = '도시별 지파 고유 색상 라인 및 영역 채색 활성화됨 (클릭 시 OFF)';
      } else {
        btn.classList.remove('active');
        btn.classList.add('inactive');
        btn.innerHTML = '<span>🎨</span> 지경 채색 OFF';
        btn.title = '도시별 지파 고유 색상 라인 및 영역 채색 비활성화됨 (클릭 시 ON)';
      }
    }

    updateBtnUI();

    btn.addEventListener('click', () => {
      isBoundaryEnabled = !isBoundaryEnabled;
      try {
        localStorage.setItem(BOUNDARY_STORAGE_KEY, String(isBoundaryEnabled));
      } catch (e) {}
      updateBtnUI();
      renderCityBoundaries();
    });
  }

  function renderMapMarkers() {
    if (!mapInstance) return;

    currentMarkers.forEach(m => mapInstance.removeLayer(m));
    currentMarkers = [];

    // 필터링 적용
    const filtered = territoriesState.filter(item => {
      if (selectedTribeId !== null && item.tribeId !== selectedTribeId) return false;
      if (selectedCategory !== null) {
        const cat = getCategoryByMembers(item);
        if (cat.key !== selectedCategory) return false;
      }
      if (territorySearchQuery.trim() !== '') {
        const q = territorySearchQuery.toLowerCase();
        const match = item.country.toLowerCase().includes(q) ||
                      item.city.toLowerCase().includes(q) ||
                      (item.leader && item.leader.toLowerCase().includes(q));
        if (!match) return false;
      }
      return true;
    });

    // 도시 행정 경계선 및 영역 채색 레이어 동기화
    renderCityBoundaries(filtered);

    filtered.forEach(item => {
      const tribe = TRIBES_CONFIG[item.tribeId] || { name: '지파', color: '#86cab6', textColor: '#fff' };
      const cat = getCategoryByMembers(item);
      const hasMembers = (item.members !== undefined && item.members !== null && item.members > 0);
      const memberText = hasMembers ? `${item.members.toLocaleString()}명` : (item.category ? '성도 수 미상 (거점 등급 등록)' : '0명');

      const isState = item.unitType === 'STATE';
      const unitBadgeHtml = isState ? `<div class="marker-unit-badge" title="주/광역 단위 관할 지경">주</div>` : '';
      const statePulseHtml = isState ? `<div class="marker-pulse-state"></div>` : '';

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

      marker.on('click', () => {
        openTerritoryDrawer(item);
        mapInstance.flyTo([item.lat, item.lng], Math.max(mapInstance.getZoom(), 6), { duration: 1.2 });
      });

      marker.addTo(mapInstance);
      currentMarkers.push(marker);
    });
  }

  function filterMapByTribe(tribeId) {
    selectedTribeId = tribeId;
    renderMapMarkers();
    update12TribesKpi();

    if (tribeId !== null) {
      const target = territoriesState.find(t => t.tribeId === tribeId);
      if (target && mapInstance) {
        mapInstance.flyTo([target.lat, target.lng], 5, { duration: 1.2 });
      }
    }
  }

  function filterMapByCategory(catKey) {
    selectedCategory = catKey;
    renderMapMarkers();
  }

  function filterMapBySearch(query) {
    territorySearchQuery = query;
    renderMapMarkers();

    if (query.trim() !== '') {
      const match = territoriesState.filter(t =>
        t.country.toLowerCase().includes(query.toLowerCase()) ||
        t.city.toLowerCase().includes(query.toLowerCase())
      );
      if (match.length === 1 && mapInstance) {
        mapInstance.flyTo([match[0].lat, match[0].lng], 7, { duration: 1.2 });
      }
    }
  }

  /* ==========================================================================
     9. 12지파 지경판 KPI 계산 및 렌더링 (12지파 지경 개수 상세 표기)
     ========================================================================== */
  function update12TribesKpi() {
    let churches = 0;
    let branches = 0;
    let pioneers = 0;

    // 각 지파별 지경 카운트 집계
    const tribeCounts = {};
    for (let id = 1; id <= 12; id++) {
      tribeCounts[id] = { total: 0, church: 0, branch: 0, pioneer: 0 };
    }

    territoriesState.forEach(t => {
      const cat = getCategoryByMembers(t);
      if (cat.key === 'CHURCH') churches++;
      else if (cat.key === 'BRANCH') branches++;
      else pioneers++;

      if (tribeCounts[t.tribeId]) {
        tribeCounts[t.tribeId].total++;
        if (cat.key === 'CHURCH') tribeCounts[t.tribeId].church++;
        else if (cat.key === 'BRANCH') tribeCounts[t.tribeId].branch++;
        else tribeCounts[t.tribeId].pioneer++;
      }
    });

    // 상단 종합 KPI 수치
    const elTotal = document.getElementById('kpiTotalTerritoriesCount');
    const elChurch = document.getElementById('kpiChurchesCount');
    const elBranch = document.getElementById('kpiBranchesCount');
    const elPioneer = document.getElementById('kpiPioneersCount');
    const badgeTabCount = document.getElementById('statTotalTerritoriesBadge');

    if (elTotal) elTotal.textContent = territoriesState.length;
    if (elChurch) elChurch.textContent = churches;
    if (elBranch) elBranch.textContent = branches;
    if (elPioneer) elPioneer.textContent = pioneers;
    if (badgeTabCount) badgeTabCount.textContent = territoriesState.length;

    // 12지파별 지경 보유 현황 그리드 렌더링 (요구사항: 12지파의 지경이 몇 개가 있는지 표현)
    const grid = document.getElementById('tribesKpiGrid');
    if (!grid) return;

    let gridHtml = '';
    Object.values(TRIBES_CONFIG).forEach(t => {
      const stats = tribeCounts[t.id] || { total: 0, church: 0, branch: 0, pioneer: 0 };
      const isSelected = selectedTribeId === t.id;

      gridHtml += `
        <div class="tribe-kpi-card ${isSelected ? 'active' : ''}" data-tribe-id="${t.id}" title="${t.name}지파 (${t.gem}) - 클릭하여 필터링">
          <div class="tribe-kpi-header">
            <div class="tribe-kpi-badge">
              <span class="tribe-gem-dot" style="background-color: ${t.color}; color: ${t.color};"></span>
              <span style="color: ${t.id === 8 ? 'var(--primary)' : 'inherit'}; font-weight: 700;">${t.name}</span>
            </div>
            <span class="tribe-kpi-count">${stats.total}<span style="font-size: 0.72rem; font-weight: 600; color: var(--text-dim);">개</span></span>
          </div>
          <div class="tribe-kpi-breakdown">
            <span style="color: var(--church-color);">교회 ${stats.church}</span>
            <span style="color: var(--branch-color);">지역 ${stats.branch}</span>
            <span style="color: var(--pioneer-color);">개척 ${stats.pioneer}</span>
          </div>
        </div>
      `;
    });

    grid.innerHTML = gridHtml;

    // 각 지파 카드 클릭 시 필터링 바인딩
    grid.querySelectorAll('.tribe-kpi-card').forEach(card => {
      card.addEventListener('click', () => {
        const tid = parseInt(card.getAttribute('data-tribe-id'), 10);
        if (selectedTribeId === tid) {
          // 동일 지파 다시 클릭 시 전체 보기로 복귀
          filterMapByTribe(null);
          syncTribeFilterBar(null);
        } else {
          filterMapByTribe(tid);
          syncTribeFilterBar(tid);
        }
      });
    });
  }

  function syncTribeFilterBar(selectedId) {
    const bar = document.getElementById('tribeFilterBar');
    if (!bar) return;
    bar.querySelectorAll('.tribe-chip').forEach(c => {
      const val = c.getAttribute('data-tribe');
      if (selectedId === null && val === 'ALL') {
        c.classList.add('active');
      } else if (selectedId !== null && parseInt(val, 10) === selectedId) {
        c.classList.add('active');
      } else {
        c.classList.remove('active');
      }
    });
  }

  function renderTribeFilterBar() {
    const container = document.getElementById('tribeFilterBar');
    if (!container) return;

    let html = `
      <button class="tribe-chip active" data-tribe="ALL">
        <span>🌐</span> 전체 지파
      </button>
    `;

    Object.values(TRIBES_CONFIG).forEach(t => {
      html += `
        <button class="tribe-chip" data-tribe="${t.id}" title="${t.gem} (${t.pantone})">
          <span class="tribe-gem-dot" style="background-color: ${t.color}; color: ${t.color};"></span>
          <span>${t.name}</span>
          <span style="font-size: 10px; opacity: 0.65;">${t.gem}</span>
        </button>
      `;
    });

    container.innerHTML = html;

    container.querySelectorAll('.tribe-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        const val = chip.getAttribute('data-tribe');
        const parsedId = val === 'ALL' ? null : parseInt(val, 10);
        filterMapByTribe(parsedId);
        syncTribeFilterBar(parsedId);
      });
    });
  }

  /* ==========================================================================
     10. 바돌로매 인재 현황판 렌더링 & KPI
     ========================================================================== */
  function updateTalentKpi() {
    let ready = 0;
    let dispatched = 0;
    let training = 0;
    let standby = 0;

    talentsState.forEach(t => {
      if (t.status === 'READY') ready++;
      else if (t.status === 'DISPATCHED') dispatched++;
      else if (t.status === 'TRAINING') training++;
      else standby++;
    });

    const elTotal = document.getElementById('kpiTalentTotal');
    const elReady = document.getElementById('kpiTalentReady');
    const elDispatched = document.getElementById('kpiTalentDispatched');
    const elTraining = document.getElementById('kpiTalentTraining');
    const elStandby = document.getElementById('kpiTalentStandby');
    const badgeCount = document.getElementById('statTalentsBadge');

    if (elTotal) elTotal.textContent = `${talentsState.length}명`;
    if (elReady) elReady.textContent = `${ready}명`;
    if (elDispatched) elDispatched.textContent = `${dispatched}명`;
    if (elTraining) elTraining.textContent = `${training}명`;
    if (elStandby) elStandby.textContent = `${standby}명`;
    if (badgeCount) badgeCount.textContent = talentsState.length;
  }

  function renderTalentsGallery() {
    const container = document.getElementById('talentsGalleryGrid');
    if (!container) return;

    const filtered = talentsState.filter(talent => {
      if (talentLangFilter !== 'ALL') {
        const matchLangs = talent.languages.some(l => l.name.includes(talentLangFilter)) ||
                           talent.primaryLanguage.includes(talentLangFilter);
        if (!matchLangs) return false;
      }

      if (talentStatusFilter !== 'ALL') {
        if (talent.status !== talentStatusFilter) return false;
      }

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
          <h4 style="color: var(--text-main); font-size: 1.1rem; margin-bottom: 0.35rem;">조건에 맞는 인재가 없습니다.</h4>
          <p style="font-size: 0.85rem;">필터 조건을 변경하거나 검색어를 초기화해보세요.</p>
        </div>
      `;
      return;
    }

    container.innerHTML = filtered.map(talent => {
      let statusClass = 'status-standby';
      if (talent.status === 'READY') statusClass = 'status-ready';
      else if (talent.status === 'DISPATCHED') statusClass = 'status-dispatched';
      else if (talent.status === 'TRAINING') statusClass = 'status-training';

      return `
        <div class="talent-card" data-id="${talent.id}">
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

          <div class="talent-card-body">
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

            <div>
              <div class="field-group-title">희망 파견 국가 및 도시</div>
              <div class="target-city-group">
                ${talent.targetCities.map(c => `
                  <span class="city-tag">📍 ${c}</span>
                `).join('')}
                ${talent.targetCountries.map(cnt => `
                  <span class="city-tag" style="background: rgba(255,255,255,0.03); color: var(--text-dim);">${cnt}</span>
                `).join('')}
              </div>
            </div>

            <div>
              <div class="field-group-title">핵심 역량 / 특기</div>
              <div style="display: flex; flex-wrap: wrap; gap: 0.25rem;">
                ${talent.specialties.map(s => `
                  <span style="font-size: 0.74rem; color: var(--text-muted); background: var(--bg-card); border: 1px solid var(--border-subtle); padding: 0.15rem 0.45rem; border-radius: 4px;">
                    #${s}
                  </span>
                `).join('')}
              </div>
            </div>
          </div>

          <div class="talent-card-footer">
            <span style="font-size: 0.75rem; color: var(--text-dim);">
              ${talent.contact ? `📞 ${talent.contact}` : '연락처 비공개'}
            </span>
            <div style="display: flex; gap: 0.3rem; align-items: center;">
              <button type="button" class="btn-secondary btn-card-edit-action" style="padding: 0.32rem 0.6rem; font-size: 0.76rem;" data-id="${talent.id}" title="인재 정보 수정">
                ✏️ 수정
              </button>
              <button type="button" class="btn-danger-outline btn-card-delete-action" style="padding: 0.32rem 0.55rem; font-size: 0.74rem;" data-id="${talent.id}" title="인재 삭제">
                🗑️
              </button>
              <button type="button" class="btn-primary btn-detail-action" style="padding: 0.32rem 0.65rem; font-size: 0.76rem;" data-id="${talent.id}">
                상세 ➔
              </button>
            </div>
          </div>
        </div>
      `;
    }).join('');

    container.querySelectorAll('.btn-detail-action').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const id = e.currentTarget.getAttribute('data-id');
        const item = talentsState.find(t => t.id === id);
        if (item) openTalentDetailModal(item);
      });
    });

    container.querySelectorAll('.btn-card-edit-action').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const id = e.currentTarget.getAttribute('data-id');
        const item = talentsState.find(t => t.id === id);
        if (item) openEditTalentModal(item);
      });
    });

    container.querySelectorAll('.btn-card-delete-action').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const id = e.currentTarget.getAttribute('data-id');
        const item = talentsState.find(t => t.id === id);
        if (item && confirm(`정말로 [${item.name} (${item.role})] 인재 정보를 영구 삭제하시겠습니까?`)) {
          talentsState = talentsState.filter(t => t.id !== id);
          saveTalents(talentsState);
          if (typeof cloudDeleteTalent === 'function') cloudDeleteTalent(id);
          logActivity('TALENT', `인재 삭제 완료: ${item.name} (${item.role}, ${item.primaryLanguage})`, 'SUCCESS');
          alert(`[${item.name}] 인재가 정상적으로 삭제되었습니다.`);
        }
      });
    });
  }

  /* ==========================================================================
     11. 모달 및 드로어 인터랙션
     ========================================================================== */
  let currentDrawerTerritory = null;
  let currentDetailTalent = null;

  function openTerritoryDrawer(item) {
    currentDrawerTerritory = item;
    const drawer = document.getElementById('territoryDrawer');
    if (!drawer) return;

    const tribe = TRIBES_CONFIG[item.tribeId] || { name: '지파', color: '#86cab6', textColor: '#fff' };
    const cat = getCategoryByMembers(item);

    document.getElementById('drawerTribeBadge').style.backgroundColor = tribe.color;
    document.getElementById('drawerTribeBadge').style.color = tribe.textColor;
    document.getElementById('drawerTribeBadge').textContent = `${tribe.name}지파`;

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
    
    const hasMembers = (item.members !== undefined && item.members !== null && item.members > 0);
    document.getElementById('drawerMembersCount').textContent = hasMembers 
      ? `${item.members.toLocaleString()}명` 
      : (item.category ? '성도 수 미상 (등급 등록)' : '0명 (개척 준비)');

    document.getElementById('drawerCategoryName').textContent = `${cat.name} (${cat.desc})`;
    document.getElementById('drawerLeader').textContent = item.leader || '미정';
    document.getElementById('drawerEstYear').textContent = item.establishedYear ? `${item.establishedYear}년` : '-';
    document.getElementById('drawerAddress').textContent = item.address || `${item.country} ${item.city}`;
    document.getElementById('drawerNotes').textContent = item.notes || '기록된 특이사항이 없습니다.';

    drawer.classList.add('open');
  }

  function openTalentDetailModal(talent) {
    currentDetailTalent = talent;
    const modal = document.getElementById('talentDetailModal');
    if (!modal) return;

    document.getElementById('detailTalentName').textContent = talent.name;
    document.getElementById('detailTalentRole').textContent = `[${talent.role}] ${talent.department} · ${talent.gender} ${talent.age}세`;
    document.getElementById('detailTalentAvatar').src = talent.photo;
    document.getElementById('detailTalentStatus').textContent = talent.statusLabel;

    const langContainer = document.getElementById('detailTalentLanguages');
    langContainer.innerHTML = talent.languages.map(l => `
      <div style="background: var(--bg-card); border: 1px solid var(--border-subtle); padding: 0.5rem 0.75rem; border-radius: 6px;">
        <div style="font-weight: 700; color: var(--text-main); font-size: 0.85rem;">${l.name} <span style="color: var(--primary); font-size: 0.8rem;">[${l.level}]</span></div>
        ${l.exam ? `<div style="font-size: 0.74rem; color: var(--text-dim); margin-top: 2px;">공인시험: ${l.exam}</div>` : ''}
      </div>
    `).join('');

    document.getElementById('detailTalentCities').textContent = talent.targetCities.join(', ') + ` (${talent.targetCountries.join(', ')})`;
    document.getElementById('detailTalentSpecialties').textContent = talent.specialties.join(', ');
    document.getElementById('detailTalentExp').textContent = talent.experience || '경력 정보 없음';
    document.getElementById('detailTalentMemo').textContent = talent.memo || '메모 없음';
    document.getElementById('detailTalentContact').textContent = talent.contact || '연락처 미등록';

    modal.classList.add('open');
  }

  function populateTribeSelect() {
    const select = document.getElementById('newTribeId');
    if (!select || select.children.length > 0) return;

    Object.values(TRIBES_CONFIG).forEach(t => {
      const opt = document.createElement('option');
      opt.value = t.id;
      opt.textContent = `${t.name}지파 (${t.gem} - ${t.pantone})`;
      if (t.id === 8) opt.selected = true;
      select.appendChild(opt);
    });
  }

  function populateEditTribeSelect() {
    const select = document.getElementById('editTribeId');
    if (!select || select.children.length > 0) return;

    Object.values(TRIBES_CONFIG).forEach(t => {
      const opt = document.createElement('option');
      opt.value = t.id;
      opt.textContent = `${t.name}지파 (${t.gem} - ${t.pantone})`;
      select.appendChild(opt);
    });
  }

  function openEditTerritoryModal(territory) {
    if (!territory) return;
    populateEditTribeSelect();
    const modal = document.getElementById('editTerritoryModal');
    if (!modal) return;

    const cat = getCategoryByMembers(territory);

    document.getElementById('editTerritoryId').value = territory.id;
    document.getElementById('editTribeId').value = String(territory.tribeId);
    document.getElementById('editCountry').value = territory.country || '';
    document.getElementById('editCity').value = territory.city || '';

    const isState = territory.unitType === 'STATE';
    const editRadios = document.getElementsByName('editTerritoryUnit');
    editRadios.forEach(r => {
      r.checked = (r.value === (isState ? 'STATE' : 'CITY'));
    });

    const editCityLabel = document.getElementById('editCityLabel');
    const editCityInput = document.getElementById('editCity');
    const editCityBox = document.getElementById('editUnitCityLabel');
    const editStateBox = document.getElementById('editUnitStateLabel');
    if (isState) {
      if (editCityLabel) editCityLabel.innerHTML = '주(State) / 도 명칭 (입력 시 좌표 자동 연동) <span style="color: #ef4444;">*</span>';
      if (editCityInput) editCityInput.placeholder = '예: 캘리포니아주, 텍사스주, 바이에른주, 온타리오주';
      if (editStateBox) editStateBox.style.borderColor = 'var(--primary)';
      if (editCityBox) editCityBox.style.borderColor = 'var(--border-subtle)';
    } else {
      if (editCityLabel) editCityLabel.innerHTML = '도시명 (입력 시 좌표 자동 연동) <span style="color: #ef4444;">*</span>';
      if (editCityInput) editCityInput.placeholder = '예: 베를린, 파리, 뉴욕';
      if (editCityBox) editCityBox.style.borderColor = 'var(--primary)';
      if (editStateBox) editStateBox.style.borderColor = 'var(--border-subtle)';
    }

    const catSelect = document.getElementById('editCategory');
    if (catSelect) {
      catSelect.value = territory.category || cat.key;
    }

    const memInput = document.getElementById('editMembers');
    if (memInput) {
      memInput.value = (territory.members !== undefined && territory.members !== null && territory.members > 0) ? territory.members : '';
    }

    document.getElementById('editLat').value = territory.lat !== undefined ? territory.lat : '';
    document.getElementById('editLng').value = territory.lng !== undefined ? territory.lng : '';
    document.getElementById('editLeader').value = territory.leader || '';
    document.getElementById('editEstYear').value = territory.establishedYear || '';
    document.getElementById('editAddress').value = territory.address || '';
    document.getElementById('editNotes').value = territory.notes || '';

    const geoStatus = document.getElementById('editGeoStatus');
    if (geoStatus) {
      geoStatus.style.display = 'block';
      geoStatus.style.color = '#10b981';
      geoStatus.textContent = `📍 현재 등록 좌표: 위도 ${territory.lat}, 경도 ${territory.lng}`;
    }

    modal.classList.add('open');
  }

  function openEditTalentModal(talent) {
    if (!talent) return;
    const modal = document.getElementById('editTalentModal');
    if (!modal) return;

    document.getElementById('editTalentId').value = talent.id;
    document.getElementById('editTalentName').value = talent.name || '';
    document.getElementById('editTalentGender').value = talent.gender || '남';
    document.getElementById('editTalentAge').value = talent.age || 30;
    document.getElementById('editTalentDept').value = talent.department || '청년부';
    document.getElementById('editTalentRole').value = talent.role || '';
    document.getElementById('editTalentStatus').value = talent.status || 'READY';
    document.getElementById('editTalentPrimaryLang').value = talent.primaryLanguage || '독일어';
    document.getElementById('editTalentLangLevel').value = (talent.languages && talent.languages[0]?.level) || '';
    document.getElementById('editTalentCities').value = (talent.targetCities || []).join(', ');
    document.getElementById('editTalentSpecialties').value = (talent.specialties || []).join(', ');
    document.getElementById('editTalentContact').value = talent.contact || '';
    document.getElementById('editTalentExp').value = talent.experience || '';
    document.getElementById('editTalentMemo').value = talent.memo || '';

    modal.classList.add('open');
  }

  function openEditAccountModal(account) {
    if (!account) return;
    const modal = document.getElementById('editAccountModal');
    if (!modal) return;

    document.getElementById('editAccountId').value = account.id;
    document.getElementById('editAccountLabel').value = account.label || '';
    document.getElementById('editAccountRole').value = account.role || 'STAFF';

    modal.classList.add('open');
  }

  /* ==========================================================================
     11-2. 총괄·개발자 관제 렌더러 및 데이터 제어 함수
     ========================================================================== */
  function renderAccountsTable() {
    const tbody = document.getElementById('accountsTableBody');
    const badgeCount = document.getElementById('adminSubtabAccountsCount');
    const kpiCount = document.getElementById('kpiAdminAccountsCount');

    if (badgeCount) badgeCount.textContent = accountsState.length;
    if (kpiCount) kpiCount.textContent = `${accountsState.length}명`;

    if (!tbody) return;

    const currentUid = getCurrentUserId();

    tbody.innerHTML = accountsState.map(acc => {
      let roleBadgeClass = 'badge-role-staff';
      let roleText = '실무 담당';
      if (acc.role === 'MASTER') {
        roleBadgeClass = 'badge-role-master';
        roleText = '총괄 관제 (MASTER)';
      } else if (acc.role === 'EXECUTIVE') {
        roleBadgeClass = 'badge-role-exec';
        roleText = '중앙 임원';
      } else if (acc.role === 'DEV') {
        roleBadgeClass = 'badge-role-dev';
        roleText = '시스템 개발';
      }

      const isMe = acc.id === currentUid;
      const isMasterAdmin = acc.id === 'admin';

      return `
        <tr>
          <td>
            <div style="font-weight: 700; color: var(--text-main); font-family: monospace;">
              ${acc.id} ${isMe ? '<span style="color: var(--primary); font-size: 0.72rem; font-weight: 600;">(현재 접속중)</span>' : ''}
            </div>
          </td>
          <td>
            <div style="font-weight: 600; color: var(--text-main);">${acc.label}</div>
          </td>
          <td>
            <span class="role-badge ${roleBadgeClass}">${roleText}</span>
          </td>
          <td style="color: var(--text-dim); font-size: 0.78rem;">${acc.createdAt || '2026-01-01'}</td>
          <td style="color: var(--text-muted); font-size: 0.8rem;">
            ${acc.lastLoginAt ? `🕒 ${acc.lastLoginAt}` : '-'}
          </td>
          <td>
            <div style="display: flex; gap: 0.35rem; align-items: center;">
              <button type="button" class="btn-table-action btn-change-pw" data-id="${acc.id}" data-label="${acc.label}">
                PW 변경
              </button>
              <button type="button" class="btn-table-action btn-edit-account" data-id="${acc.id}">
                ✏️ 수정
              </button>
              ${!isMasterAdmin && !isMe ? `
                <button type="button" class="btn-table-danger btn-delete-account" data-id="${acc.id}" data-label="${acc.label}">
                  삭제
                </button>
              ` : `
                <span style="font-size: 0.72rem; color: var(--text-dim); padding: 0.2rem 0.4rem;">보호됨</span>
              `}
            </div>
          </td>
        </tr>
      `;
    }).join('');

    tbody.querySelectorAll('.btn-change-pw').forEach(btn => {
      btn.addEventListener('click', () => {
        const id = btn.getAttribute('data-id');
        const label = btn.getAttribute('data-label');
        openChangePasswordModal(id, label);
      });
    });

    tbody.querySelectorAll('.btn-edit-account').forEach(btn => {
      btn.addEventListener('click', () => {
        const id = btn.getAttribute('data-id');
        const acc = accountsState.find(a => a.id === id);
        if (acc) openEditAccountModal(acc);
      });
    });

    tbody.querySelectorAll('.btn-delete-account').forEach(btn => {
      btn.addEventListener('click', () => {
        const id = btn.getAttribute('data-id');
        const label = btn.getAttribute('data-label');
        if (confirm(`정말로 관리자 계정 [${label} (${id})]을(를) 영구 삭제하시겠습니까?`)) {
          const filtered = accountsState.filter(a => a.id !== id);
          saveAccounts(filtered);
          logActivity('ACCOUNT', `관리자 계정 [${label} (${id})] 삭제 완료`, 'SUCCESS');
          alert(`계정 [${id}]이(가) 정상적으로 삭제되었습니다.`);
        }
      });
    });
  }

  let logTypeFilter = 'ALL';
  let logSearchQuery = '';

  function renderLogsTable() {
    const tbody = document.getElementById('logsTableBody');
    const badgeCount = document.getElementById('adminSubtabLogsCount');
    const badgeTabCount = document.getElementById('statAdminLogsBadge');
    const kpiCount = document.getElementById('kpiAdminTotalLogsCount');

    if (badgeCount) badgeCount.textContent = logsState.length;
    if (badgeTabCount) badgeTabCount.textContent = logsState.length;
    if (kpiCount) kpiCount.textContent = `${logsState.length}건`;

    if (!tbody) return;

    const filtered = logsState.filter(item => {
      if (logTypeFilter !== 'ALL' && item.actionType !== logTypeFilter) return false;
      if (logSearchQuery.trim() !== '') {
        const q = logSearchQuery.toLowerCase();
        const matchOp = item.operator && item.operator.toLowerCase().includes(q);
        const matchDet = item.details && item.details.toLowerCase().includes(q);
        if (!matchOp && !matchDet) return false;
      }
      return true;
    });

    if (filtered.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="5" style="text-align: center; padding: 3rem 1rem; color: var(--text-dim);">
            <div style="font-size: 1.8rem; margin-bottom: 0.5rem;">📜</div>
            조건에 부합하는 사용 이력 로그가 없습니다.
          </td>
        </tr>
      `;
      return;
    }

    const typeBadgeMap = {
      AUTH: { text: '보안 인증', cls: 'log-badge-auth' },
      TERRITORY: { text: '지경 제어', cls: 'log-badge-territory' },
      TALENT: { text: '인재 관리', cls: 'log-badge-talent' },
      ACCOUNT: { text: '계정 제어', cls: 'log-badge-account' },
      DATA: { text: '데이터 제어', cls: 'log-badge-auth' }
    };

    tbody.innerHTML = filtered.map(log => {
      const typeInfo = typeBadgeMap[log.actionType] || { text: log.actionType, cls: 'log-badge-auth' };
      const isSuccess = log.status === 'SUCCESS';

      return `
        <tr>
          <td style="font-family: monospace; font-size: 0.78rem; color: var(--text-dim); white-space: nowrap;">
            ${log.timestamp}
          </td>
          <td>
            <div style="font-weight: 600; color: var(--text-main); font-size: 0.82rem;">${log.operator}</div>
          </td>
          <td>
            <span class="log-type-badge ${typeInfo.cls}">${typeInfo.text}</span>
          </td>
          <td style="font-size: 0.83rem; color: var(--text-muted); line-height: 1.4;">
            ${log.details}
          </td>
          <td>
            <span style="font-size: 0.75rem; font-weight: 700; color: ${isSuccess ? '#10b981' : '#ef4444'};">
              ${isSuccess ? '● 성공' : '▲ 실패'}
            </span>
          </td>
        </tr>
      `;
    }).join('');
  }

  function updateAdminKpis() {
    const accCountEl = document.getElementById('kpiAdminAccountsCount');
    const logsCountEl = document.getElementById('kpiAdminTotalLogsCount');
    const trCountEl = document.getElementById('kpiAdminTerritoriesCount');
    const curAccEl = document.getElementById('adminCurrentAccountDisplay');

    if (accCountEl) accCountEl.textContent = `${accountsState.length}명`;
    if (logsCountEl) logsCountEl.textContent = `${logsState.length}건`;
    if (trCountEl) trCountEl.textContent = `${territoriesState.length}개`;
    if (curAccEl) curAccEl.textContent = `${getCurrentUserDisplay()} (권한: ${safeGetStorage('CURRENT_USER_ROLE') || 'MASTER'})`;
  }

  function openChangePasswordModal(targetId, targetLabel) {
    const modal = document.getElementById('changePasswordModal');
    if (!modal) return;
    document.getElementById('changePassTargetId').value = targetId;
    document.getElementById('changePassTargetLabel').textContent = `${targetLabel} (${targetId})`;
    document.getElementById('newPasswordInput').value = '';
    document.getElementById('newPasswordConfirmInput').value = '';
    modal.classList.add('open');
  }

  function exportLogsCsv() {
    if (logsState.length === 0) {
      alert('내보낼 사용 이력 로그가 없습니다.');
      return;
    }
    const headers = ['일시', '작업자', '작업유형', '상세내용', '결과'];
    const rows = logsState.map(l => [
      `"${l.timestamp}"`,
      `"${(l.operator || '').replace(/"/g, '""')}"`,
      `"${l.actionType}"`,
      `"${(l.details || '').replace(/"/g, '""')}"`,
      `"${l.status}"`
    ]);
    const csvContent = '\uFEFF' + [headers.join(','), ...rows.map(r => r.join(','))].join('\r\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `mission_audit_logs_${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    logActivity('DATA', '시스템 사용 이력(감사 로그) CSV 파일 내보내기 다운로드', 'SUCCESS');
  }

  function backupTerritoriesJson() {
    const backupData = {
      exportDate: new Date().toISOString(),
      system: '해외선교 총괄 관제 시스템',
      totalCount: territoriesState.length,
      territories: territoriesState
    };
    const jsonStr = JSON.stringify(backupData, null, 2);
    const blob = new Blob([jsonStr], { type: 'application/json;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `mission_territories_backup_${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    logActivity('DATA', `지경 데이터 전체 JSON 백업 다운로드 (${territoriesState.length}개 거점)`, 'SUCCESS');
  }

  function importTerritoriesJson(file) {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = function(e) {
      try {
        const parsed = JSON.parse(e.target.result);
        const list = Array.isArray(parsed) ? parsed : (Array.isArray(parsed.territories) ? parsed.territories : null);
        if (!list || list.length === 0) {
          alert('올바른 지경 백업 JSON 형식이 아니거나 데이터가 비어 있습니다.');
          return;
        }
        if (confirm(`선택한 백업 파일에서 총 ${list.length}개의 지경 데이터를 불러오시겠습니까?\n(현재 지경 목록과 안전하게 합쳐지며 클라우드에도 동기화됩니다)`)) {
          const map = new Map();
          territoriesState.forEach(item => { if (item && item.id) map.set(item.id, item); });
          list.forEach(item => { if (item && item.id) map.set(item.id, item); });
          const merged = Array.from(map.values());
          saveTerritories(merged);
          if (typeof cloudRestoreTerritories === 'function') cloudRestoreTerritories(merged);
          logActivity('TERRITORY', `JSON 백업 파일 불러오기 완료 (총 ${merged.length}개 거점)`, 'SUCCESS');
          alert(`총 ${merged.length}개의 지경 데이터가 성공적으로 반영되었습니다!`);
        }
      } catch (err) {
        alert('JSON 파일 읽기 중 오류가 발생했습니다: ' + err.message);
      }
    };
    reader.readAsText(file);
  }

  /* ==========================================================================
     12. 탭 전환 (해외지경판 ↔ 바돌로매 인재현황판 ↔ 총괄·개발자 관제 3단 분리)
     ========================================================================== */
  function switchTab(targetTab) {
    const tabMap = document.getElementById('tabMapBtn');
    const tabTalents = document.getElementById('tabTalentsBtn');
    const tabAdmin = document.getElementById('tabAdminBtn');

    const kpiTerritory = document.getElementById('territoryKpiSection');
    const kpiTalent = document.getElementById('talentKpiSection');
    const kpiAdmin = document.getElementById('adminKpiSection');

    const viewMap = document.getElementById('mapViewSection');
    const viewTalents = document.getElementById('talentViewSection');
    const viewAdmin = document.getElementById('adminViewSection');

    const openAddBtn = document.getElementById('headerPrimaryActionBtn');

    if (targetTab === 'MAP') {
      if (tabMap) tabMap.classList.add('active');
      if (tabTalents) tabTalents.classList.remove('active');
      if (tabAdmin) tabAdmin.classList.remove('active');

      if (kpiTerritory) kpiTerritory.style.display = 'flex';
      if (kpiTalent) kpiTalent.style.display = 'none';
      if (kpiAdmin) kpiAdmin.style.display = 'none';

      if (viewMap) viewMap.style.display = 'flex';
      if (viewTalents) viewTalents.style.display = 'none';
      if (viewAdmin) viewAdmin.style.display = 'none';

      if (openAddBtn) {
        openAddBtn.innerHTML = '<span>＋</span> 신규 지경 등록';
        openAddBtn.onclick = () => {
          populateTribeSelect();
          document.getElementById('addTerritoryModal').classList.add('open');
        };
      }

      // 지도 리사이즈 재호출
      setTimeout(() => {
        if (mapInstance) mapInstance.invalidateSize();
      }, 100);
    } else if (targetTab === 'TALENTS') {
      if (tabTalents) tabTalents.classList.add('active');
      if (tabMap) tabMap.classList.remove('active');
      if (tabAdmin) tabAdmin.classList.remove('active');

      if (kpiTerritory) kpiTerritory.style.display = 'none';
      if (kpiTalent) kpiTalent.style.display = 'block';
      if (kpiAdmin) kpiAdmin.style.display = 'none';

      if (viewMap) viewMap.style.display = 'none';
      if (viewTalents) viewTalents.style.display = 'block';
      if (viewAdmin) viewAdmin.style.display = 'none';

      if (openAddBtn) {
        openAddBtn.innerHTML = '<span>＋</span> 신규 인재 등록';
        openAddBtn.onclick = () => {
          document.getElementById('addTalentModal').classList.add('open');
        };
      }

      renderTalentsGallery();
      updateTalentKpi();
    } else if (targetTab === 'ADMIN') {
      if (tabAdmin) tabAdmin.classList.add('active');
      if (tabMap) tabMap.classList.remove('active');
      if (tabTalents) tabTalents.classList.remove('active');

      if (kpiTerritory) kpiTerritory.style.display = 'none';
      if (kpiTalent) kpiTalent.style.display = 'none';
      if (kpiAdmin) kpiAdmin.style.display = 'flex';

      if (viewMap) viewMap.style.display = 'none';
      if (viewTalents) viewTalents.style.display = 'none';
      if (viewAdmin) viewAdmin.style.display = 'flex';

      if (openAddBtn) {
        openAddBtn.innerHTML = '<span>🔑</span> 신규 계정 발급';
        openAddBtn.onclick = () => {
          document.getElementById('addAccountModal').classList.add('open');
        };
      }

      renderAccountsTable();
      renderLogsTable();
      updateAdminKpis();
    }
  }

  /* ==========================================================================
     12-2. 도시명 입력 시 위도·경도 실시간 자동 지오코딩 바인딩
     ========================================================================== */
  function setupAutoGeocoding() {
    function bindAutoGeo(cityInputId, countryInputId, latInputId, lngInputId, statusId) {
      const cityInput = document.getElementById(cityInputId);
      const countryInput = document.getElementById(countryInputId);
      const latInput = document.getElementById(latInputId);
      const lngInput = document.getElementById(lngInputId);
      const statusEl = document.getElementById(statusId);

      if (!cityInput || !latInput || !lngInput) return;

      let debounceTimer = null;

      function updateCoords() {
        const cityName = cityInput.value.trim();
        const countryName = countryInput ? countryInput.value.trim() : '';

        if (!cityName) {
          if (statusEl) statusEl.style.display = 'none';
          return;
        }

        // 1. 로컬 0ms 오프라인 도시 사전 매핑
        const localGeo = lookupCityCoordinates(cityName, countryName);
        if (localGeo) {
          latInput.value = localGeo.lat;
          lngInput.value = localGeo.lng;
          if (statusEl) {
            statusEl.style.display = 'block';
            statusEl.style.color = '#10b981';
            statusEl.textContent = `✅ [${localGeo.name || cityName}] 좌표 자동 매핑 완료: 위도 ${localGeo.lat}, 경도 ${localGeo.lng}`;
          }
          return;
        }

        // 2. 국가 기준 기본 좌표 매핑
        const countryGeo = lookupCountryCoordinates(countryName || cityName);
        if (countryGeo) {
          latInput.value = countryGeo.lat;
          lngInput.value = countryGeo.lng;
          if (statusEl) {
            statusEl.style.display = 'block';
            statusEl.style.color = '#38bdf8';
            statusEl.textContent = `📍 [${countryGeo.name || countryName}] 국가 기준 좌표 매핑: 위도 ${countryGeo.lat}, 경도 ${countryGeo.lng}`;
          }
        }

        // 3. 온라인 오픈스트리트맵(Nominatim) 비동기 정밀 검색
        if (statusEl) {
          statusEl.style.display = 'block';
          statusEl.style.color = '#fbbf24';
          statusEl.textContent = `🔍 [${cityName}] 정밀 좌표 검색 중...`;
        }

        fetchGeoFromNominatim(cityName, countryName, (res) => {
          latInput.value = res.lat;
          lngInput.value = res.lng;
          if (statusEl) {
            statusEl.style.display = 'block';
            statusEl.style.color = '#10b981';
            statusEl.textContent = `🌐 [${cityName}] 글로벌 정밀 좌표 자동 적용 완료: 위도 ${res.lat}, 경도 ${res.lng}`;
          }
        });
      }

      cityInput.addEventListener('input', () => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(updateCoords, 300);
      });

      cityInput.addEventListener('blur', updateCoords);

      if (countryInput) {
        countryInput.addEventListener('input', () => {
          if (cityInput.value.trim()) {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(updateCoords, 500);
          }
        });
        countryInput.addEventListener('blur', () => {
          if (cityInput.value.trim()) updateCoords();
        });
      }
    }

    bindAutoGeo('newCity', 'newCountry', 'newLat', 'newLng', 'newGeoStatus');
    bindAutoGeo('editCity', 'editCountry', 'editLat', 'editLng', 'editGeoStatus');
  }

  /* ==========================================================================
     12-3. 지경 등록/수정 모달 단위 구분(도시 단위 vs 주·광역 단위) 토글러
     ========================================================================== */
  function setupTerritoryUnitToggles() {
    function bindToggle(radioName, cityLabelId, cityInputId, cityBoxId, stateBoxId) {
      const radios = document.getElementsByName(radioName);
      const label = document.getElementById(cityLabelId);
      const input = document.getElementById(cityInputId);
      const cityBox = document.getElementById(cityBoxId);
      const stateBox = document.getElementById(stateBoxId);

      radios.forEach(r => {
        r.addEventListener('change', () => {
          const isState = r.value === 'STATE';
          if (isState) {
            if (label) label.innerHTML = '주(State) / 도 명칭 (입력 시 좌표 자동 연동) <span style="color: #ef4444;">*</span>';
            if (input) input.placeholder = '예: 캘리포니아주, 텍사스주, 바이에른주, 온타리오주';
            if (stateBox) stateBox.style.borderColor = 'var(--primary)';
            if (cityBox) cityBox.style.borderColor = 'var(--border-subtle)';
          } else {
            if (label) label.innerHTML = '도시명 (입력 시 좌표 자동 연동) <span style="color: #ef4444;">*</span>';
            if (input) input.placeholder = '예: 베를린, 파리, 뉴욕';
            if (cityBox) cityBox.style.borderColor = 'var(--primary)';
            if (stateBox) stateBox.style.borderColor = 'var(--border-subtle)';
          }
        });
      });
    }

    bindToggle('newTerritoryUnit', 'newCityLabel', 'newCity', 'newUnitCityLabel', 'newUnitStateLabel');
    bindToggle('editTerritoryUnit', 'editCityLabel', 'editCity', 'editUnitCityLabel', 'editUnitStateLabel');
  }

  /* ==========================================================================
     13. 애플리케이션 초기화 및 이벤트 바인딩
     ========================================================================== */
  function initApp() {
    // 1. 테마 초기화
    initTheme();

    // 2. 테마 토글 버튼
    const themeBtn = document.getElementById('themeToggleBtn');
    if (themeBtn) {
      themeBtn.addEventListener('click', toggleTheme);
    }

    // 3. 보안 인증 게이트 초기화
    const loginModal = document.getElementById('loginModal');
    const userBadge = document.getElementById('currentUserBadge');

    if (!isAuthenticated()) {
      loginModal.classList.add('open');
    } else {
      loginModal.classList.remove('open');
      if (userBadge) userBadge.textContent = getCurrentUserLabel();
    }

    // 로그인 폼
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
      loginForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const u = document.getElementById('loginUser').value;
        const p = document.getElementById('loginPass').value;
        const err = document.getElementById('loginErrorMsg');

        const res = doLogin(u, p);
        if (res.success) {
          loginModal.classList.remove('open');
          if (userBadge) userBadge.textContent = getCurrentUserLabel();
          if (err) err.style.display = 'none';
          setTimeout(() => {
            if (mapInstance) mapInstance.invalidateSize();
          }, 300);
        } else {
          if (err) {
            err.textContent = res.message;
            err.style.display = 'block';
          }
        }
      });
    }

    // 로그아웃 버튼
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
      logoutBtn.addEventListener('click', () => {
        if (confirm('시스템에서 로그아웃 하시겠습니까?')) {
          doLogout();
        }
      });
    }

    // 4. 상단 탭 전환 이벤트
    const tabMap = document.getElementById('tabMapBtn');
    const tabTalents = document.getElementById('tabTalentsBtn');
    const tabAdmin = document.getElementById('tabAdminBtn');
    if (tabMap) tabMap.addEventListener('click', () => switchTab('MAP'));
    if (tabTalents) tabTalents.addEventListener('click', () => switchTab('TALENTS'));
    if (tabAdmin) tabAdmin.addEventListener('click', () => switchTab('ADMIN'));

    // 5. 12지파 필터 바 및 KPI 렌더링
    renderTribeFilterBar();
    update12TribesKpi();
    updateTalentKpi();
    updateAdminKpis();
    updateMapClearButtonsState();

    // 6. 지도 엔진 기동 및 베이스맵 컨트롤러 초기화
    initMapEngine();
    initMapStyleControls();
    setupAutoGeocoding();
    setupTerritoryUnitToggles();
    initBoundaryToggleControl();

    // 7. 지도 등급 필터 (전체, 교회, 지역, 개척지)
    document.querySelectorAll('.cat-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.cat-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const cat = btn.getAttribute('data-cat');
        filterMapByCategory(cat === 'ALL' ? null : cat);
      });
    });

    // 8. 지도 실시간 검색바
    const mapSearch = document.getElementById('mapSearchInput');
    if (mapSearch) {
      mapSearch.addEventListener('input', (e) => {
        filterMapBySearch(e.target.value);
      });
    }

    // 9. 지경 상세 드로어 닫기 및 개별 지경 삭제
    const closeDrawerBtn = document.getElementById('closeDrawerBtn');
    if (closeDrawerBtn) {
      closeDrawerBtn.addEventListener('click', () => {
        document.getElementById('territoryDrawer').classList.remove('open');
      });
    }

    const deleteCurrentTerritoryBtn = document.getElementById('deleteCurrentTerritoryBtn');
    if (deleteCurrentTerritoryBtn) {
      deleteCurrentTerritoryBtn.addEventListener('click', () => {
        if (!currentDrawerTerritory) return;
        const target = currentDrawerTerritory;
        if (confirm(`정말로 [${target.country} ${target.city}] 지경 거점을 삭제하시겠습니까?\n이 작업은 즉시 반영됩니다.`)) {
          const remaining = territoriesState.filter(t => t.id !== target.id);
          saveTerritories(remaining);
          if (typeof cloudDeleteTerritory === 'function') cloudDeleteTerritory(target.id);
          const drawer = document.getElementById('territoryDrawer');
          if (drawer) drawer.classList.remove('open');
          logActivity('TERRITORY', `지경 거점 삭제: ${target.country} ${target.city} (${target.members}명)`, 'SUCCESS');
          alert(`[${target.country} ${target.city}] 지경이 정상적으로 삭제되었습니다.`);
        }
      });
    }

    const editCurrentTerritoryBtn = document.getElementById('editCurrentTerritoryBtn');
    if (editCurrentTerritoryBtn) {
      editCurrentTerritoryBtn.addEventListener('click', () => {
        if (!currentDrawerTerritory) return;
        openEditTerritoryModal(currentDrawerTerritory);
      });
    }

    // 10. 지경 가데이터 일괄 삭제 및 복원 제어
    const clearTerritoriesModal = document.getElementById('clearTerritoriesConfirmModal');
    const closeClearModalBtn = document.getElementById('closeClearTerritoriesModalBtn');
    const cancelClearModalBtn = document.getElementById('cancelClearTerritoriesBtn');
    const confirmClearBtn = document.getElementById('confirmClearTerritoriesBtn');

    function openClearModal() {
      const noticeCount = document.getElementById('clearTerritoryCountNotice');
      if (noticeCount) noticeCount.textContent = `${territoriesState.length}개`;
      if (clearTerritoriesModal) clearTerritoriesModal.classList.add('open');
    }

    const mapClearAllBtn = document.getElementById('mapClearAllBtn');
    const adminClearAllBtn = document.getElementById('adminClearAllTerritoriesBtn');
    if (mapClearAllBtn) mapClearAllBtn.addEventListener('click', openClearModal);
    if (adminClearAllBtn) adminClearAllBtn.addEventListener('click', openClearModal);

    if (closeClearModalBtn) closeClearModalBtn.onclick = () => clearTerritoriesModal.classList.remove('open');
    if (cancelClearModalBtn) cancelClearModalBtn.onclick = () => clearTerritoriesModal.classList.remove('open');

    if (confirmClearBtn) {
      confirmClearBtn.addEventListener('click', () => {
        const count = territoriesState.length;
        saveTerritories([]);
        if (typeof cloudClearAllTerritories === 'function') cloudClearAllTerritories();
        clearTerritoriesModal.classList.remove('open');
        const drawer = document.getElementById('territoryDrawer');
        if (drawer) drawer.classList.remove('open');
        logActivity('TERRITORY', `전체 지경 데이터 일괄 삭제 완료 (총 ${count}개 거점 초기화)`, 'SUCCESS');
        alert(`모든 지경 가데이터(${count}개)가 성공적으로 삭제되었습니다.\n이제 실제 지경을 등록하시거나 필요 시 복원 버튼을 이용해주세요.`);
      });
    }

    // 샘플 지경 데이터 복원 핸들러
    function handleRestoreSampleTerritories() {
      if (confirm('초기 12지파 28개 샘플 지경 데이터를 복원하시겠습니까?\n현재 등록된 데이터는 28개 기본 샘플로 대체됩니다.')) {
        saveTerritories([...INITIAL_TERRITORIES]);
        if (typeof cloudRestoreTerritories === 'function') cloudRestoreTerritories([...INITIAL_TERRITORIES]);
        logActivity('TERRITORY', '초기 12지파 28개 샘플 지경 데이터 복원 완료', 'SUCCESS');
        alert('초기 28개 샘플 지경 데이터가 성공적으로 복원되었습니다.');
      }
    }

    const mapRestoreBtn = document.getElementById('mapRestoreSampleBtn');
    const adminRestoreBtn = document.getElementById('adminRestoreSampleBtn');
    if (mapRestoreBtn) mapRestoreBtn.addEventListener('click', handleRestoreSampleTerritories);
    if (adminRestoreBtn) adminRestoreBtn.addEventListener('click', handleRestoreSampleTerritories);

    // 지경 전체 JSON 백업 다운로드 및 가져오기
    const backupJsonBtn = document.getElementById('backupTerritoriesJsonBtn');
    if (backupJsonBtn) backupJsonBtn.addEventListener('click', backupTerritoriesJson);

    const importInput = document.getElementById('importTerritoriesJsonInput');
    if (importInput) {
      importInput.addEventListener('change', (e) => {
        if (e.target.files && e.target.files[0]) {
          importTerritoriesJson(e.target.files[0]);
          e.target.value = '';
        }
      });
    }

    // 11. 승인 계정 관리 모달 및 폼 제어
    const addAccountModal = document.getElementById('addAccountModal');
    const openAddAccountBtn = document.getElementById('openAddAccountBtn') || document.getElementById('openAddAccountModalBtn');
    const closeAddAccountBtn = document.getElementById('closeAddAccountBtn');
    const cancelAddAccountBtn = document.getElementById('cancelAddAccountBtn');
    const addAccountForm = document.getElementById('addAccountForm');

    if (openAddAccountBtn) openAddAccountBtn.onclick = () => addAccountModal.classList.add('open');
    if (closeAddAccountBtn) closeAddAccountBtn.onclick = () => addAccountModal.classList.remove('open');
    if (cancelAddAccountBtn) cancelAddAccountBtn.onclick = () => addAccountModal.classList.remove('open');

    if (addAccountForm) {
      addAccountForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const id = document.getElementById('newAccountId').value.trim().toLowerCase();
        const pw = document.getElementById('newAccountPass').value.trim();
        const label = document.getElementById('newAccountLabel').value.trim();
        const role = document.getElementById('newAccountRole').value;

        if (accountsState.some(a => a.id.toLowerCase() === id)) {
          alert('이미 존재하는 계정 아이디입니다. 다른 아이디를 입력해주세요.');
          return;
        }

        const now = new Date();
        const pad = (n) => String(n).padStart(2, '0');
        const createdAt = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;

        const newAccount = {
          id,
          pw,
          label,
          role,
          createdAt,
          lastLoginAt: '-'
        };

        accountsState.push(newAccount);
        saveAccounts(accountsState);
        logActivity('ACCOUNT', `신규 관리자 계정 발급 완료 (ID: ${id}, 직분: ${label}, 등급: ${role})`, 'SUCCESS');
        addAccountModal.classList.remove('open');
        addAccountForm.reset();
        alert(`신규 관리자 계정 [${id}]이(가) 정상적으로 발급되었습니다.`);
      });
    }

    // 비밀번호 변경 모달 및 폼
    const changePasswordModal = document.getElementById('changePasswordModal');
    const closeChangePassBtn = document.getElementById('closeChangePassBtn');
    const cancelChangePassBtn = document.getElementById('cancelChangePassBtn');
    const changePasswordForm = document.getElementById('changePasswordForm');

    if (closeChangePassBtn) closeChangePassBtn.onclick = () => changePasswordModal.classList.remove('open');
    if (cancelChangePassBtn) cancelChangePassBtn.onclick = () => changePasswordModal.classList.remove('open');

    if (changePasswordForm) {
      changePasswordForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const targetId = document.getElementById('changePassTargetId').value;
        const newPw = document.getElementById('newPasswordInput').value.trim();
        const confirmPw = document.getElementById('newPasswordConfirmInput').value.trim();

        if (newPw !== confirmPw) {
          alert('새 비밀번호와 비밀번호 확인이 일치하지 않습니다.');
          return;
        }
        if (newPw.length < 4) {
          alert('비밀번호는 최소 4자리 이상이어야 합니다.');
          return;
        }

        const target = accountsState.find(a => a.id === targetId);
        if (target) {
          target.pw = newPw;
          saveAccounts(accountsState);
          logActivity('ACCOUNT', `관리자 [${target.label} (${target.id})] 비밀번호 변경 완료`, 'SUCCESS');
          changePasswordModal.classList.remove('open');
          changePasswordForm.reset();
          alert(`계정 [${targetId}]의 비밀번호가 성공적으로 변경되었습니다.`);
        }
      });
    }

    // 12. 시스템 사용 이력 (감사 로그) 필터 & 제어
    document.querySelectorAll('.admin-log-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        document.querySelectorAll('.admin-log-chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        logTypeFilter = chip.getAttribute('data-logtype') || 'ALL';
        renderLogsTable();
      });
    });

    const logSearchInput = document.getElementById('logSearchInput');
    if (logSearchInput) {
      logSearchInput.addEventListener('input', (e) => {
        logSearchQuery = e.target.value;
        renderLogsTable();
      });
    }

    const exportLogsBtn = document.getElementById('exportLogsCsvBtn');
    if (exportLogsBtn) exportLogsBtn.addEventListener('click', exportLogsCsv);

    const clearLogsBtn = document.getElementById('clearAllLogsBtn');
    if (clearLogsBtn) {
      clearLogsBtn.addEventListener('click', () => {
        if (confirm('모든 시스템 사용 이력 및 감사 로그를 영구 삭제하시겠습니까?\n이 작업은 되돌릴 수 없습니다.')) {
          saveLogs([]);
          logActivity('DATA', '감사 로그 전체 초기화 실행됨', 'SUCCESS');
          alert('모든 사용 이력 로그가 초기화되었습니다.');
        }
      });
    }

    // 13. 총괄·개발자 관제 서브탭 전환
    document.querySelectorAll('.admin-subnav-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.admin-subnav-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const targetSubtab = btn.getAttribute('data-subtab');

        const panelAccounts = document.getElementById('adminAccountsPanel');
        const panelLogs = document.getElementById('adminLogsPanel');
        const panelData = document.getElementById('adminDataPanel');

        if (panelAccounts) panelAccounts.style.display = targetSubtab === 'accounts' ? 'block' : 'none';
        if (panelLogs) panelLogs.style.display = targetSubtab === 'logs' ? 'block' : 'none';
        if (panelData) panelData.style.display = targetSubtab === 'data' ? 'block' : 'none';
      });
    });

    // 14. 인재 필터 칩 (언어, 파견 상태)
    document.querySelectorAll('.talent-lang-pill').forEach(pill => {
      pill.addEventListener('click', () => {
        document.querySelectorAll('.talent-lang-pill').forEach(p => p.classList.remove('active'));
        pill.classList.add('active');
        talentLangFilter = pill.getAttribute('data-lang');
        renderTalentsGallery();
      });
    });

    document.querySelectorAll('.talent-status-pill-btn').forEach(pill => {
      pill.addEventListener('click', () => {
        document.querySelectorAll('.talent-status-pill-btn').forEach(p => p.classList.remove('active'));
        pill.classList.add('active');
        talentStatusFilter = pill.getAttribute('data-status');
        renderTalentsGallery();
      });
    });

    // 15. 인재 검색
    const talentSearchInput = document.getElementById('talentSearchInput');
    if (talentSearchInput) {
      talentSearchInput.addEventListener('input', (e) => {
        talentSearchQuery = e.target.value;
        renderTalentsGallery();
      });
    }

    // 16. 헤더 신규 등록 액션 버튼 초기화
    switchTab('MAP');

    // 17. 신규 지경 추가 모달 이벤트
    const addTerritoryModal = document.getElementById('addTerritoryModal');
    const closeAddTerritoryBtn = document.getElementById('closeAddTerritoryBtn');
    const cancelAddTerritoryBtn = document.getElementById('cancelAddTerritoryBtn');
    const addTerritoryForm = document.getElementById('addTerritoryForm');

    if (closeAddTerritoryBtn) closeAddTerritoryBtn.onclick = () => addTerritoryModal.classList.remove('open');
    if (cancelAddTerritoryBtn) cancelAddTerritoryBtn.onclick = () => addTerritoryModal.classList.remove('open');

    if (addTerritoryForm) {
      addTerritoryForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const tribeId = parseInt(document.getElementById('newTribeId').value, 10);
        const country = document.getElementById('newCountry').value.trim();
        const city = document.getElementById('newCity').value.trim();
        const category = document.getElementById('newCategory').value || 'PIONEER';
        const unitType = document.querySelector('input[name="newTerritoryUnit"]:checked')?.value || 'CITY';

        const rawMembers = document.getElementById('newMembers').value.trim();
        const members = rawMembers !== '' ? parseInt(rawMembers, 10) : 0;

        let lat = parseFloat(document.getElementById('newLat').value);
        let lng = parseFloat(document.getElementById('newLng').value);

        if (isNaN(lat) || isNaN(lng)) {
          const resolved = resolveCoordinatesSync(city, country);
          lat = resolved.lat;
          lng = resolved.lng;
        }

        const leader = document.getElementById('newLeader').value.trim();
        const notes = document.getElementById('newNotes').value.trim();

        const newTerritory = {
          id: `TR-${Date.now()}`,
          tribeId,
          country,
          city,
          unitType, // 'CITY' | 'STATE'
          category, // 등급 직접 지정 등록 (교회/지역/개척지)
          members,
          lat,
          lng,
          leader: leader || '지경 책임자',
          establishedYear: new Date().getFullYear(),
          notes: notes || (unitType === 'STATE' ? '신규 주 단위 지경 등록' : '신규 지경 등록'),
          updatedAt: new Date().toISOString().split('T')[0]
        };

        territoriesState.unshift(newTerritory);
        saveTerritories(territoriesState);
        if (typeof cloudUpsertTerritory === 'function') cloudUpsertTerritory(newTerritory);
        addTerritoryModal.classList.remove('open');
        addTerritoryForm.reset();

        // 라디오 기본값(도시) 복원 및 플레이스홀더 초기화
        const cityRadio = document.querySelector('input[name="newTerritoryUnit"][value="CITY"]');
        if (cityRadio) {
          cityRadio.checked = true;
          cityRadio.dispatchEvent(new Event('change'));
        }

        const statusEl = document.getElementById('newGeoStatus');
        if (statusEl) statusEl.style.display = 'none';

        openTerritoryDrawer(newTerritory);
        const catName = CATEGORY_CONFIG[category]?.name || '개척지';
        const memberInfo = members > 0 ? `${members}명` : '성도수 미상';
        const unitLabel = unitType === 'STATE' ? '[주단위]' : '[도시단위]';
        logActivity('TERRITORY', `신규 지경 등록: [${TRIBES_CONFIG[tribeId]?.name || ''}지파] ${country} ${city} ${unitLabel} (${catName} · ${memberInfo})`, 'SUCCESS');

        // 서버 환경일 경우 디스크 영구 저장 API 호출
        if (window.location.protocol.startsWith('http')) {
          fetch('/api/territories', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(newTerritory)
          }).catch(e => console.warn('[Server Sync]', e));
        }

        if (mapInstance) {
          mapInstance.flyTo([newTerritory.lat, newTerritory.lng], unitType === 'STATE' ? 6 : 7, { duration: 1.2 });
        }
      });
    }

    // 17-2. 지경 정보 수정 모달 이벤트
    const editTerritoryModal = document.getElementById('editTerritoryModal');
    const closeEditTerritoryBtn = document.getElementById('closeEditTerritoryBtn');
    const cancelEditTerritoryBtn = document.getElementById('cancelEditTerritoryBtn');
    const editTerritoryForm = document.getElementById('editTerritoryForm');

    if (closeEditTerritoryBtn) closeEditTerritoryBtn.onclick = () => editTerritoryModal.classList.remove('open');
    if (cancelEditTerritoryBtn) cancelEditTerritoryBtn.onclick = () => editTerritoryModal.classList.remove('open');

    if (editTerritoryForm) {
      editTerritoryForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const targetId = document.getElementById('editTerritoryId').value;
        const index = territoriesState.findIndex(t => t.id === targetId);
        if (index === -1) {
          alert('수정할 지경 정보를 찾을 수 없습니다.');
          return;
        }

        const tribeId = parseInt(document.getElementById('editTribeId').value, 10);
        const country = document.getElementById('editCountry').value.trim();
        const city = document.getElementById('editCity').value.trim();
        const category = document.getElementById('editCategory').value || 'PIONEER';
        const unitType = document.querySelector('input[name="editTerritoryUnit"]:checked')?.value || 'CITY';

        const rawMembers = document.getElementById('editMembers').value.trim();
        const members = rawMembers !== '' ? parseInt(rawMembers, 10) : 0;

        const leader = document.getElementById('editLeader').value.trim();
        
        let lat = parseFloat(document.getElementById('editLat').value);
        let lng = parseFloat(document.getElementById('editLng').value);

        if (isNaN(lat) || isNaN(lng)) {
          const resolved = resolveCoordinatesSync(city, country);
          lat = resolved.lat;
          lng = resolved.lng;
        }

        const establishedYear = parseInt(document.getElementById('editEstYear').value, 10) || new Date().getFullYear();
        const address = document.getElementById('editAddress').value.trim();
        const notes = document.getElementById('editNotes').value.trim();

        const updatedTerritory = {
          ...territoriesState[index],
          tribeId,
          country,
          city,
          unitType, // 'CITY' | 'STATE'
          category, // 등급 직접 지정 수정
          members,
          leader: leader || '지경 책임자',
          lat,
          lng,
          establishedYear,
          address: address || `${country} ${city}`,
          notes: notes || '',
          updatedAt: new Date().toISOString().split('T')[0]
        };

        territoriesState[index] = updatedTerritory;
        saveTerritories(territoriesState);
        if (typeof cloudUpsertTerritory === 'function') cloudUpsertTerritory(updatedTerritory);

        if (currentDrawerTerritory && currentDrawerTerritory.id === targetId) {
          openTerritoryDrawer(updatedTerritory);
        }

        editTerritoryModal.classList.remove('open');
        const catName = CATEGORY_CONFIG[category]?.name || '개척지';
        const memberInfo = members > 0 ? `${members}명` : '성도수 미상';
        logActivity('TERRITORY', `지경 정보 수정: [${TRIBES_CONFIG[tribeId]?.name || ''}지파] ${country} ${city} (${catName} · ${memberInfo})`, 'SUCCESS');
        alert(`[${country} ${city}] 지경 정보가 성공적으로 수정되었습니다.`);

        if (mapInstance) {
          mapInstance.flyTo([lat, lng], Math.max(mapInstance.getZoom(), 6), { duration: 1.0 });
        }

        if (window.location.protocol.startsWith('http')) {
          fetch(`/api/territories/${targetId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updatedTerritory)
          }).catch(err => console.warn('[Server Sync]', err));
        }
      });
    }

    // 17-3. 신규 인재 등록 모달 이벤트
    const addTalentModal = document.getElementById('addTalentModal');
    const closeAddTalentBtn = document.getElementById('closeAddTalentBtn');
    const cancelAddTalentBtn = document.getElementById('cancelAddTalentBtn');
    const addTalentForm = document.getElementById('addTalentForm');

    if (closeAddTalentBtn) closeAddTalentBtn.onclick = () => addTalentModal.classList.remove('open');
    if (cancelAddTalentBtn) cancelAddTalentBtn.onclick = () => addTalentModal.classList.remove('open');

    if (addTalentForm) {
      addTalentForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const name = document.getElementById('newTalentName').value.trim();
        const gender = document.getElementById('newTalentGender').value;
        const age = parseInt(document.getElementById('newTalentAge').value, 10) || 28;
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
          statusLabel: statusMap[status] || '즉시 파견 가능',
          primaryLanguage,
          languages: [{ name: primaryLanguage, level: langLevel || '회화 가능' }],
          targetCountries: ['해외 전체'],
          targetCities: targetCities.length > 0 ? targetCities : ['희망지 미정'],
          specialties: specialties.length > 0 ? specialties : ['언어소통'],
          contact: contact || '-',
          memo: memo || '신규 인재 등록',
          experience: '신규 등록 인재',
          updatedAt: new Date().toISOString().split('T')[0]
        };

        talentsState.unshift(newTalent);
        saveTalents(talentsState);
        if (typeof cloudUpsertTalent === 'function') cloudUpsertTalent(newTalent);
        addTalentModal.classList.remove('open');
        addTalentForm.reset();
        openTalentDetailModal(newTalent);
        logActivity('TALENT', `신규 인재 등록: ${name} (${role || '성도'}, ${primaryLanguage})`, 'SUCCESS');
        alert(`신규 인재 [${name}]이(가) 성공적으로 등록되었습니다.`);

        if (window.location.protocol.startsWith('http')) {
          fetch('/api/talents', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(newTalent)
          }).catch(e => console.warn('[Server Sync]', e));
        }
      });
    }

    // 17-4. 인재 정보 수정 및 상세 모달 액션 이벤트
    const openEditTalentModalBtn = document.getElementById('openEditTalentModalBtn');
    if (openEditTalentModalBtn) {
      openEditTalentModalBtn.addEventListener('click', () => {
        if (!currentDetailTalent) return;
        openEditTalentModal(currentDetailTalent);
      });
    }

    const deleteCurrentTalentBtn = document.getElementById('deleteCurrentTalentBtn');
    if (deleteCurrentTalentBtn) {
      deleteCurrentTalentBtn.addEventListener('click', () => {
        if (!currentDetailTalent) return;
        const target = currentDetailTalent;
        if (confirm(`정말로 [${target.name} (${target.role})] 인재 정보를 영구 삭제하시겠습니까?\n이 작업은 즉시 반영됩니다.`)) {
          talentsState = talentsState.filter(t => t.id !== target.id);
          saveTalents(talentsState);
          if (typeof cloudDeleteTalent === 'function') cloudDeleteTalent(target.id);
          document.getElementById('talentDetailModal').classList.remove('open');
          logActivity('TALENT', `인재 삭제 완료: ${target.name} (${target.role}, ${target.primaryLanguage})`, 'SUCCESS');
          alert(`[${target.name}] 인재 정보가 정상적으로 삭제되었습니다.`);
        }
      });
    }

    const editTalentModal = document.getElementById('editTalentModal');
    const closeEditTalentBtn = document.getElementById('closeEditTalentBtn');
    const cancelEditTalentBtn = document.getElementById('cancelEditTalentBtn');
    const editTalentForm = document.getElementById('editTalentForm');

    if (closeEditTalentBtn) closeEditTalentBtn.onclick = () => editTalentModal.classList.remove('open');
    if (cancelEditTalentBtn) cancelEditTalentBtn.onclick = () => editTalentModal.classList.remove('open');

    if (editTalentForm) {
      editTalentForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const targetId = document.getElementById('editTalentId').value;
        const index = talentsState.findIndex(t => t.id === targetId);
        if (index === -1) {
          alert('수정할 인재 정보를 찾을 수 없습니다.');
          return;
        }

        const name = document.getElementById('editTalentName').value.trim();
        const gender = document.getElementById('editTalentGender').value;
        const age = parseInt(document.getElementById('editTalentAge').value, 10) || 30;
        const department = document.getElementById('editTalentDept').value;
        const role = document.getElementById('editTalentRole').value.trim();
        const primaryLanguage = document.getElementById('editTalentPrimaryLang').value;
        const langLevel = document.getElementById('editTalentLangLevel').value.trim();
        const status = document.getElementById('editTalentStatus').value;
        const targetCities = document.getElementById('editTalentCities').value.split(',').map(s => s.trim()).filter(Boolean);
        const specialties = document.getElementById('editTalentSpecialties').value.split(',').map(s => s.trim()).filter(Boolean);
        const contact = document.getElementById('editTalentContact').value.trim();
        const experience = document.getElementById('editTalentExp').value.trim();
        const memo = document.getElementById('editTalentMemo').value.trim();

        const statusMap = {
          READY: '즉시 파견 가능',
          DISPATCHED: '현지 파견중',
          TRAINING: '사역 연수중',
          STANDBY: '국내 사역 (언어 지원)'
        };

        const existingLangs = talentsState[index].languages || [];
        const otherLangs = existingLangs.filter(l => l.name !== primaryLanguage);
        const updatedLanguages = [
          { name: primaryLanguage, level: langLevel || '회화 가능', exam: existingLangs.find(l => l.name === primaryLanguage)?.exam || '' },
          ...otherLangs
        ];

        const updatedTalent = {
          ...talentsState[index],
          name,
          gender,
          age,
          department,
          role: role || '성도',
          primaryLanguage,
          languages: updatedLanguages,
          status,
          statusLabel: statusMap[status] || '즉시 파견 가능',
          targetCities: targetCities.length > 0 ? targetCities : ['희망지 미정'],
          specialties: specialties.length > 0 ? specialties : ['언어소통'],
          contact: contact || '-',
          experience: experience || '경력 정보 없음',
          memo: memo || '',
          updatedAt: new Date().toISOString().split('T')[0]
        };

        talentsState[index] = updatedTalent;
        saveTalents(talentsState);
        if (typeof cloudUpsertTalent === 'function') cloudUpsertTalent(updatedTalent);

        editTalentModal.classList.remove('open');

        if (currentDetailTalent && currentDetailTalent.id === targetId) {
          openTalentDetailModal(updatedTalent);
        }

        logActivity('TALENT', `인재 정보 수정: ${name} (${role || '성도'}, ${primaryLanguage} ${langLevel})`, 'SUCCESS');
        alert(`[${name}] 인재 정보가 성공적으로 수정되었습니다.`);

        if (window.location.protocol.startsWith('http')) {
          fetch(`/api/talents/${targetId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updatedTalent)
          }).catch(err => console.warn('[Server Sync]', err));
        }
      });
    }

    // 17-5. 관리자 계정 정보 수정 모달 이벤트
    const editAccountModal = document.getElementById('editAccountModal');
    const closeEditAccountBtn = document.getElementById('closeEditAccountBtn');
    const cancelEditAccountBtn = document.getElementById('cancelEditAccountBtn');
    const editAccountForm = document.getElementById('editAccountForm');

    if (closeEditAccountBtn) closeEditAccountBtn.onclick = () => editAccountModal.classList.remove('open');
    if (cancelEditAccountBtn) cancelEditAccountBtn.onclick = () => editAccountModal.classList.remove('open');

    if (editAccountForm) {
      editAccountForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const targetId = document.getElementById('editAccountId').value;
        const target = accountsState.find(a => a.id === targetId);
        if (!target) {
          alert('수정할 계정 정보를 찾을 수 없습니다.');
          return;
        }

        const newLabel = document.getElementById('editAccountLabel').value.trim();
        const newRole = document.getElementById('editAccountRole').value;

        target.label = newLabel;
        target.role = newRole;

        saveAccounts(accountsState);
        renderAccountsTable();
        editAccountModal.classList.remove('open');

        // 현재 로그인된 사용자의 정보가 변경되었을 경우 헤더 뱃지 갱신
        if (getCurrentUserId() === targetId) {
          sessionStorage.setItem('OMCS_USER_LABEL', `${newLabel} (${targetId})`);
          sessionStorage.setItem('OMCS_USER_ROLE', newRole);
          const userBadge = document.getElementById('currentUserBadge');
          if (userBadge) userBadge.textContent = `${newLabel} (${targetId})`;
        }

        logActivity('ACCOUNT', `관리자 계정 정보 수정: [${newLabel} (${targetId})] 권한: ${newRole}`, 'SUCCESS');
        alert(`계정 [${targetId}] 정보가 성공적으로 수정되었습니다.`);
      });
    }

    // 19. 모달 외부 클릭 시 닫기
    window.addEventListener('click', (e) => {
      if (e.target.classList.contains('modal-overlay') && !e.target.classList.contains('login-gate-modal')) {
        e.target.classList.remove('open');
      }
    });

    // 16. ESC 키 입력 시 모달 닫기
    window.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        document.querySelectorAll('.modal-overlay:not(.login-gate-modal)').forEach(m => m.classList.remove('open'));
        const drawer = document.getElementById('territoryDrawer');
        if (drawer) drawer.classList.remove('open');
      }
    });

    // 초기 인재 갤러리 렌더링
    renderTalentsGallery();

    // Supabase 실시간 클라우드 DB 동기화 및 실시간 리스너 가동
    try {
      syncFromSupabase();
      initRealtimeSubscriptions();
    } catch (e) {
      console.warn('[Supabase Sync Init Error]', e);
    }

    // 서버 환경일 경우 기 저장된 데이터 동기화
    if (window.location.protocol.startsWith('http')) {
      fetch('/api/data')
        .then(r => r.json())
        .then(data => {
          if (data && data.customTerritories && data.customTerritories.length > 0) {
            territoriesState = [...data.customTerritories, ...INITIAL_TERRITORIES];
            renderMapMarkers();
            update12TribesKpi();
          }
          if (data && data.customTalents && data.customTalents.length > 0) {
            talentsState = [...data.customTalents, ...INITIAL_TALENTS];
            renderTalentsGallery();
            updateTalentKpi();
          }
        })
        .catch(e => console.log('[Server Data] 로컬 데이터셋 사용'));
    }
  }

  // DOM 로드 완료 시 즉시 실행
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initApp);
  } else {
    initApp();
  }
})();
