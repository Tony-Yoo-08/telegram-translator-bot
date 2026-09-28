/* ==========================================================================
   신천지 12지파 공식 색상 코드표 (PANTONE Solid Coated 기준)
   ========================================================================== */
export const TRIBES_CONFIG = {
  1: {
    id: 1,
    name: '요한',
    gem: '녹보석',
    color: '#009651',
    pantone: 'PANTONE 340C',
    rgb: 'rgb(0, 150, 81)',
    textColor: '#ffffff'
  },
  2: {
    id: 2,
    name: '베드로',
    gem: '벽옥',
    color: '#00a0e9',
    pantone: 'PANTONE 2925C',
    rgb: 'rgb(0, 160, 233)',
    textColor: '#ffffff'
  },
  3: {
    id: 3,
    name: '부산야고보',
    gem: '남보석',
    color: '#1d2088',
    pantone: 'PANTONE 2758C',
    rgb: 'rgb(29, 32, 136)',
    textColor: '#ffffff'
  },
  4: {
    id: 4,
    name: '안드레',
    gem: '옥수',
    color: '#59c3e1',
    pantone: 'PANTONE 637C',
    rgb: 'rgb(89, 195, 225)',
    textColor: '#0f172a'
  },
  5: {
    id: 5,
    name: '다대오',
    gem: '홍마노',
    color: '#eb6120',
    pantone: 'PANTONE 7579C',
    rgb: 'rgb(235, 97, 32)',
    textColor: '#ffffff'
  },
  6: {
    id: 6,
    name: '빌립',
    gem: '홍보석',
    color: '#d7005b',
    pantone: 'PANTONE 214C',
    rgb: 'rgb(215, 0, 91)',
    textColor: '#ffffff'
  },
  7: {
    id: 7,
    name: '시몬',
    gem: '황옥',
    color: '#fdd000',
    pantone: 'PANTONE 116C',
    rgb: 'rgb(253, 208, 0)',
    textColor: '#0f172a'
  },
  8: {
    id: 8,
    name: '바돌로매',
    gem: '녹옥',
    color: '#86cab6',
    pantone: 'PANTONE 564C',
    rgb: 'rgb(134, 202, 182)',
    textColor: '#0f172a'
  },
  9: {
    id: 9,
    name: '마태',
    gem: '담황옥',
    color: '#e39300',
    pantone: 'PANTONE 7564C',
    rgb: 'rgb(227, 147, 0)',
    textColor: '#ffffff'
  },
  10: {
    id: 10,
    name: '맛디아',
    gem: '비취옥',
    color: '#6FBA2C',
    pantone: 'PANTONE 368C',
    rgb: 'rgb(111, 186, 44)',
    textColor: '#ffffff'
  },
  11: {
    id: 11,
    name: '서울야고보',
    gem: '청옥',
    color: '#005dac',
    pantone: 'PANTONE 2728C',
    rgb: 'rgb(0, 93, 172)',
    textColor: '#ffffff'
  },
  12: {
    id: 12,
    name: '도마',
    gem: '자정',
    color: '#7f1084',
    pantone: 'PANTONE 2612C',
    rgb: 'rgb(127, 16, 132)',
    textColor: '#ffffff'
  }
};

/* ==========================================================================
   지경 구분 기준 (성도 수 기준)
   - 개척지: 0명 (신규 개척/확장 대상지)
   - 지역: 50명 이상 (준교회)
   - 교회: 300명 이상 (정식 교회)
   ========================================================================== */
export const CATEGORY_CONFIG = {
  PIONEER: {
    key: 'PIONEER',
    name: '개척지',
    badgeClass: 'badge-pioneer',
    minMembers: 0,
    maxMembers: 49,
    color: '#38bdf8', // Sky Cyan
    bgLight: 'rgba(56, 189, 248, 0.15)',
    icon: 'compass',
    desc: '신규 확장 목표 지역 (성도 0명~49명)'
  },
  BRANCH: {
    key: 'BRANCH',
    name: '지역',
    badgeClass: 'badge-branch',
    minMembers: 50,
    maxMembers: 299,
    color: '#fbbf24', // Amber
    bgLight: 'rgba(251, 191, 36, 0.15)',
    icon: 'flag',
    desc: '준교회 형태의 거점 (성도 50명 이상)'
  },
  CHURCH: {
    key: 'CHURCH',
    name: '교회',
    badgeClass: 'badge-church',
    minMembers: 300,
    color: '#10b981', // Emerald
    bgLight: 'rgba(16, 185, 129, 0.15)',
    icon: 'church',
    desc: '자립 교회 (성도 300명 이상)'
  }
};

export function getCategoryByMembers(itemOrCount) {
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
   12지파 전 세계 도시 단위 초기 지경 데이터 (고화질 도시 좌표 포함)
   ========================================================================== */
export const INITIAL_TERRITORIES = [
  // 바돌로매지파 (주요 담당 지경 및 전 세계 거점)
  {
    id: 'TR-BAR-01',
    tribeId: 8,
    country: '독일',
    countryCode: 'DE',
    city: '프랑크푸르트',
    lat: 50.1109,
    lng: 8.6821,
    members: 420,
    leader: '김바돌 사역자',
    establishedYear: 2017,
    address: 'Frankfurt am Main, Hessen, Germany',
    phone: '+49 69 1234 5678',
    notes: '유럽 거점 교회로 성장, 정기 온라인 세미나 진행 및 현지인 사역 활성화',
    updatedAt: '2026-09-15'
  },
  {
    id: 'TR-BAR-02',
    tribeId: 8,
    country: '독일',
    countryCode: 'DE',
    city: '베를린',
    lat: 52.5200,
    lng: 13.4050,
    members: 145,
    leader: '이은혜 전도사',
    establishedYear: 2021,
    address: 'Mitte, Berlin, Germany',
    phone: '+49 30 8765 4321',
    notes: '독일 수도 중심 사역 거점, 대학생 청년 중심 성도 구성',
    updatedAt: '2026-09-18'
  },
  {
    id: 'TR-BAR-03',
    tribeId: 8,
    country: '스위스',
    countryCode: 'CH',
    city: '취리히',
    lat: 47.3769,
    lng: 8.5417,
    members: 68,
    leader: '박요한 사역자',
    establishedYear: 2023,
    address: 'Zurich Center, Switzerland',
    phone: '+41 44 234 5678',
    notes: '스위스 금융 중심지, 전문직 대상 언어 스터디 및 성경 세미나 거점',
    updatedAt: '2026-08-20'
  },
  {
    id: 'TR-BAR-04',
    tribeId: 8,
    country: '오스트리아',
    countryCode: 'AT',
    city: '비엔나',
    lat: 48.2082,
    lng: 16.3738,
    members: 0,
    leader: '파견 준비중',
    establishedYear: 2026,
    address: 'Innere Stadt, Wien, Austria',
    phone: '-',
    notes: '2026년 하반기 신규 개척 목표 도시. 독일어 및 현지 문화 가능 인재 파견 대기',
    updatedAt: '2026-09-24'
  },
  {
    id: 'TR-BAR-05',
    tribeId: 8,
    country: '체코',
    countryCode: 'CZ',
    city: '프라하',
    lat: 50.0755,
    lng: 14.4378,
    members: 0,
    leader: '사전 조사팀 배정',
    establishedYear: 2026,
    address: 'Prague 1, Czech Republic',
    phone: '-',
    notes: '동유럽 교두보 개척지. 영어 및 체코어 가능 인재 수요 조사 중',
    updatedAt: '2026-09-20'
  },

  // 요한지파 (녹보석 #009651)
  {
    id: 'TR-JOH-01',
    tribeId: 1,
    country: '미국',
    countryCode: 'US',
    city: '로스앤젤레스',
    lat: 34.0522,
    lng: -118.2437,
    members: 680,
    leader: '정요한 총무',
    establishedYear: 2014,
    address: 'Wilshire Blvd, Los Angeles, CA, USA',
    phone: '+1 213 555 0199',
    notes: '미주 서부 최대 거점 교회, 다민족 성도 활성화',
    updatedAt: '2026-09-10'
  },
  {
    id: 'TR-JOH-02',
    tribeId: 1,
    country: '미국',
    countryCode: 'US',
    city: '샌프란시스코',
    lat: 37.7749,
    lng: -122.4194,
    members: 120,
    leader: '최진우 강사',
    establishedYear: 2022,
    address: 'Market St, San Francisco, CA, USA',
    phone: '+1 415 555 0142',
    notes: '실리콘밸리 연계 IT 인재 및 다국적 청년층 전도 활발',
    updatedAt: '2026-08-30'
  },
  {
    id: 'TR-JOH-03',
    tribeId: 1,
    country: '캐나다',
    countryCode: 'CA',
    city: '밴쿠버',
    lat: 49.2827,
    lng: -123.1207,
    members: 0,
    leader: '답사단 구성',
    establishedYear: 2026,
    address: 'Downtown, Vancouver, BC, Canada',
    phone: '-',
    notes: '캐나다 서부 개척 예정지',
    updatedAt: '2026-09-12'
  },
  {
    id: 'TR-JOH-04',
    tribeId: 1,
    country: '미국',
    countryCode: 'US',
    city: '텍사스주',
    unitType: 'STATE',
    lat: 31.9686,
    lng: -99.9018,
    members: 280,
    leader: '김요한 사역자',
    establishedYear: 2023,
    address: 'Texas, United States',
    phone: '+1 512 555 0188',
    notes: '미주 남부 텍사스주 광역 주 단위 관할 지경 (댈러스, 오스틴, 휴스턴 등 연계 관할)',
    updatedAt: '2026-09-15'
  },

  // 베드로지파 (벽옥 #00a0e9)
  {
    id: 'TR-PET-01',
    tribeId: 2,
    country: '호주',
    countryCode: 'AU',
    city: '시드니',
    lat: -33.8688,
    lng: 151.2093,
    members: 390,
    leader: '강베드로 사역자',
    establishedYear: 2016,
    address: 'George St, Sydney NSW, Australia',
    phone: '+61 2 9234 5678',
    notes: '오세아니아 본부 교회, 호주 및 뉴질랜드 전역 선교 지원',
    updatedAt: '2026-09-01'
  },
  {
    id: 'TR-PET-02',
    tribeId: 2,
    country: '호주',
    countryCode: 'AU',
    city: '멜버른',
    lat: -37.8136,
    lng: 144.9631,
    members: 85,
    leader: '신영민 전도사',
    establishedYear: 2023,
    address: 'Swanston St, Melbourne VIC, Australia',
    phone: '+61 3 9876 5432',
    notes: '다문화 예술 도시 거점, 청년 중심 지역 모임 성장세',
    updatedAt: '2026-08-15'
  },

  // 부산야고보지파 (남보석 #1d2088)
  {
    id: 'TR-BJA-01',
    tribeId: 3,
    country: '영국',
    countryCode: 'GB',
    city: '런던',
    lat: 51.5074,
    lng: -0.1278,
    members: 310,
    leader: '문야고보 사역자',
    establishedYear: 2018,
    address: 'Holborn, London, UK',
    phone: '+44 20 7946 0912',
    notes: '영국 정식 교회 인가, 유럽 북부권 선교 허브',
    updatedAt: '2026-09-14'
  },
  {
    id: 'TR-BJA-02',
    tribeId: 3,
    country: '아일랜드',
    countryCode: 'IE',
    city: '더블린',
    lat: 53.3498,
    lng: -6.2603,
    members: 0,
    leader: '개척 준비단',
    establishedYear: 2026,
    address: 'Grafton St, Dublin, Ireland',
    phone: '-',
    notes: '아일랜드 신규 개척 목표지, 영국 런던 교회에서 주 1회 순회 지원',
    updatedAt: '2026-09-22'
  },

  // 안드레지파 (옥수 #59c3e1)
  {
    id: 'TR-AND-01',
    tribeId: 4,
    country: '일본',
    countryCode: 'JP',
    city: '도쿄',
    lat: 35.6762,
    lng: 139.6503,
    members: 450,
    leader: '조안드레 사역자',
    establishedYear: 2015,
    address: 'Shinjuku-ku, Tokyo, Japan',
    phone: '+81 3 5321 1111',
    notes: '일본 수도 거점 교회, 온라인 말씀 세미나 수강생 급증',
    updatedAt: '2026-09-11'
  },
  {
    id: 'TR-AND-02',
    tribeId: 4,
    country: '일본',
    countryCode: 'JP',
    city: '오사카',
    lat: 34.6937,
    lng: 135.5023,
    members: 180,
    leader: '김경호 전도사',
    establishedYear: 2020,
    address: 'Namba, Osaka, Japan',
    phone: '+81 6 6211 2222',
    notes: '간사이 중심 지역, 현지 일본인 사역자 배출 중',
    updatedAt: '2026-09-05'
  },

  // 다대오지파 (홍마노 #eb6120)
  {
    id: 'TR-THD-01',
    tribeId: 5,
    country: '터키',
    countryCode: 'TR',
    city: '이스탄불',
    lat: 41.0082,
    lng: 28.9784,
    members: 95,
    leader: '린다대오 선교사',
    establishedYear: 2022,
    address: 'Kadikoy, Istanbul, Turkey',
    phone: '+90 216 123 4567',
    notes: '유럽-아시아 교차로, 비공개 문화 사역 중심 진행',
    updatedAt: '2026-09-08'
  },

  // 빌립지파 (홍보석 #d7005b)
  {
    id: 'TR-PHI-01',
    tribeId: 6,
    country: '남아프리카공화국',
    countryCode: 'ZA',
    city: '케이프타운',
    lat: -33.9249,
    lng: 18.4241,
    members: 510,
    leader: '윤빌립 사역자',
    establishedYear: 2016,
    address: 'Foreshore, Cape Town, South Africa',
    phone: '+27 21 421 0000',
    notes: '아프리카 남부 최대 대형 교회, 현지 목회자 말씀 교류 활발',
    updatedAt: '2026-09-03'
  },

  // 시몬지파 (황옥 #fdd000)
  {
    id: 'TR-SIM-01',
    tribeId: 7,
    country: '프랑스',
    countryCode: 'FR',
    city: '파리',
    lat: 48.8566,
    lng: 2.3522,
    members: 210,
    leader: '하시몬 사역자',
    establishedYear: 2019,
    address: '15th Arrondissement, Paris, France',
    phone: '+33 1 45 67 89 00',
    notes: '불어권 문화 및 복음 전파 거점 지역',
    updatedAt: '2026-08-28'
  },

  // 마태지파 (담황옥 #e39300)
  {
    id: 'TR-MAT-01',
    tribeId: 9,
    country: '네덜란드',
    countryCode: 'NL',
    city: '암스테르담',
    lat: 52.3676,
    lng: 4.9041,
    members: 75,
    leader: '백마태 전도사',
    establishedYear: 2023,
    address: 'Amsterdam Centrum, Netherlands',
    phone: '+31 20 123 4567',
    notes: '다국적 영어 및 네덜란드어 병행 사역 진행',
    updatedAt: '2026-09-02'
  },

  // 맛디아지파 (비취옥 #6FBA2C)
  {
    id: 'TR-MTH-01',
    tribeId: 10,
    country: '브라질',
    countryCode: 'BR',
    city: '상파울루',
    lat: -23.5505,
    lng: -46.6333,
    members: 330,
    leader: '엄맛디아 사역자',
    establishedYear: 2017,
    address: 'Paulista Ave, Sao Paulo, Brazil',
    phone: '+55 11 3145 6789',
    notes: '남미 포르투갈어권 정식 교회, 전역으로 온라인 수강자 확대',
    updatedAt: '2026-09-17'
  },

  // 서울야고보지파 (청옥 #005dac)
  {
    id: 'TR-SJA-01',
    tribeId: 11,
    country: '몽골',
    countryCode: 'MN',
    city: '울란바토르',
    lat: 47.9184,
    lng: 106.9177,
    members: 460,
    leader: '장야고보 사역자',
    establishedYear: 2015,
    address: 'Sukhbaatar District, Ulaanbaatar, Mongolia',
    phone: '+976 11 32 1234',
    notes: '몽골어 완역 교재 보급 완료 및 현지 신학교 성황리 운영',
    updatedAt: '2026-09-19'
  },

  // 도마지파 (자정 #7f1084)
  {
    id: 'TR-THO-01',
    tribeId: 12,
    country: '인도',
    countryCode: 'IN',
    city: '뉴델리',
    lat: 28.6139,
    lng: 77.2090,
    members: 380,
    leader: '홍도마 사역자',
    establishedYear: 2018,
    address: 'Connaught Place, New Delhi, India',
    phone: '+91 11 2334 5678',
    notes: '힌디어 및 영어 병용, 인도 주요 대도시 지경 지속 확장 중',
    updatedAt: '2026-09-16'
  }
];

/* ==========================================================================
   바돌로매지파 해외 언어 인재 현황 초기 데이터
   - 구사 언어 및 레벨, 파견 가능 상태, 선호 도시, 전공/특기
   ========================================================================== */
export const INITIAL_TALENTS = [
  {
    id: 'TAL-BAR-001',
    name: '김서연',
    gender: '여',
    age: 29,
    department: '청년부',
    role: '구역장',
    photo: 'https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?auto=format&fit=crop&q=80&w=400',
    status: 'READY', // READY(즉시 파견 가능), DISPATCHED(현지 파견중), TRAINING(연수중), STANDBY(국내 대기)
    statusLabel: '즉시 파견 가능',
    statusColor: '#10b981', // green
    primaryLanguage: '독일어',
    languages: [
      { name: '독일어', level: 'C1 (유창/비즈니스)', exam: 'Goethe-Zertifikat C1' },
      { name: '영어', level: 'B2 (상급회화)', exam: 'TOEIC 915' }
    ],
    targetCountries: ['독일', '오스트리아', '스위스'],
    targetCities: ['비엔나', '베를린', '프랑크푸르트'],
    specialties: ['동시/순차통역', '현지적응 멘토링', '문서 번역'],
    experience: '독일 뮌헨 대학교 교환학생 1년, 현지 선교 단기 캠프 2회 참가',
    memo: '오스트리아 비엔나 신규 개척지 파견 1순위 추천 인재. 적극적인 성품과 영적 분별력 탁월.',
    contact: '010-3847-1928'
  },
  {
    id: 'TAL-BAR-002',
    name: '이준혁',
    gender: '남',
    age: 33,
    department: '장년부',
    role: '팀장',
    photo: 'https://images.unsplash.com/photo-1560250097-0b93528c311a?auto=format&fit=crop&q=80&w=400',
    status: 'DISPATCHED',
    statusLabel: '현지 파견중 (프랑크푸르트)',
    statusColor: '#00a0e9', // blue
    primaryLanguage: '독일어',
    languages: [
      { name: '독일어', level: 'C2 (원어민 수준)', exam: 'TestDaF TDN 5' },
      { name: '영어', level: 'C1 (비즈니스)', exam: 'IELTS 8.0' }
    ],
    targetCountries: ['독일'],
    targetCities: ['프랑크푸르트'],
    specialties: ['교회 행정/법인설립', '말씀 강의', '현지 비자 관리'],
    experience: '프랑크푸르트 현지 거주 4년차, 현지 사역 총괄 담당',
    memo: '현지 독일 교회 및 정부 등록 절차 주도. 바돌로매 유럽 본부 실무 핵심.',
    contact: '+49 176 1234 5678'
  },
  {
    id: 'TAL-BAR-003',
    name: '박유진',
    gender: '여',
    age: 26,
    department: '청년부',
    role: '총무',
    photo: 'https://images.unsplash.com/photo-1580489944761-15a19d654956?auto=format&fit=crop&q=80&w=400',
    status: 'READY',
    statusLabel: '즉시 파견 가능',
    statusColor: '#10b981',
    primaryLanguage: '영어',
    languages: [
      { name: '영어', level: 'C2 (원어민급)', exam: 'TOEFL 116' },
      { name: '체코어', level: 'A2 (기초회화)', exam: '현지 어학원 수강중' }
    ],
    targetCountries: ['체코', '스위스', '영국'],
    targetCities: ['프라하', '취리히'],
    specialties: ['미디어/영상 제작', '영어 말씀 세미나', 'SNS 홍보'],
    experience: '미국 조기유학 6년, 국제기구 인턴십 1년',
    memo: '체코 프라하 신규 개척지에 영어권 청년 전도 거점으로 조기 파견 적합.',
    contact: '010-8472-9102'
  },
  {
    id: 'TAL-BAR-004',
    name: '정현우',
    gender: '남',
    age: 31,
    department: '청년부',
    role: '강사보',
    photo: 'https://images.unsplash.com/photo-1519085360753-af0119f7cbe7?auto=format&fit=crop&q=80&w=400',
    status: 'TRAINING',
    statusLabel: '해외선교 사역 연수중',
    statusColor: '#fdd000', // yellow
    primaryLanguage: '스페인어',
    languages: [
      { name: '스페인어', level: 'B2 (중상급)', exam: 'DELE B2' },
      { name: '영어', level: 'B1 (일반회화)', exam: 'TOEIC 780' }
    ],
    targetCountries: ['스페인', '중남미'],
    targetCities: ['마드리드', '바르셀로나'],
    specialties: ['복음방 인도', '찬양/예배', '청년 소그룹 리더십'],
    experience: '스페인 어학연수 10개월, 해외 선교 특별 훈련 3기 수료',
    memo: '2027년 스페인어권 신규 개척 대비 집중 양성 인재. 열정과 헌신도 우수.',
    contact: '010-9182-3746'
  },
  {
    id: 'TAL-BAR-005',
    name: '최소민',
    gender: '여',
    age: 28,
    department: '부녀부',
    role: '서무',
    photo: 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&q=80&w=400',
    status: 'STANDBY',
    statusLabel: '국내 사역 (언어 지원)',
    statusColor: '#94a3b8', // slate
    primaryLanguage: '프랑스어',
    languages: [
      { name: '프랑스어', level: 'B2 (회화 가능)', exam: 'DELF B2' },
      { name: '영어', level: 'B2 (상급)', exam: 'TOEIC 870' }
    ],
    targetCountries: ['프랑스', '벨기에', '스위스'],
    targetCities: ['파리', '브뤼셀'],
    specialties: ['서면 공문 번역', '온라인 원격 번역지원', '재정/회계'],
    experience: '프랑스계 외투기업 근무 3년, 대외 서신 번역 지원 경험 다수',
    memo: '국내에서 온라인으로 유럽 지경 회계 및 번역 상시 지원 중. 요청 시 단기 파견 가능.',
    contact: '010-7261-5930'
  },
  {
    id: 'TAL-BAR-006',
    name: '한동원',
    gender: '남',
    age: 35,
    department: '장년부',
    role: '구역장',
    photo: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&q=80&w=400',
    status: 'DISPATCHED',
    statusLabel: '현지 파견중 (베를린)',
    statusColor: '#00a0e9',
    primaryLanguage: '독일어',
    languages: [
      { name: '독일어', level: 'C1 (전문가)', exam: 'TestDaF TDN 4' },
      { name: '영어', level: 'B2 (회화)', exam: 'OPIc IH' }
    ],
    targetCountries: ['독일'],
    targetCities: ['베를린'],
    specialties: ['현지인 전도', '성경 교육', '공관 및 비자 행정'],
    experience: '독일 베를린 현지 체류 3년, 현지 대학교 연계 사역',
    memo: '베를린 청년 중심 지역을 145명 성도로 성장시킨 주역. 리더십 탁월.',
    contact: '+49 152 9876 5432'
  }
];
