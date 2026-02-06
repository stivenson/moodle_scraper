"""Parser de fechas multi-formato para portales LMS."""
import re
from datetime import datetime
from typing import List, Optional


def parse_date(date_string: Optional[str], patterns: Optional[List[str]] = None) -> Optional[datetime]:
    """
    Parsea cadenas de fecha en varios formatos.
    patterns: regex opcionales del perfil para extraer fechas.
    """
    if not date_string:
        return None
    date_string = date_string.strip()
    if "31-12-1969" in date_string or "1969" in date_string:
        return None

    date_formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d/%m/%y",
        "%d-%m-%y",
        "%B %d, %Y",
        "%d %B %Y",
        "%d de %B de %Y",
        "%Y-%m-%d %H:%M:%S",
        "%d/%m/%Y %H:%M",
    ]
    for fmt in date_formats:
        try:
            parsed = datetime.strptime(date_string, fmt).date()
            if 2020 <= parsed.year <= datetime.now().year + 2:
                return datetime(parsed.year, parsed.month, parsed.day)
        except ValueError:
            continue

    regex_patterns = [
        r"(\d{4})-(\d{1,2})-(\d{1,2})",
        r"(\d{1,2})/(\d{1,2})/(\d{4})",
        r"(\d{1,2})-(\d{1,2})-(\d{4})",
        r"(\d{1,2})/(\d{1,2})/(\d{2})",
        r"(\d{1,2})-(\d{1,2})-(\d{2})",
    ]
    for pattern in regex_patterns:
        match = re.search(pattern, date_string)
        if match:
            try:
                if pattern.startswith(r"(\d{4})"):
                    year, month, day = match.groups()
                    year = int(year)
                else:
                    day, month, year = match.groups()
                    year = int(year)
                    if year < 100:
                        year += 2000 if year < 50 else 1900
                parsed = datetime(int(year), int(month), int(day)).date()
                if 2020 <= parsed.year <= datetime.now().year + 2:
                    return datetime(parsed.year, parsed.month, parsed.day)
            except ValueError:
                continue
    return None


def extract_date_from_text(text: str, profile_patterns: List[str]) -> Optional[str]:
    """Extrae la primera fecha encontrada en text usando los patrones del perfil."""
    import re
    for pattern in profile_patterns or []:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1) if match.lastindex and match.lastindex >= 1 else match.group(0)
    return None
