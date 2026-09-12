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

# 특수기호, 문장부호, 대표적인 리액션 이모지 제거용 정규식
PUNCT_AND_EMOJI = re.compile(r'[\s!~.?,\^;:\-_/\\()\[\]{}@#$%&*+=\'\"|🙏❤️✨🙌👏🙇👍😊😄😃😀]+')

# 베트남어 고유 특수문자 및 성조 문자 정규식
VIETNAMESE_PATTERN = re.compile(
    r'[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ'
    r'ÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴĐ]'
)

# 1. 단답형 리액션/감탄사로만 이루어진 경우 번역에서 제외할 단어 목록
IGNORED_EXACT_WORDS = {
    # 종교적/신앙적 단답 리액션
    "아멘", "amen", "아멘입니다", "아멘요",
    "샬롬", "shalom", "할렐루야", "hallelujah",
    "기도합니다", "축복합니다", "은혜롭습니다",
    
    # 한국어 단순 감탄사/대답
    "네", "넵", "넹", "넴", "예", "응", "어", "아니", "아뇨", "아닙니다",
    "오키", "오케이", "ㅇㅋ", "알겠습니다", "확인했습니다",
    "감사", "감사합니다", "고마워", "고마워요", "수고", "수고하셨습니다", "수고하세요",
    "축하", "축하합니다", "축하해요", "축하드려요",
    "하이", "바이", "굿", "좋아요", "대박",
    
    # 영어 단순 리액션
    "ok", "okay", "yes", "yeah", "yep", "no", "nope",
    "thx", "thanks", "thankyou", "thank",
    "ty", "k", "gg", "lol", "nvm", "np", "pls", "plz", "sry", "sorry",
    "good", "great", "nice", "cool", "wow", "omg", "congrats",

    # 베트남어 단순 리액션
    "dạ", "vâng", "cảm ơn", "cam on", "ok", "oke"
}

# 2. "아멘 아멘", "Amen Amen 🙏" 처럼 특정 단어가 반복되는 패턴 정규식
REPEATING_AMEN_PATTERN = re.compile(
    r'^((아멘|amen|샬롬|shalom|할렐루야|hallelujah)[\s!~.?🙏❤️✨🙌👏🙇]*)+$',
    re.IGNORECASE
)


def preprocess_text(text: str) -> str:
    """URL, 멘션 등을 임시 제거하여 실제 번역할 텍스트 내용만 추출"""
    cleaned = URL_PATTERN.sub('', text)
    cleaned = MENTION_PATTERN.sub('', cleaned)
    return cleaned.strip()


def is_trivial_reaction(text: str) -> bool:
    """단순 감탄사, 아멘, 단답형 리액션 등 번역할 가치가 없는 사소한 메시지인지 판별"""
    if re.fullmatch(r'^[ㄱ-ㅎㅏ-ㅣ\s]+$', text):
        return True

    if REPEATING_AMEN_PATTERN.fullmatch(text):
        return True

    stripped = PUNCT_AND_EMOJI.sub('', text).lower()
    if not stripped:
        return True

    if stripped in IGNORED_EXACT_WORDS:
        return True

    return False


def detect_source_language(text: str) -> Optional[str]:
    """텍스트의 언어를 감지하여 "KO", "VI", "EN" 중 하나를 반환"""
    if not text or not text.strip():
        return None

    if text.strip().startswith('/'):
        return None

    cleaned = preprocess_text(text)
    if not cleaned:
        return None

    # 단순 기호/숫자/이모지만 있는 경우 제외
    if not re.search(r'[가-힣a-zA-Z]', cleaned) and not VIETNAMESE_PATTERN.search(cleaned):
        return None

    # 사소한 리액션 필터링
    if is_trivial_reaction(cleaned):
        return None

    # 1. 한국어 감지
    if re.search(r'[가-힣]', cleaned):
        return "KO"

    # 2. 베트남어 특수 문자 감지
    if VIETNAMESE_PATTERN.search(cleaned):
        return "VI"

    # 3. 영문 / 라틴 문자 감지
    if re.search(r'[a-zA-Z]', cleaned):
        return "EN"

    return None


def get_translation_targets(source_lang: str, mode: str = "all") -> List[Tuple[str, str]]:
    """모드별 번역 목적지 언어 반환"""
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

    # mode == "all" (한-영-베 동시 모드)
    if source_lang == "KO":
        return [("en", "🇺🇸"), ("vi", "🇻🇳")]
    elif source_lang == "VI":
        return [("ko", "🇰🇷")]
    elif source_lang == "EN":
        return [("ko", "🇰🇷"), ("vi", "🇻🇳")]

    return []


def translate_google_gtx(text: str, target_lang: str) -> Optional[str]:
    """
    Google GTX 공식 JSON API (POST 방식)
    줄바꿈, 긴 공지사항, 특수문자, 클라우드 IP 차단 문제를 완벽하게 해결하는 고신뢰 무료 번역기
    """
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
                # 500 에러 문자열이 섞여 들어오지 않았는지 검증
                if result and "Error 500" not in result and "That's an error" not in result:
                    return result
    except Exception as e:
        logger.error(f"GTX API 번역 오류 ({target_lang}): {e}")
    return None


class UnifiedTranslationService:
    """통합 번역 서비스: DeepL(키 있을 시) 또는 고성능 GTX API(기본) 사용"""
    def __init__(self, deepl_api_key: str = ""):
        self.deepl_api_key = deepl_api_key.strip() if deepl_api_key else ""
        self._deepl_translator: Optional[deepl.Translator] = None

        if self.deepl_api_key:
            try:
                self._deepl_translator = deepl.Translator(self.deepl_api_key)
                logger.info("공식 DeepL API가 초기화되었습니다.")
            except Exception as e:
                logger.warning(f"DeepL 초기화 실패: {e}")

    def get_engine_name(self) -> str:
        if self._deepl_translator:
            return "공식 DeepL API + Google GTX 엔진"
        return "Google GTX 고성능 무료 번역 엔진"

    def _translate_free(self, text: str, target_lang: str) -> Optional[str]:
        # 1. Google GTX POST API 우선 호출 (긴 글, 줄바꿈, 500 에러 방지)
        gtx_res = translate_google_gtx(text, target_lang)
        if gtx_res:
            return gtx_res

        # 2. 예비 폴백 (deep-translator)
        try:
            translator = GoogleTranslator(source='auto', target=target_lang)
            res = translator.translate(text)
            if res and "Error 500" not in res:
                return res
        except Exception as e:
            logger.error(f"deep-translator 오류: {e}")

        return None

    def translate(self, text: str, target_lang: str) -> Optional[str]:
        # 베트남어는 Google GTX 엔진 사용
        if target_lang == "vi":
            return self._translate_free(text, "vi")

        # 영어/한국어이고 DeepL 키가 있는 경우 DeepL 우선 시도
        if self._deepl_translator and target_lang in ["en", "ko"]:
            deepl_target = "EN-US" if target_lang == "en" else "KO"
            try:
                result = self._deepl_translator.translate_text(text, target_lang=deepl_target)
                return result.text
            except Exception as e:
                logger.warning(f"DeepL 실패 ({e}) -> GTX 엔진으로 대체")
                return self._translate_free(text, target_lang)

        # 기본 무료 GTX 엔진 실행
        return self._translate_free(text, target_lang)
