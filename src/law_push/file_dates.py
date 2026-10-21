"""Local file generation timestamps shared by export and push commands."""

from datetime import date, datetime

FILE_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def format_file_date(value):
    """Legacy dates use midnight; never invent a generation time when pushing."""
    if isinstance(value, datetime):
        return value.strftime(FILE_DATE_FORMAT)
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time()).strftime(FILE_DATE_FORMAT)
    text = str(value or "").strip()
    for fmt in (FILE_DATE_FORMAT, "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(text, fmt)
        except ValueError:
            continue
        if parsed.strftime(fmt) == text:
            return parsed.strftime(FILE_DATE_FORMAT)
    raise ValueError("file date must be YYYY-MM-DD HH:MM:SS (or legacy YYYY-MM-DD)")
