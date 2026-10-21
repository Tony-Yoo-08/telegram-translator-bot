import re
import json
import logging
import urllib.parse
import urllib.request
from typing import Optional, List, Tuple, Set, Dict
import deepl
from deep_translator import GoogleTranslator

logger = logging.getLogger(__name__)

# URL 및 멘션 정규식
URL_PATTERN = re.compile(r'https?://\S+|www\.\S+')
MENTION_PATTERN = re.compile(r'@\w+')

# 특수기호, 문장부호, 대표적인 이모지 제거용 정규식
PUNCT_AND_EMOJI = re.compile(r'[\s!~.?,\^;:\-_/\\()\[\]{}@#$%&*+=\'\"|🙏❤️✨🙌👏🙇👍😊😄😃😀]+')

# 특정 언어 고유 문자 정규식 (S12 준수: 중립적 명칭)
LANG_SPECIFIC_CHAR_PATTERN = re.compile(
    r'[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ'
    r'ÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴĐ]'
)

# 중국어 한자 정규식 (CJK 통합 한자)
CHINESE_CHAR_PATTERN = re.compile(r'[\u4e00-\u9fff]')

# 스페인어 고유 문자 정규식 (역물음표, 역느낌표, 악센트 모음, ñ)
SPANISH_CHAR_PATTERN = re.compile(r'[áéíóúüñ¿¡ÁÉÍÓÚÜÑ]')

# 단답형 감탄사 및 빈번한 단문 리액션 필터링 목록 (S12 준수: 중립적 변수명 및 주석)
FILTERED_SHORT_RESPONSES = {
    # 그룹 1: 단문 호응어
    "아멘", "amen", "아멘입니다", "아멘요",
    "샬롬", "shalom", "할렐루야", "hallelujah",
    "기도합니다", "축복합니다", "은혜롭습니다",
    
    # 그룹 2: 일상 단답/확인
    "네", "넵", "넹", "넴", "예", "응", "어", "아니", "아뇨", "아닙니다",
    "오키", "오케이", "ㅇㅋ", "알겠습니다", "확인했습니다",
    "감사", "감사합니다", "고마워", "고마워요", "수고", "수고하셨습니다", "수고하세요",
    "축하", "축하합니다", "축하해요", "축하드려요",
    "하이", "바이", "굿", "좋아요", "대박",
    
    # 그룹 3: 영문 단답
    "ok", "okay", "yes", "yeah", "yep", "no", "nope",
    "thx", "thanks", "thankyou", "thank",
    "ty", "k", "gg", "lol", "nvm", "np", "pls", "plz", "sry", "sorry",
    "good", "great", "nice", "cool", "wow", "omg", "congrats",

    # 그룹 4: 베트남어 단답
    "dạ", "vâng", "cảm ơn", "cam on", "oke",

    # 그룹 5: 중국어 단답
    "好的", "收到", "谢谢", "谢谢你", "多谢", "感恩", "阿门", "阿們",
    "哈利路亚", "哈利路亞", "赞美", "讚美", "你好", "再见", "对", "是的",

    # 그룹 6: 스페인어 단답
    "si", "sí", "gracias", "hola", "adios", "adiós", "bien", "amén", "bueno", "vale"
}

# 단순 반복 패턴 정규식
REPEATING_WORD_PATTERN = re.compile(
    r'^((아멘|amen|샬롬|shalom|할렐루야|hallelujah)[\s!~.?🙏❤️✨🙌👏🙇]*)+$',
    re.IGNORECASE
)


def preprocess_text(text: str) -> str:
    """URL, 멘션 등을 임시 제거하여 실제 내용만 추출"""
    cleaned = URL_PATTERN.sub('', text)
    cleaned = MENTION_PATTERN.sub('', cleaned)
    return cleaned.strip()


def is_trivial_reaction(text: str) -> bool:
    """단순 리액션 여부 판별 (실질적인 대화/공지는 False 반환)"""
    if re.fullmatch(r'^[ㄱ-ㅎㅏ-ㅣ\s]+$', text):
        return True

    if REPEATING_WORD_PATTERN.fullmatch(text):
        return True

    stripped = PUNCT_AND_EMOJI.sub('', text).lower()
    if not stripped:
        return True

    if stripped in FILTERED_SHORT_RESPONSES:
        return True

    return False


def detect_source_language(text: str) -> Optional[str]:
    """텍스트의 언어를 감지하여 'KO', 'VI', 'EN' 중 하나를 반환"""
    if not text or not text.strip():
        return None

    if text.strip().startswith('/'):
        return None

    cleaned = preprocess_text(text)
    if not cleaned:
        return None

    # 단순 기호/숫자/이모지만 있는 경우 제외
    if (not re.search(r'[가-힣a-zA-Z]', cleaned) 
            and not LANG_SPECIFIC_CHAR_PATTERN.search(cleaned)
            and not CHINESE_CHAR_PATTERN.search(cleaned)
            and not SPANISH_CHAR_PATTERN.search(cleaned)):
        return None

    # 단순 리액션 필터링
    if is_trivial_reaction(cleaned):
        return None

    # 1. 한국어 감지 (한글 우선)
    if re.search(r'[가-힣]', cleaned):
        return "KO"

    # 2. 중국어 한자 감지 (한글 없는 한자 문장)
    if CHINESE_CHAR_PATTERN.search(cleaned):
        return "ZH"

    # 3. 베트남어 문자 감지
    if LANG_SPECIFIC_CHAR_PATTERN.search(cleaned):
        return "VI"

    # 4. 스페인어 고유 문자 감지
    if SPANISH_CHAR_PATTERN.search(cleaned):
        return "ES"

    # 5. 영문/라틴 문자 감지
    if re.search(r'[a-zA-Z]', cleaned):
        return "EN"

    return None


# 5개국어 지원 정의 (한국어 기준 4개 외국어 타겟)
SUPPORTED_TARGET_LANGUAGES: Dict[str, Dict[str, str]] = {
    "en": {"code": "en", "target_code": "en", "flag": "🇺🇸", "name": "영어"},
    "vi": {"code": "vi", "target_code": "vi", "flag": "🇻🇳", "name": "베트남어"},
    "zh": {"code": "zh", "target_code": "zh-CN", "flag": "🇨🇳", "name": "중국어"},
    "es": {"code": "es", "target_code": "es", "flag": "🇪🇸", "name": "스페인어"},
}
ORDERED_TARGET_LANGS = ["en", "vi", "zh", "es"]


def parse_active_languages(mode: str) -> Set[str]:
    """
    모드 문자열을 분석하여 활성화된 외국어 대상 식별자 집합(set) 반환
    - 'all', '5' -> {'en', 'vi', 'zh', 'es'} (5개국어 전체 번역)
    - 'ko-en', 'en' -> {'en'}
    - 'ko-vi', 'vi' -> {'vi'}
    - 'ko-zh', 'zh' -> {'zh'}
    - 'ko-es', 'es' -> {'es'}
    - 'en,vi', 'en+zh', 'en,vi,zh,es' 등 임의의 다중 선택 조합 완벽 지원
    """
    if not mode:
        return set(ORDERED_TARGET_LANGS)

    m = mode.strip().lower()
    if m in ["all", "5", "5개국어", "전체", "모두"]:
        return set(ORDERED_TARGET_LANGS)
    if m in ["3", "3개국어"]:
        # 과거 3개국어 하위 호환
        return {"en", "vi"}
    if m in ["ko-en", "en", "영어"]:
        return {"en"}
    if m in ["ko-vi", "vi", "베트남어"]:
        return {"vi"}
    if m in ["ko-zh", "zh", "중국어"]:
        return {"zh"}
    if m in ["ko-es", "es", "스페인어"]:
        return {"es"}

    tokens = re.split(r'[,+\s/]+', m)
    result: Set[str] = set()
    for tok in tokens:
        tok = tok.strip()
        if not tok:
            continue
        if tok in ["en", "영어", "ko-en", "us"]:
            result.add("en")
        elif tok in ["vi", "베트남어", "ko-vi", "vn"]:
            result.add("vi")
        elif tok in ["zh", "zh-cn", "중국어", "ko-zh", "cn"]:
            result.add("zh")
        elif tok in ["es", "스페인어", "ko-es"]:
            result.add("es")
        elif tok in ["all", "전체", "5개국어", "5"]:
            return set(ORDERED_TARGET_LANGS)

    return result if result else set(ORDERED_TARGET_LANGS)


def get_translation_targets(source_lang: str, mode: str = "all") -> List[Tuple[str, str]]:
    """
    모드별(단일/다중/5개국어 전체) 번역 대상 언어 및 심볼 반환
    - source_lang == 'KO': 활성화된 모든 대상 외국어(선택된 언어들) 동시 번역 반환
    - source_lang == 'EN': 한국어([('ko', '🇰🇷')]) + 다른 활성화된 외국어(베트남, 중국, 스페인 등) 함께 번역
    - source_lang in ['VI', 'ZH', 'ES']: 한국어([('ko', '🇰🇷')])로 번역
    """
    active = parse_active_languages(mode)
    if not active:
        return []

    if source_lang == "KO":
        return [
            (SUPPORTED_TARGET_LANGUAGES[k]["target_code"], SUPPORTED_TARGET_LANGUAGES[k]["flag"])
            for k in ORDERED_TARGET_LANGS
            if k in active
        ]

    src = source_lang.lower() if source_lang else ""

    if src == "en":
        targets: List[Tuple[str, str]] = [("ko", "🇰🇷")]
        for k in ["vi", "zh", "es"]:
            if k in active:
                targets.append((SUPPORTED_TARGET_LANGUAGES[k]["target_code"], SUPPORTED_TARGET_LANGUAGES[k]["flag"]))
        return targets

    elif src in ["vi", "zh", "es"]:
        return [("ko", "🇰🇷")]

    return []


def is_bilingual_ko_en(text: str) -> bool:
    """
    한글과 영문이 함께 수록된 양방향 게시글(생명의 어록 등) 판별
    - 한글 음절 15자 이상 & 영문 단어 10단어 이상
    - 또는 어록 관련 키워드가 포함된 경우 완화된 기준(한글 8자 이상, 영문 6단어 이상) 적용
    """
    if not text:
        return False

    ko_chars = len(re.findall(r'[가-힣]', text))
    en_words = len(re.findall(r'[a-zA-Z]{2,}', text))

    quote_keywords = [
        "어록", "말씀", "생명의 어록", "신천지", "약속의 목자", "교회 말씀",
        "quote", "quote of life", "shincheonji", "promised pastor", "church"
    ]
    has_keyword = any(kw in text.lower() for kw in quote_keywords)

    if has_keyword:
        return (ko_chars >= 8 and en_words >= 6)

    return (ko_chars >= 15 and en_words >= 10)


def is_image_quote_caption(text: str, has_photo: bool = False) -> bool:
    """
    사진과 함께 올라온 영문 생명의 어록 캡션인지 판별
    (사진에 한글이 이미 그래픽으로 박혀 있고 캡션은 영어인 유형)
    """
    if not text or not has_photo:
        return False

    lower = text.lower()
    quote_en_keywords = [
        "quote of life", "quote", "promised pastor",
        "word of life", "words of life", "shincheonji"
    ]
    is_quote = any(kw in lower for kw in quote_en_keywords)

    en_words = len(re.findall(r'[a-zA-Z]{2,}', text))
    ko_chars = len(re.findall(r'[가-힣]', text))

    # 캡션에 한글이 거의 없고, 영문이 풍부하며 어록 키워드가 있거나 영문 단어 15단어 이상
    if ko_chars < 5:
        if is_quote or en_words >= 15:
            return True

    return False


def extract_korean_section(text: str) -> str:
    """한-영 병기 텍스트에서 베트남어 번역을 위한 한글 원문 섹션 추출"""
    paragraphs = text.split("\n\n")
    ko_paragraphs = [p.strip() for p in paragraphs if re.search(r'[가-힣]', p) and p.strip()]
    if ko_paragraphs:
        return "\n\n".join(ko_paragraphs)
    lines = [line.strip() for line in text.splitlines() if re.search(r'[가-힣]', line) and line.strip()]
    return "\n".join(lines) if lines else text


def determine_translation_plan(
    text: str, mode: str = "all", has_photo: bool = False
) -> Tuple[List[Tuple[str, str]], str]:
    """
    메시지 내용 및 사진 첨부 여부에 따라 번역 대상 언어와 번역할 텍스트 결정
    반환값: (targets, text_to_translate)
    - targets: [(lang_code, flag_emoji), ...]
    - text_to_translate: 실제로 번역기에 전달할 텍스트
    """
    active = parse_active_languages(mode)
    if not active:
        return ([], "")

    # 1. 유형 1: 한글+영어 동시 수록된 텍스트 어록
    if is_bilingual_ko_en(text):
        # 이미 영문이 본문에 제공되었으므로 영어는 번역에서 제외하고 나머지 활성 외국어 번역
        remaining_langs = [k for k in ["vi", "zh", "es"] if k in active]
        if remaining_langs:
            ko_section = extract_korean_section(text)
            targets = [
                (SUPPORTED_TARGET_LANGUAGES[k]["target_code"], SUPPORTED_TARGET_LANGUAGES[k]["flag"])
                for k in remaining_langs
            ]
            return (targets, ko_section)
        # 영어 외에 다른 활성 언어가 없는 경우(예: 한-영 전용 방) 번역 불필요 (스킵)
        return ([], "")

    # 2. 유형 2: 사진(한글 이미지) + 영문 캡션 어록
    if is_image_quote_caption(text, has_photo=has_photo):
        # 사진에 한글이 있고 캡션에 영어가 있으므로 영어 제외 나머지 활성 외국어 번역
        remaining_langs = [k for k in ["vi", "zh", "es"] if k in active]
        if remaining_langs:
            targets = [
                (SUPPORTED_TARGET_LANGUAGES[k]["target_code"], SUPPORTED_TARGET_LANGUAGES[k]["flag"])
                for k in remaining_langs
            ]
            return (targets, text)
        return ([], "")

    # 3. 일반 메시지 처리
    source_lang = detect_source_language(text)
    if not source_lang:
        return ([], "")

    targets = get_translation_targets(source_lang, mode=mode)
    return (targets, text)


def translate_google_gtx(text: str, target_lang: str) -> Optional[str]:
    """Google GTX POST API 번역 (S6: 최대 입력 길이 4000자 제한 적용)"""
    if len(text) > 4000:
        text = text[:4000]

    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            "client": "gtx",
            "sl": "auto",
            "tl": target_lang,
            "dt": "t",
            "q": text,
        }
        post_data = urllib.parse.urlencode(params).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=post_data,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
            }
        )
        with urllib.request.urlopen(req, timeout=12) as response:
            content = response.read().decode("utf-8")
            data = json.loads(content)
            if data and isinstance(data, list) and len(data) > 0 and data[0]:
                parts = [p[0] for p in data[0] if p and len(p) > 0 and p[0]]
                result = "".join(parts).strip()
                if result and "Error 500" not in result and "That's an error" not in result:
                    return result
    except Exception as e:
        # S8: 에러 로그에 원문 텍스트 미포함 (언어 코드만 기록)
        logger.error(f"GTX translation error for target {target_lang}: {type(e).__name__}")
    return None


class UnifiedTranslationService:
    """통합 번역 서비스"""
    def __init__(self, deepl_api_key: str = "", glossary_manager=None):
        self.deepl_api_key = deepl_api_key.strip() if deepl_api_key else ""
        self.glossary_manager = glossary_manager
        self._deepl_translator: Optional[deepl.Translator] = None

        if self.deepl_api_key:
            try:
                self._deepl_translator = deepl.Translator(self.deepl_api_key)
                logger.info("External translation API initialized.")
            except Exception as e:
                logger.warning(f"External API init failed: {type(e).__name__}")

    def get_engine_name(self) -> str:
        base = "Primary API + GTX Engine" if self._deepl_translator else "GTX Translation Engine"
        if self.glossary_manager and self.glossary_manager.is_enabled() and self.glossary_manager.loaded_count > 0:
            return f"{base} + 용어집({self.glossary_manager.loaded_count}개 적용)"
        return base

    def _translate_free(self, text: str, target_lang: str) -> Optional[str]:
        gtx_res = translate_google_gtx(text, target_lang)
        if gtx_res:
            return gtx_res

        try:
            translator = GoogleTranslator(source='auto', target=target_lang)
            res = translator.translate(text)
            if res and "Error 500" not in res:
                return res
        except Exception as e:
            logger.error(f"Fallback translator error: {type(e).__name__}")

        return None

    def translate(self, text: str, target_lang: str) -> Optional[str]:
        # 1. 용어집 전처리 (활성화되어 있는 경우에만 호출)
        source_to_translate = text
        if self.glossary_manager and self.glossary_manager.is_enabled():
            try:
                source_to_translate = self.glossary_manager.preprocess_source(text)
            except Exception as e:
                logger.warning(f"Glossary pre-processing error: {e}")

        deepl_lang_map = {
            "en": "EN-US",
            "ko": "KO",
            "es": "ES",
            "zh": "ZH",
            "zh-cn": "ZH",
        }
        raw_result = None
        if target_lang == "vi":
            raw_result = self._translate_free(source_to_translate, "vi")
        elif self._deepl_translator and target_lang.lower() in deepl_lang_map:
            deepl_target = deepl_lang_map[target_lang.lower()]
            try:
                result = self._deepl_translator.translate_text(source_to_translate, target_lang=deepl_target)
                raw_result = result.text
            except Exception as e:
                logger.warning(f"Primary API error ({type(e).__name__}) -> Fallback to GTX")
                raw_result = self._translate_free(source_to_translate, target_lang)
        else:
            raw_result = self._translate_free(source_to_translate, target_lang)

        # 2. 용어집 후처리 치환 적용 (활성화되어 있는 경우에만 보정)
        if raw_result and self.glossary_manager and self.glossary_manager.is_enabled():
            try:
                raw_result = self.glossary_manager.apply_glossary(
                    translated_text=raw_result,
                    target_lang=target_lang,
                    source_text=source_to_translate
                )
            except Exception as e:
                logger.warning(f"Glossary post-processing error: {e}")

        return raw_result


