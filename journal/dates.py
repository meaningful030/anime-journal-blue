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


def premiere_bounds(premiere):
    """Preserve month-only precision instead of inventing a premiere day."""
    if len(premiere) == 7:
        first = date.fromisoformat(premiere + '-01')
        if first.isoformat()[:7] != premiere:
            raise ValueError('Invalid premiere month')
        return first, date(first.year, first.month, monthrange(first.year, first.month)[1])
    first = date.fromisoformat(premiere)
    if first.isoformat() != premiere:
        raise ValueError('Invalid premiere date')
    return first, first


def category(premiere, today=None):
    today = today or taipei_today()
    if not premiere:
        return 'pending'
    first, last = premiere_bounds(premiere)
    cutoff = six_months_before(today)
    if last > today:
        return 'pending'
    if last < cutoff:
        return 'archive'
    return 'recent' if first >= cutoff else 'pending'
