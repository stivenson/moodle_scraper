"""Tests para detección de cursos por segmento de URL (browser_tools)."""
import pytest

from lms_agent_scraper.tools.browser_tools import (
    DEFAULT_COURSE_LINK_SEGMENTS,
    _get_course_link_segments_from_profile,
    _is_course_url_by_segment,
    _extract_courses_by_link_segment,
)


BASE = "https://aulapregrado.unisimon.edu.co"


class TestIsCourseUrlBySegment:
    """Tests para _is_course_url_by_segment."""

    def test_course_in_path_accepts(self):
        assert _is_course_url_by_segment(
            "https://aulapregrado.unisimon.edu.co/course/view.php?id=3417",
            BASE,
            ["course", "courses", "cursos"],
        ) is True

    def test_courses_in_path_accepts(self):
        assert _is_course_url_by_segment(
            "https://example.edu/courses/123",
            "https://example.edu",
            ["course", "courses", "cursos"],
        ) is True

    def test_cursos_in_path_accepts(self):
        assert _is_course_url_by_segment(
            "/cursos/ver?id=1",
            BASE,
            ["course", "courses", "cursos"],
        ) is True

    def test_case_insensitive(self):
        assert _is_course_url_by_segment(
            "https://example.edu/Cursos/view",
            "https://example.edu",
            ["course", "cursos"],
        ) is True
        assert _is_course_url_by_segment(
            "https://example.edu/COURSE/1",
            "https://example.edu",
            ["course"],
        ) is True

    def test_no_keyword_in_path_rejects(self):
        assert _is_course_url_by_segment(
            "https://example.edu/mod/assign/view.php?id=1",
            "https://example.edu",
            ["course", "courses", "cursos"],
        ) is False

    def test_keyword_only_in_query_rejects(self):
        assert _is_course_url_by_segment(
            "https://example.edu/view.php?course=1",
            "https://example.edu",
            ["course"],
        ) is False

    def test_relative_url_with_course_accepts(self):
        assert _is_course_url_by_segment(
            "/course/view.php?id=3418",
            BASE,
            ["course", "courses", "cursos"],
        ) is True

    def test_empty_keywords_rejects(self):
        assert _is_course_url_by_segment("/course/view.php", BASE, []) is False


class TestGetCourseLinkSegmentsFromProfile:
    """Tests para _get_course_link_segments_from_profile."""

    def test_default_when_empty_profile(self):
        assert _get_course_link_segments_from_profile({}) == DEFAULT_COURSE_LINK_SEGMENTS
        assert _get_course_link_segments_from_profile(None) == DEFAULT_COURSE_LINK_SEGMENTS

    def test_course_link_segments_list(self):
        profile = {"course_link_segments": ["course", "curso"]}
        assert _get_course_link_segments_from_profile(profile) == ["course", "curso"]

    def test_course_link_segment_singular(self):
        profile = {"course_link_segment": "materia"}
        assert _get_course_link_segments_from_profile(profile) == ["materia"]

    def test_plural_takes_precedence_over_singular(self):
        profile = {"course_link_segments": ["a", "b"], "course_link_segment": "x"}
        assert _get_course_link_segments_from_profile(profile) == ["a", "b"]


class TestExtractCoursesByLinkSegment:
    """Tests para _extract_courses_by_link_segment."""

    def test_extracts_course_links_from_html(self):
        html = """
        <html><body>
        <a href="https://aulapregrado.unisimon.edu.co/course/view.php?id=3417">Algebra Lineal</a>
        <a href="/course/view.php?id=3418">Fisica I</a>
        <a href="#">No course</a>
        </body></html>
        """
        result = _extract_courses_by_link_segment(html, BASE, None)
        assert len(result) >= 2
        urls = [r["url"] for r in result]
        names = [r["name"] for r in result]
        assert any("3417" in u for u in urls)
        assert any("3418" in u for u in urls)
        assert "Algebra Lineal" in names or "Fisica I" in names

    def test_deduplicates_by_url(self):
        html = """
        <html><body>
        <a href="/course/view.php?id=1">Curso A</a>
        <a href="/course/view.php?id=1">Curso A again</a>
        </body></html>
        """
        result = _extract_courses_by_link_segment(html, BASE, None)
        assert len(result) == 1

    def test_uses_profile_keywords(self):
        html = '<html><body><a href="/materias/1">Matemáticas</a></body></html>'
        profile = {"course_link_segments": ["materias"]}
        result = _extract_courses_by_link_segment(html, BASE, profile)
        assert len(result) == 1
        assert "materias" in result[0]["url"]
        assert result[0]["name"] == "Matemáticas"

    def test_empty_html_returns_empty(self):
        assert _extract_courses_by_link_segment("", BASE, None) == []
        assert _extract_courses_by_link_segment("<html></html>", BASE, None) == []
