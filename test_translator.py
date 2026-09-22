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


class TestBilingualAndImageQuoteTranslation(unittest.TestCase):
    def test_type_1_bilingual_post_all_mode(self):
        from translator import determine_translation_plan, is_bilingual_ko_en

        text = (
            "💌 신 42(2025). 10. 12. 서울야고보지파 서울교회 말씀\n\n"
            '"그냥 입으로만 형식적으로 신앙한다 교회 간다, 그런 생각 그만하고 진짜로 이 말씀을 내 마음에 기록을 하면 '
            '내가 걸어 다니는 성경책이 되겠죠 몇 년이 됐는데 아직까지 그것을 못했다면 말이나 되겠습니까? '
            '신앙이라는 것이 뭡니까? 이 말씀이 영생의 말씀이죠. 예수의 피와 살을 먹어야 영생한다고 요 6장에 기록돼 있질 않습니까? '
            '이거를 마음에 인 맞아야만 이 말씀을 먹은 것이 되겠죠."\n\n'
            "💌 Shincheonji 42 (2025). October 12 — Word from Seoul Church, Seoul James Tribe\n\n"
            '“Let us stop thinking that faith is simply something we practice formally with our lips and simply by going to church. '
            'If I truly write this Word on my heart, then I will become a walking Bible, right? If several years have passed and I still have not done that, '
            'does that even make sense? What is faith? This Word is the Word of eternal life. Is it not written in John 6 that we must eat Jesus’ flesh '
            'and drink his blood in order to have eternal life? Only when this Word is sealed in our hearts can it be said that we have truly eaten this Word.”'
        )

        self.assertTrue(is_bilingual_ko_en(text))

        # all 모드: 이미 영문이 제공되었으므로 영문 번역은 제외하고 베트남어만 단독 번역
        targets, text_to_translate = determine_translation_plan(text, mode="all", has_photo=False)
        self.assertEqual(targets, [("vi", "🇻🇳")])
        self.assertIn("서울교회 말씀", text_to_translate)
        self.assertNotIn("Let us stop thinking", text_to_translate)

        # ko-en 모드: 한글과 영어가 이미 다 있으므로 번역 스킵 (빈 타겟)
        targets_koen, _ = determine_translation_plan(text, mode="ko-en", has_photo=False)
        self.assertEqual(targets_koen, [])

    def test_type_2_image_quote_caption(self):
        from translator import determine_translation_plan, is_image_quote_caption

        caption = (
            "📖 Quote of Life from the Promised Pastor\n\n"
            "At times, painful things overwhelm me.\n"
            "In anguish, I want to beat the ground and weep toward heaven.\n\n"
            "But at times like these,\n"
            "I look upon Jesus’ suffering on the cross.\n\n"
            "To once again look upon\n"
            "the suffering Jesus and his disciples endured as they faced death—\n\n"
            "this may be called\n"
            "“a heart that has become one,”\n"
            "born from the bond we have formed with Jesus."
        )

        self.assertTrue(is_image_quote_caption(caption, has_photo=True))
        # 사진이 없는 일반 텍스트인 경우 false
        self.assertFalse(is_image_quote_caption(caption, has_photo=False))

        # all 모드: 사진에 한글이 있으므로 캡션에 대해 베트남어만 번역
        targets, text_to_translate = determine_translation_plan(caption, mode="all", has_photo=True)
        self.assertEqual(targets, [("vi", "🇻🇳")])
        self.assertEqual(text_to_translate, caption)

        # ko-en 모드: 사진(한글)과 캡션(영어)이 이미 있으므로 번역 스킵
        targets_koen, _ = determine_translation_plan(caption, mode="ko-en", has_photo=True)
        self.assertEqual(targets_koen, [])

    def test_regular_messages_unaffected(self):
        from translator import determine_translation_plan

        # 일반 한글 메시지 -> all 모드에서 영+베 번역
        targets, _ = determine_translation_plan("안녕하세요! 오늘 공지사항 확인 부탁드립니다.", mode="all", has_photo=False)
        self.assertEqual(targets, [("en", "🇺🇸"), ("vi", "🇻🇳")])

        # 일반 한글 메시지 -> ko-en 모드에서 영어만 번역
        targets, _ = determine_translation_plan("안녕하세요! 오늘 공지사항 확인 부탁드립니다.", mode="ko-en", has_photo=False)
        self.assertEqual(targets, [("en", "🇺🇸")])

        # 일반 영어 메시지 -> all 모드에서 한+베 번역
        targets, _ = determine_translation_plan("Hello everyone, please check the announcement.", mode="all", has_photo=False)
        self.assertEqual(targets, [("ko", "🇰🇷"), ("vi", "🇻🇳")])

        # 일반 영어 메시지 -> ko-en 모드에서 한국어만 번역
        targets, _ = determine_translation_plan("Hello everyone, please check the announcement.", mode="ko-en", has_photo=False)
        self.assertEqual(targets, [("ko", "🇰🇷")])


class TestMaintenanceMode(unittest.TestCase):
    def test_maintenance_flag(self):
        import db
        db.init_db()
        initial_state = db.is_maintenance_mode()
        try:
            db.set_maintenance_mode(True)
            self.assertTrue(db.is_maintenance_mode())
            db.set_maintenance_mode(False)
            self.assertFalse(db.is_maintenance_mode())
        finally:
            db.set_maintenance_mode(initial_state)


if __name__ == "__main__":
    unittest.main()
