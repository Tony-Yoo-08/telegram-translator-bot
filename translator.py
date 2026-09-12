import re
import logging
from typing import Optional, Tuple
import deepl
from deep_translator import GoogleTranslator

logger = logging.getLogger(__name__)

# URL 및 멘션 정규식
URL_PATTERN = re.compile(r'https?://\S+|www\.\S+')
MENTION_PATTERN = re.compile(r'@\w+')

# 특수기호, 문장부호, 대표적인 리액션 이모지 제거용 정규식
PUNCT_AND_EMOJI = re.compile(r'[\s!~.?,\^;:\-_/\\()\[\]{}@#$%&*+=\'\"|🙏❤️✨🙌👏🙇👍😊😄😃😀]+')

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
    """
    단순 감탄사, 아멘, 단답형 리액션 등 번역할 가치가 없는 사소한 메시지인지 판별
    (대화나 공지 내용 등 실질적인 문장은 False 반환하여 번역 진행)
    """
    # 자음/모음만 있는 경우 (ㅋㅋ, ㅎㅎ, ㅠㅠ 등)
    if re.fullmatch(r'^[ㄱ-ㅎㅏ-ㅣ\s]+$', text):
        return True

    # "아멘", "Amen", "아멘 아멘 🙏" 등 반복적인 아멘/종교적 리액션인 경우
    if REPEATING_AMEN_PATTERN.fullmatch(text):
        return True

    # 기호, 문장부호, 이모지를 모두 떼어낸 순수 텍스트 추출
    stripped = PUNCT_AND_EMOJI.sub('', text).lower()
    if not stripped:
        return True

    # 순수 텍스트가 단답형 리액션 목록에 포함된 경우 (예: "아멘!", "Amen🙏", "감사합니다~~")
    if stripped in IGNORED_EXACT_WORDS:
        return True

    return False


def detect_target_language(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    텍스트를 분석하여 번역 대상 언어를 결정합니다.
    Returns:
        (target_lang, flag)
        - 한글 포함 -> ("en", "🇺🇸")
        - 영어 위주 -> ("ko", "🇰🇷")
        - 번역 불필요 (사소한 리액션/아멘/기호 등) -> (None, None)
    """
    if not text or not text.strip():
        return None, None

    # 명령어(/로 시작)는 제외
    if text.strip().startswith('/'):
        return None, None

    cleaned = preprocess_text(text)
    if not cleaned:
        return None, None

    # 단순 기호/숫자/이모지만 있는 경우 제외
    if not re.search(r'[가-힣a-zA-Z]', cleaned):
        return None, None

    # 사소한 리액션(아멘, Amen, ㅋㅋ, ok 등) 필터링
    if is_trivial_reaction(cleaned):
        return None, None

    # 1. 한글 음절이 포함되어 있으면 -> 영어로 번역
    # (한국어가 섞인 한영 혼용 문장이나 공지도 외국인을 위해 영어로 번역)
    if re.search(r'[가-힣]', cleaned):
        return "en", "🇺🇸"

    # 2. 한글은 없고 영문 알파벳이 있으면 -> 한국어로 번역
    if re.search(r'[a-zA-Z]', cleaned):
        return "ko", "🇰🇷"

    return None, None


class UnifiedTranslationService:
    """
    DeepL API 키가 있으면 공식 DeepL API를 사용하고,
    키가 없거나 오류 발생 시 완전 무료 무키(Keyless) 엔진(deep-translator)으로 자동 처리하는 서비스
    """
    def __init__(self, deepl_api_key: str = ""):
        self.deepl_api_key = deepl_api_key.strip() if deepl_api_key else ""
        self._deepl_translator: Optional[deepl.Translator] = None

        if self.deepl_api_key:
            try:
                self._deepl_translator = deepl.Translator(self.deepl_api_key)
                logger.info("공식 DeepL API가 성공적으로 초기화되었습니다.")
            except Exception as e:
                logger.warning(f"DeepL 번역기 초기화 실패 (무료 엔진으로 대체합니다): {e}")

    def get_engine_name(self) -> str:
        if self._deepl_translator:
            return "공식 DeepL API"
        return "무료 번역 엔진 (deep-translator / API키 불필요)"

    def is_deepl_active(self) -> bool:
        return bool(self._deepl_translator)

    def _translate_free(self, text: str, target_lang: str) -> Optional[str]:
        """무료 엔진(GoogleTranslator)을 통한 무키 번역"""
        try:
            translator = GoogleTranslator(source='auto', target=target_lang)
            return translator.translate(text)
        except Exception as e:
            logger.error(f"무료 번역 엔진 오류: {e}")
            return None

    def translate(self, text: str, target_lang: str) -> Optional[str]:
        """
        target_lang: 'en' 또는 'ko'
        """
        # 1. DeepL API 키가 있는 경우 DeepL 우선 시도
        if self._deepl_translator:
            deepl_target = "EN-US" if target_lang.lower().startswith("en") else "KO"
            try:
                result = self._deepl_translator.translate_text(text, target_lang=deepl_target)
                return result.text
            except deepl.exceptions.QuotaExceededException:
                logger.warning("DeepL 사용량 한도 초과. 무료 번역 엔진으로 자동 대체합니다.")
                return self._translate_free(text, target_lang)
            except Exception as e:
                logger.warning(f"DeepL 번역 실패 ({e}). 무료 번역 엔진으로 자동 대체합니다.")
                return self._translate_free(text, target_lang)

        # 2. DeepL 키가 없는 경우 무료 번역 엔진 실행
        return self._translate_free(text, target_lang)
