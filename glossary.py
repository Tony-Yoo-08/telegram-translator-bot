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

CACHE_FILE = Path(__file__).parent / "glossary_cache.json"

# 이미지에 확인된 기본 12개 시트 탭 목록 (자동 검색 실패 시 폴백 및 기본 탐색용)
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
    구글 스프레드시트의 모든 탭(다중 시트) 자동 연동 및 후처리 번역 치환 관리자
    - 모든 시트 탭(초중고 센터, 말씀/실상 단어집, 예배, 부서명 등)을 일괄 수집
    - 스마트 컬럼 헤더 감지 (한글, 영문, 베트남어, 동의어)
    - 로컬 캐시(glossary_cache.json) 보관으로 오프라인 및 장애 방지
    - 단어 길이 역순 정렬 및 단어 경계(\b)를 고려한 안전한 후처리 치환
    """

    def __init__(self, sheet_url: str = ""):
        self.raw_sheet_url = sheet_url.strip() if sheet_url else ""
        self.doc_id = extract_doc_id(self.raw_sheet_url)

        # 타겟 언어별 용어 매핑: {"en": [(ko_term, en_term), ...], "vi": [(ko_term, vi_term), ...]}
        self.terms: Dict[str, List[Tuple[str, str]]] = {"en": [], "vi": []}
        # 영문/베트남어 결과물에서 직접 치환하기 위한 사전: {"en": [(synonym_or_mistranslation, official_term), ...]}
        self.direct_replacements: Dict[str, List[Tuple[str, str]]] = {"en": [], "vi": []}
        # 한글 동의어 -> 표준 대표 한글 용어 매핑: [(synonym, main_term), ...]
        self.synonym_to_main: List[Tuple[str, str]] = []

        self.last_sync_time: float = 0
        self.loaded_count: int = 0
        self.loaded_sheet_count: int = 0

        # 초기 로컬 캐시 로드
        self.load_from_cache()

    def load_from_cache(self) -> bool:
        """로컬 파일에서 캐시된 용어집 로드"""
        if not CACHE_FILE.exists():
            return False

        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.terms["en"] = data.get("en", [])
            self.terms["vi"] = data.get("vi", [])
            self.direct_replacements["en"] = data.get("direct_en", [])
            self.direct_replacements["vi"] = data.get("direct_vi", [])
            self.synonym_to_main = data.get("synonyms", [])
            self.last_sync_time = data.get("timestamp", 0)
            self.loaded_count = len(self.terms["en"]) + len(self.terms["vi"])
            self.loaded_sheet_count = data.get("sheet_count", 0)
            logger.info(f"Loaded {self.loaded_count} glossary terms from local cache ({self.loaded_sheet_count} sheets).")
            return True
        except Exception as e:
            logger.warning(f"Failed to load glossary cache: {e}")
            return False

    def save_to_cache(self):
        """현재 인메모리 용어집을 로컬 파일에 저장"""
        try:
            data = {
                "en": self.terms["en"],
                "vi": self.terms["vi"],
                "direct_en": self.direct_replacements["en"],
                "direct_vi": self.direct_replacements["vi"],
                "synonyms": self.synonym_to_main,
                "sheet_count": self.loaded_sheet_count,
                "timestamp": self.last_sync_time,
            }
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info("Saved glossary terms to local cache file.")
        except Exception as e:
            logger.warning(f"Failed to save glossary cache: {e}")

    def fetch_url_content(self, url: str) -> Optional[str]:
        """HTTP 요청으로 텍스트 컨텐츠 다운로드"""
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

    def discover_sheet_tabs(self) -> List[Tuple[Optional[str], Optional[str]]]:
        """
        스프레드시트의 모든 탭(시트 이름 및 gid) 자동 탐색
        반환값: [(sheet_name, gid), ...]
        """
        if not self.doc_id:
            return []

        tabs: Dict[str, Optional[str]] = {}

        # 1. htmlview 웹페이지에서 탭 목록 검색 시도
        html_url = f"https://docs.google.com/spreadsheets/d/{self.doc_id}/htmlview"
        html_content = self.fetch_url_content(html_url)

        if html_content:
            # 패턴 A: <li id="sheet-button-12345"><a href="...gid=12345...">시트명</a>
            matches = re.findall(r'gid=([0-9]+)[^>]*>([^<]+)</a>', html_content)
            for gid, name in matches:
                name_clean = name.strip()
                if name_clean:
                    tabs[name_clean] = gid

            # 패턴 B: JSON 데이터 내의 탭 목록 감지
            json_matches = re.findall(r'name["\']?\s*:\s*["\']([^"\']+)["\'][\s\S]*?sheetId["\']?\s*:\s*([0-9]+)', html_content)
            for name, gid in json_matches:
                name_clean = name.strip()
                if name_clean and name_clean not in tabs:
                    tabs[name_clean] = gid

        # 2. 알려진 시트 목록(KNOWN_SHEET_NAMES) 병합 (누락 방지)
        for name in KNOWN_SHEET_NAMES:
            if name not in tabs:
                tabs[name] = None

        result = [(name, gid) for name, gid in tabs.items()]
        logger.info(f"Discovered {len(result)} sheet tabs to sync.")
        return result

    def fetch_sheet_csv(self, name: Optional[str] = None, gid: Optional[str] = None) -> Optional[str]:
        """특정 시트(탭)의 CSV 데이터 다운로드"""
        if not self.doc_id:
            return None

        # 1. gid가 있으면 gid로 시도
        if gid is not None:
            url = f"https://docs.google.com/spreadsheets/d/{self.doc_id}/export?format=csv&gid={gid}"
            content = self.fetch_url_content(url)
            if content and "html" not in content.lower()[:100]:
                return content

        # 2. 시트 이름이 있으면 gviz/tq 엔드포인트로 시도
        if name:
            encoded_name = urllib.parse.quote(name)
            url = f"https://docs.google.com/spreadsheets/d/{self.doc_id}/gviz/tq?tqx=out:csv&sheet={encoded_name}"
            content = self.fetch_url_content(url)
            if content and "html" not in content.lower()[:100]:
                return content

        return None

    def parse_csv_rows(self, csv_content: str) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]], List[Tuple[str, str]]]:
        """개별 CSV 내용에서 (영문매핑, 베트남어매핑, 동의어매핑) 추출"""
        parsed_en = []
        parsed_vi = []
        parsed_synonyms = []

        try:
            lines = csv_content.splitlines()
            reader = csv.reader(lines)
            all_rows = [row for row in reader if any(cell.strip() for cell in row)]

            if not all_rows:
                return parsed_en, parsed_vi, parsed_synonyms

            # 헤더 컬럼 인덱스 자동 감지 (상위 5줄 내)
            header_idx = -1
            col_ko = -1
            col_en = -1
            col_vi = -1
            col_syn = -1

            for r_idx, row in enumerate(all_rows[:6]):
                norm_row = [cell.strip().lower() for cell in row]
                for c_idx, val in enumerate(norm_row):
                    if any(k in val for k in ["한글", "한국어", "원문", "용어", "korean", "ko"]):
                        col_ko = c_idx
                    elif any(k in val for k in ["영어", "영문", "english", "en"]):
                        col_en = c_idx
                    elif any(k in val for k in ["베트남", "vietnamese", "vi", "tiếng việt"]):
                        col_vi = c_idx
                    elif any(k in val for k in ["동의어", "유의어", "유사어", "synonym"]):
                        col_syn = c_idx

                if col_ko != -1 and (col_en != -1 or col_vi != -1):
                    header_idx = r_idx
                    break

            # 명시적 헤더가 없는 경우: 0열 한글, 1열 영문 가정
            if col_ko == -1:
                header_idx = 0
                col_ko = 0
                col_en = 1 if len(all_rows[0]) > 1 else -1

            data_rows = all_rows[header_idx + 1:] if header_idx != -1 else all_rows
            for row in data_rows:
                if len(row) <= col_ko:
                    continue

                ko_term = row[col_ko].strip()
                if not ko_term:
                    continue

                # 헤더 라벨 재출현 무시
                if ko_term.lower() in ["한글", "한국어", "원문", "용어", "korean", "ko", "단어", "no", "번호"]:
                    continue

                main_ko = ko_term
                ko_synonyms = [main_ko]

                # 동의어 분리 (쉼표, 슬래시, 줄바꿈 등)
                if col_syn != -1 and len(row) > col_syn:
                    syn_text = row[col_syn].strip()
                    if syn_text:
                        for s in re.split(r'[,/;\n\r]+', syn_text):
                            s_clean = s.strip()
                            if s_clean and s_clean not in ko_synonyms:
                                ko_synonyms.append(s_clean)

                # 한글 원문 자체에 괄호로 동의어가 표기된 경우: 예) "약속의 목자(약목, 목자님)"
                paren_match = re.search(r'\((.*?)\)', ko_term)
                if paren_match:
                    extracted_main = re.sub(r'\(.*?\)', '', ko_term).strip()
                    if extracted_main:
                        main_ko = extracted_main
                        if main_ko not in ko_synonyms:
                            ko_synonyms.append(main_ko)
                    for s in re.split(r'[,/;\n\r]+', paren_match.group(1)):
                        s_clean = s.strip()
                        if s_clean and s_clean not in ko_synonyms:
                            ko_synonyms.append(s_clean)

                # 동의어 -> 대표어 매핑 구축
                for s_term in ko_synonyms:
                    if s_term != main_ko:
                        parsed_synonyms.append((s_term, main_ko))

                # 영문 매핑
                if col_en != -1 and len(row) > col_en:
                    en_term = row[col_en].strip()
                    if en_term and en_term.lower() not in ["영어", "영문", "english", "en", "-", "n/a"]:
                        for s_term in ko_synonyms:
                            parsed_en.append((s_term, en_term))

                # 베트남어 매핑
                if col_vi != -1 and len(row) > col_vi:
                    vi_term = row[col_vi].strip()
                    if vi_term and vi_term.lower() not in ["베트남", "vietnamese", "vi", "-", "n/a"]:
                        for s_term in ko_synonyms:
                            parsed_vi.append((s_term, vi_term))

        except Exception as e:
            logger.debug(f"Row parse error in sheet: {e}")

        return parsed_en, parsed_vi, parsed_synonyms

    def sync(self) -> Tuple[bool, str]:
        """
        스프레드시트 내의 '모든 시트(탭)'를 탐색하고 다운로드하여 일괄 동기화
        반환값: (성공 여부, 안내 메시지)
        """
        if not self.doc_id:
            return False, "구글 스프레드시트 URL(GLOSSARY_SHEET_URL)이 올바르지 않습니다."

        tabs = self.discover_sheet_tabs()
        if not tabs:
            # 탭을 못 찾은 경우 기본 첫 번째 시트라도 시도
            tabs = [(None, "0")]

        all_parsed_en: List[Tuple[str, str]] = []
        all_parsed_vi: List[Tuple[str, str]] = []
        all_parsed_synonyms: List[Tuple[str, str]] = []
        successful_sheets = []

        # 각 시트별로 CSV 다운로드 및 파싱
        for sheet_name, gid in tabs:
            display_name = sheet_name or f"시트(gid={gid})"
            csv_content = self.fetch_sheet_csv(name=sheet_name, gid=gid)
            if not csv_content:
                continue

            en_list, vi_list, syn_list = self.parse_csv_rows(csv_content)
            if en_list or vi_list:
                all_parsed_en.extend(en_list)
                all_parsed_vi.extend(vi_list)
                all_parsed_synonyms.extend(syn_list)
                successful_sheets.append(display_name)
                logger.info(f"Sheet [{display_name}] synced: {len(en_list)} EN, {len(vi_list)} VI terms.")

        if not all_parsed_en and not all_parsed_vi:
            return False, "스프레드시트의 시트들에서 유효한 용어 데이터를 가져오지 못했습니다. 공유 권한(링크가 있는 모든 사용자 보기 허용)을 확인해 주세요."

        # 중복 제거 및 긴 단어 우선 정렬 (Greedy length matching)
        def deduplicate_and_sort(terms: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
            seen = set()
            unique_terms = []
            for src, tgt in terms:
                key = (src.lower(), tgt.lower())
                if key not in seen and src and tgt:
                    seen.add(key)
                    unique_terms.append((src, tgt))
            return sorted(unique_terms, key=lambda x: len(x[0]), reverse=True)

        self.terms["en"] = deduplicate_and_sort(all_parsed_en)
        self.terms["vi"] = deduplicate_and_sort(all_parsed_vi)
        self.synonym_to_main = deduplicate_and_sort(all_parsed_synonyms)

        import time
        self.last_sync_time = time.time()
        self.loaded_count = len(self.terms["en"]) + len(self.terms["vi"])
        self.loaded_sheet_count = len(successful_sheets)

        self.save_to_cache()

        sheet_preview = ", ".join(successful_sheets[:4])
        if len(successful_sheets) > 4:
            sheet_preview += f" 외 {len(successful_sheets) - 4}개"

        msg = (
            f"✅ **전체 시트 용어집 동기화 완료**\n\n"
            f"• 반영된 시트 수: **{self.loaded_sheet_count}개 시트** ({sheet_preview})\n"
            f"• 영문 공식 용어: **{len(self.terms['en'])}개**\n"
            f"• 베트남어 공식 용어: **{len(self.terms['vi'])}개**\n"
            f"• 등록된 동의어: **{len(self.synonym_to_main)}개**\n"
            f"• 총 반영 단어 수: **{self.loaded_count}개**"
        )
        logger.info(f"All sheets synced. Total terms: {self.loaded_count} from {self.loaded_sheet_count} sheets.")
        return True, msg

    def preprocess_source(self, text: str) -> str:
        """
        번역 전 전처리:
        원문에 동의어/약어(예: '약목', '목자님')가 포함되어 있으면
        번역기가 혼동하지 않도록 시트의 대표 표준 한글 용어로 통일
        """
        if not text:
            return text

        result = text
        for syn, main_term in self.synonym_to_main:
            if syn in result and syn != main_term:
                result = result.replace(syn, main_term)

        return result

    def apply_glossary(
        self,
        translated_text: str,
        target_lang: str,
        source_text: str = ""
    ) -> str:
        """
        후처리 중심 용어집 치환:
        1. 원문(source_text)에 용어집의 한글 단어가 포함되어 있는 경우
        2. 번역 결과물(translated_text)에서 대소문자 표기 및 공식 단어로 정밀 교정
        """
        if not translated_text:
            return translated_text

        target_lang = target_lang.lower()
        if target_lang not in self.terms or not self.terms[target_lang]:
            return translated_text

        result = translated_text
        source_lower = source_text.lower() if source_text else ""

        for src_ko, target_term in self.terms[target_lang]:
            if not src_ko or not target_term:
                continue

            # 원문에 해당 단어나 동의어가 있었는지 확인
            if source_text and src_ko.lower() not in source_lower:
                continue

            escaped_target = re.escape(target_term)
            if target_lang == "en":
                pattern = rf'\b{escaped_target}\b'
            else:
                pattern = rf'{escaped_target}'

            # 결과물에 이미 대소문자까지 정확히 들어가 있으면 스킵
            if target_term in result:
                continue

            # 대소문자가 다르거나 철자가 살짝 다른 경우 공식 지정어로 교정 (예: promised pastor -> Promised Pastor)
            result = re.sub(pattern, target_term, result, flags=re.IGNORECASE)

        return result

    def get_status_summary(self) -> str:
        """상태 안내용 요약 문자열 반환"""
        if self.loaded_count == 0:
            return "미등록 (또는 동기화 대기 중)"
        en_count = len(self.terms.get("en", []))
        vi_count = len(self.terms.get("vi", []))
        sheet_info = f"{self.loaded_sheet_count}개 시트" if self.loaded_sheet_count > 0 else ""
        return f"🟢 정상 작동 중 ({sheet_info} / 영문 {en_count}개 / 베트남어 {vi_count}개)"
