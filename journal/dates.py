from calendar import monthrange
from datetime import date, datetime
from zoneinfo import ZoneInfo


def taipei_today():
    return datetime.now(ZoneInfo('Asia/Taipei')).date()


def six_months_before(day):
    index = day.year * 12 + day.month - 1 - 6
    year, month = divmod(index, 12)
    month += 1
    return date(year, month, min(day.day, monthrange(year, month)[1]))


def category(premiere, today=None):
    today = today or taipei_today()
    if not premiere:
        return 'pending'
    aired = date.fromisoformat(premiere)
    if aired > today:
        return 'pending'
    return 'recent' if aired >= six_months_before(today) else 'archive'
