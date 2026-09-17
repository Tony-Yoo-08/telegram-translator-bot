import unittest
from translator import (
    detect_source_language,
    get_translation_targets,
    is_trivial_reaction,
)


class TestSecurityCompliantTranslator(unittest.TestCase):
    def test_language_detection(self):
        self.assertEqual(detect_source_language("안녕하세요! 반갑습니다."), "KO")
        self.assertEqual(detect_source_language("Xin chào tất cả mọi người"), "VI")
        self.assertEqual(detect_source_language("Hello everyone! Have a great day."), "EN")

    def test_target_languages_all_mode(self):
        targets = get_translation_targets("KO", mode="all")
        self.assertEqual(targets, [("en", "🇺🇸"), ("vi", "🇻🇳")])

        targets = get_translation_targets("VI", mode="all")
        self.assertEqual(targets, [("ko", "🇰🇷")])

        targets = get_translation_targets("EN", mode="all")
        self.assertEqual(targets, [("ko", "🇰🇷"), ("vi", "🇻🇳")])

    def test_short_reaction_filtering(self):
        self.assertTrue(is_trivial_reaction("아멘"))
        self.assertTrue(is_trivial_reaction("Amen 🙏"))
        self.assertTrue(is_trivial_reaction("dạ"))
        self.assertTrue(is_trivial_reaction("vâng"))
        self.assertTrue(is_trivial_reaction("ok"))
        self.assertTrue(is_trivial_reaction("네~"))

    def test_genuine_conversation_retained(self):
        self.assertFalse(is_trivial_reaction("아멘! 오늘 안내 공지 전달드립니다."))
        self.assertFalse(is_trivial_reaction("Xin chào! Hôm nay có thông báo gì không?"))
        self.assertFalse(is_trivial_reaction("Please review the attached schedule."))


class TestMessageEditAndReactionCache(unittest.TestCase):
    def setUp(self):
        from bot import PROCESSED_MESSAGE_TEXTS, BOT_TRANSLATION_REPLIES
        PROCESSED_MESSAGE_TEXTS.clear()
        BOT_TRANSLATION_REPLIES.clear()

    def test_message_edit_vs_reaction_flow(self):
        from bot import (
            get_cached_message_text,
            get_bot_reply_id,
            record_message_cache,
        )

        chat_id = -100123456789
        msg_id = 42

        # 1. 처음 메시지가 도착한 경우
        self.assertIsNone(get_cached_message_text(chat_id, msg_id))
        record_message_cache(chat_id, msg_id, "안녕하세요 반갑습니다", reply_id=1001)

        # 2. 동일 메시지에 리액션(반응 표시)이 달렸을 때: 텍스트 불변 확인 (재번역 스킵)
        current_text = "안녕하세요 반갑습니다"
        cached_text = get_cached_message_text(chat_id, msg_id)
        self.assertEqual(cached_text, current_text)

        # 3. 사용자가 메시지를 실제로 수정했을 때: 텍스트 변경 감지 (재번역 진행)
        edited_text = "안녕하세요 모두 반갑습니다!"
        self.assertNotEqual(cached_text, edited_text)

        # 번역 완료 후 캐시 및 기존 번역 답장 ID 갱신 확인
        record_message_cache(chat_id, msg_id, edited_text, reply_id=1001)
        self.assertEqual(get_cached_message_text(chat_id, msg_id), edited_text)
        self.assertEqual(get_bot_reply_id(chat_id, msg_id), 1001)


class TestTopicModeDefaults(unittest.TestCase):
    def test_default_topic_mode_is_all(self):
        import db
        # 미등록 신규 그룹일 때도 topic_mode가 all로 반환되는지 확인
        fake_chat_id = -999999999
        conf = db.get_group_config(fake_chat_id)
        self.assertEqual(conf.get("topic_mode"), "all")
        # 포럼 그룹의 미설정 토픽에서도 번역 활성화(True)로 판별되는지 확인
        enabled = db.is_topic_translation_enabled(fake_chat_id, thread_id=123, is_forum=True)
        self.assertTrue(enabled)


if __name__ == "__main__":
    unittest.main()
