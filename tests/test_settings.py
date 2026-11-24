from lms_agent_scraper.config.settings import ScraperSettings


def test_target_courses_are_configurable_and_default_to_all_courses(monkeypatch):
    monkeypatch.delenv("SCRAPER_TARGET_COURSES", raising=False)
    settings = ScraperSettings(_env_file=None)
    assert settings.target_courses == ""

    monkeypatch.setenv("SCRAPER_TARGET_COURSES", "Biología,Historia")
    settings = ScraperSettings(_env_file=None)
    assert settings.target_courses == "Biología,Historia"
