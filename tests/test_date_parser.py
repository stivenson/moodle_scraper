"""Tests para el parser de fechas."""
from datetime import datetime

import pytest

from lms_agent_scraper.core.date_parser import parse_date, extract_date_from_text


def test_parse_date_iso():
    assert parse_date("2024-01-15") == datetime(2024, 1, 15)


def test_parse_date_slash():
    assert parse_date("15/01/2024") == datetime(2024, 1, 15)


def test_parse_date_invalid():
    assert parse_date("") is None
    assert parse_date("31-12-1969") is None


def test_parse_date_regex():
    assert parse_date("Vencimiento: 20/12/2024") == datetime(2024, 12, 20)


def test_extract_date_from_text():
    patterns = [r"entrega.*?(\d{1,2}/\d{1,2}/\d{4})", r"(\d{1,2} de \w+ de \d{4})"]
    text = "Fecha de entrega: 25/03/2025"
    out = extract_date_from_text(text, patterns)
    assert out == "25/03/2025"
