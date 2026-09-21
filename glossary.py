import os
import re
import csv
import json
import logging
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger("GlossaryManager")

CACHE_FILE = Path(__file__).parent / "glossary_cache.json"


def normalize_sheet_url(url: str) -> str:
    """
    일반적인 구글 스프레드시트 공유/편집 URL을 CSV 다운로드 URL로 자동 정규화
    지원 형식:
    - https://docs.google.com/spreadsheets/d/{ID}/edit#gid={GID}
    - https://docs.google.com/spreadsheets/d/{ID}/edit?gid={GID}
    - https://docs.google.com/spreadsheets/d/{ID}/view
    - 이미 export?format=csv 형태인 경우 그대로 유지
    """
    if not url or "docs.google.com/spreadsheets" not in url:
        return url

    # 이미 export?format=csv 형태인 경우
    if "export?format=csv" in url or "output=csv" in url:
        return url

    # 스프레드시트 ID 추출
    match_id = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url)
    if not match_id:
        return url

    doc_id = match_id.group(1)

    # gid 추출 (시트 탭 ID)
    gid = "0"
    match_gid = re.search(r"[?&#]gid=([0-9]+)", url)
    if match_gid:
        gid = match_gid.group(1)

    return f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=csv&gid={gid}"


class GlossaryManager:
    """
    구글 스프레드시트 연동 및 후처리 번역 치환 관리자
    - 구글 시트 CSV 자동 다운로드 및 스마트 컬럼 매핑
    - 로컬 캐시(glossary_cache.json) 보관으로 오프라인 및 장애 방지
    - 단어 길이 역순 정렬 및 단어 경계(\b)를 고려한 안전한 후처리 치환
    """

    def __init__(self, sheet_url: str = ""):
        self.raw_sheet_url = sheet_url.strip() if sheet_url else ""
        self.csv_url = normalize_sheet_url(self.raw_sheet_url)

        # 타겟 언어별 용어 매핑: {"en": [(ko_term, en_term), ...], "vi": [(ko_term, vi_term), ...]}
        self.terms: Dict[str, List[Tuple[str, str]]] = {"en": [], "vi": []}
        # 영문/베트남어 결과물에서 직접 치환하기 위한 사전: {"en": [(synonym_or_mistranslation, official_term), ...]}
        self.direct_replacements: Dict[str, List[Tuple[str, str]]] = {"en": [], "vi": []}
        # 한글 동의어 -> 표준 대표 한글 용어 매핑: [(synonym, main_term), ...]
        self.synonym_to_main: List[Tuple[str, str]] = []

        self.last_sync_time: float = 0
        self.loaded_count: int = 0

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
            logger.info(f"Loaded {self.loaded_count} glossary terms from local cache.")
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
                "timestamp": self.last_sync_time,
            }
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info("Saved glossary terms to local cache file.")
        except Exception as e:
            logger.warning(f"Failed to save glossary cache: {e}")


    def fetch_sheet_csv(self) -> Optional[str]:
        """구글 스프레드시트 CSV 다운로드"""
        if not self.csv_url:
            return None

        try:
            req = urllib.request.Request(
                self.csv_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                }
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                content = response.read().decode("utf-8")
                return content
        except Exception as e:
            logger.error(f"Failed to download Google Sheet CSV: {e}")
            return None

    def sync(self) -> Tuple[bool, str]:
        """
        구글 시트로부터 최신 용어집 동기화 수행
        반환값: (성공 여부, 안내 메시지)
        """
        if not self.csv_url:
            return False, "구글 스프레드시트 URL(GLOSSARY_SHEET_URL)이 설정되지 않았습니다."

        csv_content = self.fetch_sheet_csv()
        if not csv_content:
            return False, "구글 시트 접근에 실패했습니다. 공유 권한(링크가 있는 모든 사용자에게 보기 허용)을 확인해 주세요."

        try:
            lines = csv_content.splitlines()
            reader = csv.reader(lines)
            all_rows = [row for row in reader if any(cell.strip() for cell in row)]

            if not all_rows:
                return False, "스프레드시트에 내용이 없습니다."

            # 1. 헤더 컬럼 인덱스 자동 감지 (상위 5줄 내에서 검색)
            header_idx = -1
            col_ko = -1
            col_en = -1
            col_vi = -1
            col_syn = -1

            for r_idx, row in enumerate(all_rows[:6]):
                norm_row = [cell.strip().lower() for cell in row]
                # 한국어/원문 컬럼 감지
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

            # 명시적 헤더를 찾지 못한 경우: 0열이 한글, 1열이 영문으로 기본 가정
            if col_ko == -1:
                header_idx = 0
                col_ko = 0
                col_en = 1 if len(all_rows[0]) > 1 else -1

            parsed_en: List[Tuple[str, str]] = []
            parsed_vi: List[Tuple[str, str]] = []
            parsed_direct_en: List[Tuple[str, str]] = []
            parsed_direct_vi: List[Tuple[str, str]] = []
            parsed_synonyms: List[Tuple[str, str]] = []

            data_rows = all_rows[header_idx + 1:] if header_idx != -1 else all_rows
            for row in data_rows:
                if len(row) <= col_ko:
                    continue

                ko_term = row[col_ko].strip()
                if not ko_term:
                    continue

                # 헤더명이 다시 나온 경우 스킵
                if ko_term.lower() in ["한글", "한국어", "원문", "용어", "korean", "ko"]:
                    continue

                # 동의어 분리 (쉼표, 슬래시, 줄바꿈 등)
                main_ko = ko_term
                ko_synonyms = [main_ko]
                if col_syn != -1 and len(row) > col_syn:
                    syn_text = row[col_syn].strip()
                    if syn_text:
                        for s in re.split(r'[,/;\n\r]+', syn_text):
                            s_clean = s.strip()
                            if s_clean and s_clean not in ko_synonyms:
                                ko_synonyms.append(s_clean)

                # 한글 원문 자체에 괄호로 동의어가 포함된 경우 추출: 예) "약속의 목자(약목, 목자님)"
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

            # 중복 제거 및 긴 단어 우선 정렬 (Greedy length matching: 부분 일치 방지)
            def deduplicate_and_sort(terms: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
                seen = set()
                unique_terms = []
                for src, tgt in terms:
                    key = (src.lower(), tgt.lower())
                    if key not in seen and src and tgt:
                        seen.add(key)
                        unique_terms.append((src, tgt))
                # 긴 원문 단어부터 매칭되도록 역순 정렬
                return sorted(unique_terms, key=lambda x: len(x[0]), reverse=True)

            self.terms["en"] = deduplicate_and_sort(parsed_en)
            self.terms["vi"] = deduplicate_and_sort(parsed_vi)
            self.direct_replacements["en"] = deduplicate_and_sort(parsed_direct_en)
            self.direct_replacements["vi"] = deduplicate_and_sort(parsed_direct_vi)
            self.synonym_to_main = deduplicate_and_sort(parsed_synonyms)

            import time
            self.last_sync_time = time.time()
            self.loaded_count = len(self.terms["en"]) + len(self.terms["vi"])

            self.save_to_cache()


            msg = (
                f"✅ **용어집 동기화 완료**\n\n"
                f"• 영문 공식 용어: {len(self.terms['en'])}개\n"
                f"• 베트남어 공식 용어: {len(self.terms['vi'])}개\n"
                f"• 총 등록 단어 수: {self.loaded_count}개"
            )
            logger.info(f"Glossary synced successfully. Total terms: {self.loaded_count}")
            return True, msg

        except Exception as e:
            logger.error(f"Error parsing glossary CSV: {e}", exc_info=True)
            return False, f"용어집 파싱 중 오류가 발생했습니다: {type(e).__name__}"

    def preprocess_source(self, text: str) -> str:
        """
        번역 전 전처리:
        원문에 동의어/약어(예: '약목', '목자님')가 포함되어 있으면
        번역기가 혼동하지 않도록 시트의 대표 표준 한글 용어로 통일
        """
        if not text:
            return text

        result = text
        # 대표 한글 단어로의 동의어 치환
        for syn, main_term in self.synonym_to_main:
            if syn in result and syn != main_term:
                # 단어 치환
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
        3. 직접 치환 목록(오역 패턴)이 정의되어 있으면 강제 보정
        """
        if not translated_text:
            return translated_text

        target_lang = target_lang.lower()
        if target_lang not in self.terms or not self.terms[target_lang]:
            return translated_text

        result = translated_text
        source_lower = source_text.lower() if source_text else ""

        # 1. 원문(source_text) 기반 매핑 및 공식 표기 교정
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

        # 2. 직접 치환 목록(direct_replacements) 적용 (번역기 오역 패턴 교정)
        if target_lang in self.direct_replacements:
            for wrong_term, correct_term in self.direct_replacements[target_lang]:
                escaped_wrong = re.escape(wrong_term)
                if target_lang == "en":
                    pattern = rf'\b{escaped_wrong}\b'
                else:
                    pattern = rf'{escaped_wrong}'
                result = re.sub(pattern, correct_term, result, flags=re.IGNORECASE)

        return result


    def get_status_summary(self) -> str:
        """상태 안내용 요약 문자열 반환"""
        if self.loaded_count == 0:
            return "미등록 (또는 동기화 대기 중)"
        en_count = len(self.terms.get("en", []))
        vi_count = len(self.terms.get("vi", []))
        return f"🟢 정상 작동 중 (영문 {en_count}개 / 베트남어 {vi_count}개)"
