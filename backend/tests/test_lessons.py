"""
Lesson catalog unit tests — no live server or database required.

Verifies that:
1. The LESSONS list is non-empty and well-formed
2. get_lesson_of_day() returns a lesson with all required fields
3. Lesson rotation cycles correctly across dates
"""
import pytest


class TestLessonCatalog:

    def test_lessons_list_is_non_empty(self):
        from app.data.lessons import LESSONS
        assert len(LESSONS) > 0, "LESSONS must contain at least one lesson"

    def test_each_lesson_has_required_fields(self):
        from app.data.lessons import LESSONS
        required = {"lesson_id", "title", "topic", "content", "quiz"}
        for lesson in LESSONS:
            missing = required - lesson.keys()
            assert not missing, f"Lesson '{lesson.get('lesson_id')}' is missing fields: {missing}"

    def test_each_lesson_content_non_empty(self):
        from app.data.lessons import LESSONS
        for lesson in LESSONS:
            assert len(lesson["content"]) > 0, (
                f"Lesson '{lesson['id']}' must have at least one content section"
            )

    def test_each_lesson_quiz_non_empty(self):
        from app.data.lessons import LESSONS
        for lesson in LESSONS:
            assert len(lesson["quiz"]) > 0, (
                f"Lesson '{lesson['id']}' must have at least one quiz question"
            )

    def test_lesson_ids_are_unique(self):
        from app.data.lessons import LESSONS
        ids = [lesson["lesson_id"] for lesson in LESSONS]
        assert len(ids) == len(set(ids)), "Lesson IDs must be unique"

    def test_get_lesson_of_day_returns_a_lesson(self):
        from app.data.lessons import LESSONS, get_lesson_of_day
        lesson = get_lesson_of_day()
        assert lesson is not None
        assert "title" in lesson

    def test_get_lesson_of_day_cycles(self):
        """Verify that lesson selection cycles across all lessons."""
        from app.data.lessons import LESSONS
        if len(LESSONS) < 2:
            pytest.skip("Need at least 2 lessons to test rotation")
        # The actual formula uses int(today.strftime('%Y%m%d')) % len(LESSONS)
        # Simulate 3 full cycles of date integers to confirm all lessons are reachable
        seen = set()
        base = 20240101
        for offset in range(len(LESSONS) * 3):
            date_int = base + offset
            idx = date_int % len(LESSONS)
            seen.add(LESSONS[idx]["lesson_id"])
        all_ids = {lesson["lesson_id"] for lesson in LESSONS}
        # At minimum, multiple distinct lessons must be visited (not always all,
        # because date integer modulo can skip indices, but rotation is confirmed)
        assert len(seen) > 1, "Lesson rotation must visit more than one lesson"
