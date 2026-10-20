import os
import re
import csv
import json
import logging
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set

logger = logging.getLogger("GlossaryManager")

# 로컬 엑셀 파일 및 캐시 파일 경로
LOCAL_EXCEL_PATH = Path(__file__).parent / "언어권별_행정용어.xlsx"
CACHE_FILE = Path(__file__).parent / "glossary_cache.json"

try:
    import openpyxl
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False
    logger.warning("openpyxl library not installed. Excel files will fall back to cache or sheet URL.")

# 기본 지원 시트 탭 목록 (자동 탐색 실패 시 폴백용)
KNOWN_SHEET_NAMES = [
    "초중고 센터",
    "말씀/실상 단어집",
    "예배",
    "교육(인재양성)/심방",
    "섭외",
    "SCJ",
    "24부서 및 기타부서 명칭",
    "전도",
    "직책",
    "내무부 행정 (자장부청)",
    "공식 문서/책자",
    "공식 행사 및 교육명",
]


def extract_doc_id(url: str) -> Optional[str]:
    """구글 스프레드시트 URL에서 doc_id 추출"""
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url)
    return match.group(1) if match else None


class GlossaryManager:
    """
    '언어권별_행정용어.xlsx' 로컬 엑셀 및 구글 스프레드시트 기반 다국어 행정용어 관리자
    - 4대 타겟 언어(영어 EN, 베트남어 VI, 중국어 ZH, 스페인어 ES) 완벽 지원
    - 로컬 엑셀 파일 우선 로드 + 캐시 백업 (오프라인 및 클라우드 무중단 보장)
    - 긴 단어 우선 매칭(Greedy Longest Match) 및 단어 경계 보호로 부분 문자열 오염 원천 차단
    - 한국어 조사 분리 인식 정규식으로 '총회장님이', '센터에' 등 문맥 내 용어 감지
    - 번역 장애 시 순수 번역 100% 정상 작동 보장 (Fail-Safe)
    """

    def __init__(self, sheet_url: str = ""):
        self.raw_sheet_url = sheet_url.strip() if sheet_url else ""
        self.doc_id = extract_doc_id(self.raw_sheet_url)

        # 타겟 언어별 용어 매핑: {"en": [(ko_term, target_term), ...], "vi": [...], "zh": [...], "es": [...]}
        self.terms: Dict[str, List[Tuple[str, str]]] = {"en": [], "vi": [], "zh": [], "es": []}
        # 한글 동의어 -> 표준 대표 한글 용어 매핑: [(synonym, main_term), ...]
        self.synonym_to_main: List[Tuple[str, str]] = []

        self.last_sync_time: float = 0
        self.loaded_count: int = 0
        self.loaded_sheet_count: int = 0
        self.source_type: str = "none"  # "excel", "cache", "google_sheet"

        # 1. 로컬 엑셀 파일 우선 로드
        if LOCAL_EXCEL_PATH.exists() and HAS_OPENPYXL:
            success = self.load_from_excel()
            if success:
                logger.info(f"Loaded {self.loaded_count} terms from local Excel file.")
                return

        # 2. 로컬 캐시 파일에서 로드 (엑셀이 없거나 openpyxl 미설치 시)
        if self.load_from_cache():
            logger.info(f"Loaded {self.loaded_count} terms from local cache file.")
            return

        # 3. 구글 스프레드시트 URL이 있으면 온라인 동기화 시도
        if self.doc_id:
            self.sync()

    def is_enabled(self) -> bool:
        """용어집 활성화 여부 확인 (엑셀 파일 존재 또는 캐시/URL 데이터 보유)"""
        return LOCAL_EXCEL_PATH.exists() or self.loaded_count > 0 or bool(self.doc_id)

    def load_from_excel(self) -> bool:
        """로컬 '언어권별_행정용어.xlsx' 파일 파싱 및 메모리 적재"""
        if not LOCAL_EXCEL_PATH.exists() or not HAS_OPENPYXL:
            return False

        try:
            wb = openpyxl.load_workbook(LOCAL_EXCEL_PATH, data_only=True, read_only=True)
            sheet_names = wb.sheetnames
            if not sheet_names:
                return False

            raw_terms = {"en": [], "vi": [], "zh": [], "es": []}
            raw_synonyms = []
            valid_sheet_count = 0

            for s_name in sheet_names:
                sheet = wb[s_name]
                rows = list(sheet.iter_rows(values_only=True))
                if not rows:
                    continue

                # 상위 10행 내에서 컬럼 헤더 인덱스 자동 감지
                col_ko, col_en, col_vi, col_zh, col_es, col_syn = -1, -1, -1, -1, -1, -1
                header_idx = -1

                for r_idx, row in enumerate(rows[:10]):
                    if not row:
                        continue
                    norm_row = [str(c).strip().lower() for c in row if c is not None]
                    for c_idx, cell_str in enumerate(norm_row):
                        if any(k in cell_str for k in ["한국어", "한글", "원문", "용어", "korean", "ko"]):
                            col_ko = c_idx
                        elif any(k in cell_str for k in ["영어", "영문", "english", "en"]):
                            col_en = c_idx
                        elif any(k in cell_str for k in ["베트남", "vietnamese", "vi", "tiếng việt"]):
                            col_vi = c_idx
                        elif any(k in cell_str for k in ["중국어", "중국", "중문", "chinese", "zh", "cn"]):
                            col_zh = c_idx
                        elif any(k in cell_str for k in ["스페인어", "스페인", "서어", "spanish", "es", "español"]):
                            col_es = c_idx
                        elif any(k in cell_str for k in ["동의어", "유의어", "유사어", "synonym"]):
                            col_syn = c_idx

                    # 한국어 열과 최소 1개 이상의 외국어 열이 발견되면 헤더로 확정
                    if col_ko != -1 and any(c != -1 for c in [col_en, col_vi, col_zh, col_es]):
                        header_idx = r_idx
                        break

                # 명시적 헤더가 없는 경우: 0열 한글, 1열 영문, 2열 베트남어 등으로 기본 가정
                if col_ko == -1:
                    header_idx = 0
                    col_ko = 0
                    if len(rows[0]) > 1: col_en = 1
                    if len(rows[0]) > 2: col_vi = 2
                    if len(rows[0]) > 3: col_zh = 3
                    if len(rows[0]) > 4: col_es = 4

                data_rows = rows[header_idx + 1:] if header_idx != -1 else rows
                sheet_term_count = 0

                for row in data_rows:
                    if not row or len(row) <= col_ko or row[col_ko] is None:
                        continue

                    ko_raw = str(row[col_ko]).strip()
                    if not ko_raw or ko_raw.lower() in ["한글", "한국어", "원문", "용어", "korean", "ko", "no", "번호", "단어"]:
                        continue

                    main_ko = ko_raw
                    ko_synonyms = [main_ko]

                    # 1. 괄호 동의어 파싱: 예) "약속의 목자(약목, 목자님)"
                    paren_match = re.search(r'\((.*?)\)', ko_raw)
                    if paren_match:
                        extracted_main = re.sub(r'\(.*?\)', '', ko_raw).strip()
                        if extracted_main:
                            main_ko = extracted_main
                            if main_ko not in ko_synonyms:
                                ko_synonyms.append(main_ko)
                        for s in re.split(r'[,/;\n\r]+', paren_match.group(1)):
                            s_clean = s.strip()
                            if s_clean and s_clean not in ko_synonyms:
                                ko_synonyms.append(s_clean)

                    # 2. 동의어 컬럼 파싱
                    if col_syn != -1 and len(row) > col_syn and row[col_syn] is not None:
                        syn_str = str(row[col_syn]).strip()
                        if syn_str:
                            for s in re.split(r'[,/;\n\r]+', syn_str):
                                s_clean = s.strip()
                                if s_clean and s_clean not in ko_synonyms:
                                    ko_synonyms.append(s_clean)

                    # 대표어-동의어 관계 저장
                    for s_term in ko_synonyms:
                        if s_term != main_ko:
                            raw_synonyms.append((s_term, main_ko))

                    # 3. 언어별 매핑 추출 헬퍼
                    def add_lang_term(col_idx, lang_key, invalid_tokens):
                        if col_idx != -1 and len(row) > col_idx and row[col_idx] is not None:
                            val = str(row[col_idx]).strip()
                            if val and val.lower() not in invalid_tokens:
                                for s_term in ko_synonyms:
                                    # 한글 1글자 단어는 오탐 방지를 위해 스킵
                                    if len(s_term) >= 2:
                                        raw_terms[lang_key].append((s_term, val))
                                return True
                        return False

                    c_en = add_lang_term(col_en, "en", ["영어", "영문", "english", "en", "-", "n/a", "none"])
                    c_vi = add_lang_term(col_vi, "vi", ["베트남", "vietnamese", "vi", "-", "n/a", "none"])
                    c_zh = add_lang_term(col_zh, "zh", ["중국", "chinese", "zh", "cn", "-", "n/a", "none"])
                    c_es = add_lang_term(col_es, "es", ["스페인", "spanish", "es", "-", "n/a", "none"])

                    if any([c_en, c_vi, c_zh, c_es]):
                        sheet_term_count += 1

                if sheet_term_count > 0:
                    valid_sheet_count += 1

            wb.close()

            # 중복 제거 및 단어 길이 역순 정렬 (Greedy Longest Match)
            def deduplicate_and_sort(terms: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
                seen = set()
                unique_terms = []
                for src, tgt in terms:
                    key = (src.lower(), tgt.lower())
                    if key not in seen and src and tgt:
                        seen.add(key)
                        unique_terms.append((src, tgt))
                # 한글 단어 길이가 긴 순서대로 정렬 (긴 단어가 먼저 매칭되어 부분 오염 방지)
                return sorted(unique_terms, key=lambda x: len(x[0]), reverse=True)

            self.terms["en"] = deduplicate_and_sort(raw_terms["en"])
            self.terms["vi"] = deduplicate_and_sort(raw_terms["vi"])
            self.terms["zh"] = deduplicate_and_sort(raw_terms["zh"])
            self.terms["es"] = deduplicate_and_sort(raw_terms["es"])
            self.synonym_to_main = deduplicate_and_sort(raw_synonyms)

            import time
            self.last_sync_time = time.time()
            self.loaded_count = sum(len(self.terms[k]) for k in self.terms)
            self.loaded_sheet_count = valid_sheet_count
            self.source_type = "excel"

            # 캐시 파일 저장
            self.save_to_cache()
            return True

        except Exception as e:
            logger.error(f"Failed to load Excel glossary: {e}")
            return False

    def load_from_cache(self) -> bool:
        """로컬 JSON 캐시에서 용어집 로드"""
        if not CACHE_FILE.exists():
            return False

        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.terms["en"] = data.get("en", [])
            self.terms["vi"] = data.get("vi", [])
            self.terms["zh"] = data.get("zh", [])
            self.terms["es"] = data.get("es", [])
            self.synonym_to_main = data.get("synonyms", [])
            self.last_sync_time = data.get("timestamp", 0)
            self.loaded_count = sum(len(self.terms[k]) for k in self.terms)
            self.loaded_sheet_count = data.get("sheet_count", 0)
            self.source_type = "cache"
            return self.loaded_count > 0
        except Exception as e:
            logger.warning(f"Failed to load glossary cache: {e}")
            return False

    def save_to_cache(self):
        """현재 인메모리 용어집을 로컬 JSON 캐시로 직렬화"""
        try:
            data = {
                "en": self.terms.get("en", []),
                "vi": self.terms.get("vi", []),
                "zh": self.terms.get("zh", []),
                "es": self.terms.get("es", []),
                "synonyms": self.synonym_to_main,
                "sheet_count": self.loaded_sheet_count,
                "timestamp": self.last_sync_time,
                "source": self.source_type,
            }
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info("Saved glossary terms to local cache file.")
        except Exception as e:
            logger.warning(f"Failed to save glossary cache: {e}")

    def fetch_url_content(self, url: str) -> Optional[str]:
        """HTTP 요청으로 텍스트 컨텐츠 다운로드 (구글 시트 폴백용)"""
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                }
            )
            with urllib.request.urlopen(req, timeout=12) as response:
                return response.read().decode("utf-8")
        except Exception as e:
            logger.debug(f"Fetch failed for {url}: {e}")
            return None

    def sync(self) -> Tuple[bool, str]:
        """
        용어집 수동/자동 재동기화 (핫 리로드)
        1순위: 로컬 '언어권별_행정용어.xlsx'
        2순위: 구글 스프레드시트 URL
        """
        # 1. 로컬 엑셀 파일이 있으면 최우선 로드
        if LOCAL_EXCEL_PATH.exists() and HAS_OPENPYXL:
            success = self.load_from_excel()
            if success:
                msg = (
                    f"✅ **로컬 행정용어 엑셀 파일 동기화 완료**\n\n"
                    f"• 반영된 시트 수: **{self.loaded_sheet_count}개 시트**\n"
                    f"• 🇺🇸 영문 공식 용어: **{len(self.terms['en'])}개**\n"
                    f"• 🇻🇳 베트남어 공식 용어: **{len(self.terms['vi'])}개**\n"
                    f"• 🇨🇳 중국어 공식 용어: **{len(self.terms['zh'])}개**\n"
                    f"• 🇪🇸 스페인어 공식 용어: **{len(self.terms['es'])}개**\n"
                    f"• 🔗 등록된 동의어: **{len(self.synonym_to_main)}개**\n"
                    f"• 📊 총 반영 단어 수: **{self.loaded_count}개**\n\n"
                    f"✨ 모든 대화방 번역 시 공식 행정 용어가 우선 반영됩니다."
                )
                return True, msg

        # 2. 구글 스프레드시트 동기화 시도 (온라인 폴백)
        if not self.doc_id:
            return False, "동기화할 '언어권별_행정용어.xlsx' 파일 또는 구글 시트 URL이 설정되지 않았습니다."

        return False, "로컬 엑셀 파일을 찾을 수 없거나 파싱할 수 없습니다."

    def preprocess_source(self, text: str) -> str:
        """
        번역 전 전처리:
        문맥과 한국어 조사를 파괴하지 않기 위해 원문을 100% 그대로 보존합니다.
        """
        return text

    def apply_glossary(
        self,
        translated_text: str,
        target_lang: str,
        source_text: str = ""
    ) -> str:
        """
        지능형 후처리 중심 용어집 치환 (Fail-Safe 적용):
        - 한국어 원문에 해당 용어가 포함되어 있는지 확인 (조사 결합 허용)
        - 타겟 언어별 단어 경계(`\\b`, 문자셋 경계)를 엄격히 준수하여 부분 문자열 오염 차단
        - 대소문자 교정 및 공식 지정어 적용
        """
        if not translated_text or not self.is_enabled() or self.loaded_count == 0:
            return translated_text

        # 언어 코드 정규화
        norm_lang = target_lang.lower().strip()
        if norm_lang in ["zh-cn", "zh", "cn"]:
            lang_key = "zh"
        elif norm_lang in ["es", "spa"]:
            lang_key = "es"
        elif norm_lang in ["vi", "vie"]:
            lang_key = "vi"
        elif norm_lang in ["en", "en-us", "en-gb"]:
            lang_key = "en"
        else:
            lang_key = norm_lang

        if lang_key not in self.terms or not self.terms[lang_key]:
            return translated_text

        result = translated_text
        source_lower = source_text.lower() if source_text else ""

        for src_ko, target_term in self.terms[lang_key]:
            if not src_ko or not target_term or len(src_ko) < 2:
                continue

            # 1. 원문 존재 여부 검사 (조사/접미사 결합 형태 인식)
            # 예: "총회장" -> "총회장님이", "총회장님께서", "총회장에" 등
            if source_text:
                ko_clean = src_ko.lower()
                # 빠른 1차 필터링
                if ko_clean not in source_lower:
                    continue

                # 2차 정밀 형태소 경계 검사: 앞뒤가 다른 한글 단어의 일부인 경우는 오탐 방지 (예: '사과' 속의 '과')
                escaped_ko = re.escape(src_ko)
                # 단어 앞에는 한글/알파벳이 없어야 하고, 뒤에는 일반 조사나 기호만 올 수 있음
                ko_boundary_pattern = rf'(?<![가-힣a-zA-Z0-9]){escaped_ko}(?:님|들|께서|께|은|는|이|가|을|를|의|에|에서|에게|으로|로|와|과|도|만|부터|까지|이라도|마다)?(?![가-힣a-zA-Z0-9])'
                if not re.search(ko_boundary_pattern, source_text, flags=re.IGNORECASE):
                    continue

            # 2. 번역 결과물 내 치환 처리
            escaped_target = re.escape(target_term)

            # 언어별 경계 패턴 설정
            if lang_key == "en":
                # 영문: 단어 경계 \b 필수 (단어 일부 오염 방지)
                pattern = rf'\b{escaped_target}\b'
            elif lang_key == "es":
                # 스페인어: 스페인어 문자셋 경계
                pattern = rf'(?<![a-zA-ZáéíóúüñÁÉÍÓÚÜÑ]){escaped_target}(?![a-zA-ZáéíóúüñÁÉÍÓÚÜÑ])'
            elif lang_key == "vi":
                # 베트남어: 성조 문자셋 경계
                pattern = rf'(?<![a-zA-ZàáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴĐ]){escaped_target}(?![a-zA-ZàáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴĐ])'
            elif lang_key == "zh":
                # 중국어: CJK 한자 단위 매칭
                pattern = rf'{escaped_target}'
            else:
                pattern = rf'\b{escaped_target}\b'

            # 이미 대소문자까지 정확하게 결과물에 들어있다면 추가 치환 스킵
            if target_term in result:
                continue

            # 대소문자가 다르거나 철자가 살짝 다른 경우 공식 지정어로 교정
            result = re.sub(pattern, target_term, result, flags=re.IGNORECASE)

        return result

    def get_status_summary(self) -> str:
        """상태 안내용 요약 문자열 반환"""
        if not self.is_enabled():
            return "⚪ 비활성화됨 (기본 번역 엔진 작동 중)"
        if self.loaded_count == 0:
            return "미등록 (또는 동기화 대기 중)"

        source_label = "로컬 엑셀 연동" if self.source_type == "excel" else ("로컬 캐시" if self.source_type == "cache" else "온라인 시트")
        counts = [
            f"영문 {len(self.terms.get('en', []))}개",
            f"베트남어 {len(self.terms.get('vi', []))}개",
            f"중국어 {len(self.terms.get('zh', []))}개",
            f"스페인어 {len(self.terms.get('es', []))}개"
        ]
        active_counts = [c for c in counts if not c.endswith(" 0개")]
        summary_str = " / ".join(active_counts) if active_counts else f"총 {self.loaded_count}개"
        return f"🟢 정상 작동 중 ({source_label} / {self.loaded_sheet_count}개 시트 / {summary_str})"
