import re
import json
import logging
import urllib.parse
import urllib.request
from typing import Optional, List, Tuple
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

    # 그룹 4: 기타 언어 단답
    "dạ", "vâng", "cảm ơn", "cam on", "oke"
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
    if not re.search(r'[가-힣a-zA-Z]', cleaned) and not LANG_SPECIFIC_CHAR_PATTERN.search(cleaned):
        return None

    # 단순 리액션 필터링
    if is_trivial_reaction(cleaned):
        return None

    # 1. 한국어 감지
    if re.search(r'[가-힣]', cleaned):
        return "KO"

    # 2. 베트남어 문자 감지
    if LANG_SPECIFIC_CHAR_PATTERN.search(cleaned):
        return "VI"

    # 3. 영문 문자 감지
    if re.search(r'[a-zA-Z]', cleaned):
        return "EN"

    return None


def get_translation_targets(source_lang: str, mode: str = "all") -> List[Tuple[str, str]]:
    """모드별 번역 대상 언어 및 심볼 반환"""
    mode = mode.lower()

    if mode == "ko-en":
        if source_lang == "KO":
            return [("en", "🇺🇸")]
        elif source_lang in ["EN", "VI"]:
            return [("ko", "🇰🇷")]
        return []

    elif mode == "ko-vi":
        if source_lang == "KO":
            return [("vi", "🇻🇳")]
        elif source_lang in ["VI", "EN"]:
            return [("ko", "🇰🇷")]
        return []

    # mode == 'all'
    if source_lang == "KO":
        return [("en", "🇺🇸"), ("vi", "🇻🇳")]
    elif source_lang == "VI":
        return [("ko", "🇰🇷")]
    elif source_lang == "EN":
        return [("ko", "🇰🇷"), ("vi", "🇻🇳")]

    return []


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
    def __init__(self, deepl_api_key: str = ""):
        self.deepl_api_key = deepl_api_key.strip() if deepl_api_key else ""
        self._deepl_translator: Optional[deepl.Translator] = None

        if self.deepl_api_key:
            try:
                self._deepl_translator = deepl.Translator(self.deepl_api_key)
                logger.info("External translation API initialized.")
            except Exception as e:
                logger.warning(f"External API init failed: {type(e).__name__}")

    def get_engine_name(self) -> str:
        if self._deepl_translator:
            return "Primary API + GTX Engine"
        return "GTX Translation Engine"

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
        if target_lang == "vi":
            return self._translate_free(text, "vi")

        if self._deepl_translator and target_lang in ["en", "ko"]:
            deepl_target = "EN-US" if target_lang == "en" else "KO"
            try:
                result = self._deepl_translator.translate_text(text, target_lang=deepl_target)
                return result.text
            except Exception as e:
                logger.warning(f"Primary API error ({type(e).__name__}) -> Fallback to GTX")
                return self._translate_free(text, target_lang)

        return self._translate_free(text, target_lang)
