import re
from datetime import date, datetime, time, timedelta
from enum import Enum
from pathlib import Path

from calendar import MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY  # isort: skip (keep weekdays in order)
import dateparser


def parse_duration(s: str) -> timedelta:
    try:
        return parse_duration_float(s)
    except ValueError:
        return parse_duration_combined(s)


def parse_duration_float(s: str) -> timedelta:
    return timedelta(hours=float(s))


def parse_duration_combined(s: str) -> timedelta:
    """Parse a duration string into a timedelta object."""
    pattern = r'(?:(\d+)h)?\s?(?:(\d+)m)?'  # https://regexr.com/7sem2
    match = re.match(pattern, s)
    hours, minutes = match.groups(default='0')
    return timedelta(hours=int(hours), minutes=int(minutes))


def parse_time(value: str | time) -> time:
    """Parse a time string into a time object.

    The input may be
        - a single number representing the hour.
        - a time string in the format "H:MM"
    """
    if value is None or isinstance(value, time):
        return value

    if value.isdigit():
        return time(int(value), 0)

    value_tuple = value.split(':')
    if not all(len(x) == 2 for x in value_tuple[1:]):
        raise ValueError(f'Invalid time format: {value}')

    return time(*[int(x) for x in value_tuple])


def parse_date(value: str | date) -> date:
    if value is None or isinstance(value, date):
        return value
    if value.isnumeric():
        return date.today().replace(day=int(value))
    if '.' in value:
        return parse_date_dot(value)
    else:
        try:
            return parse_past_weekday_relative(value)
        except ValueError:
            return dateparser.parse(value).date()


def parse_date_dot(value: str) -> date:
    value = value.removesuffix('.')  # 22.2. -> 22.2
    parts = [int(x) for x in value.split('.')]
    date_args = {k: v for k, v in zip(['day', 'month', 'year'], parts)}
    if 'year' in date_args and date_args['year'] < 100:
        date_args['year'] += date.today().year // 100 * 100
    return date.today().replace(**date_args)


def parse_past_weekday_relative(value: str) -> date:
    original_value = value
    value = value.lower()
    if value == 'today':
        return date.today()
    elif value in {'yesterday', 'y'}:
        return date.today() - timedelta(days=1)
    elif value in {'monday', 'mon', 'mo', 'm', 'montag'}:
        day = MONDAY
    elif value in {'tuesday', 'tue', 'tu', 'di', 'dienstag'}:
        day = TUESDAY
    elif value in {'wednesday', 'wed', 'we', 'w', 'mi', 'mittwoch'}:
        day = WEDNESDAY
    elif value in {'thursday', 'thu', 'th', 'do', 'donnerstag'}:
        day = THURSDAY
    elif value in {'friday', 'fri', 'fr', 'f', 'freitag'}:
        day = FRIDAY
    else:
        raise ValueError(f'Unknown relative date: {original_value}')
    # if day is in the future, assume last week
    if day > date.today().weekday():
        return date.today() - timedelta(weeks=1, days=date.today().weekday() - day)
    else:
        return date.today() - timedelta(days=date.today().weekday() - day)


def last_monday(day: date = None) -> date:
    if day is None:
        day = date.today()
    # Monday is 0 and Sunday is 6
    last_monday = day - timedelta(days=day.weekday() % 7)
    return last_monday


def modified_within(f: Path, **kwargs) -> bool:
    """Checks whether file was modified within given time.

    Args:
        f: check modification time of this file

    Keyword Arguments:
        Takes all arguments that `datetime.timedelta` accepts:
        `weeks`, `days`, `hours`, `minutes`, `seconds`, `microseconds`, `milliseconds`
    """
    return f.stat().st_mtime > (datetime.now() - timedelta(**kwargs)).timestamp()


def _duration_to_hours_and_minutes(duration: timedelta) -> tuple[int, int]:
    hours, remainder = divmod(int(duration.total_seconds()), 60 * 60)
    minutes, _ = divmod(remainder, 60)
    return hours, minutes


def format_duration(duration: timedelta) -> str:
    hours, minutes = _duration_to_hours_and_minutes(duration)
    return f'{hours}h{f" {minutes}m" if minutes else ""}'


def format_duration_aligned(duration: timedelta, max_hour_digits=3) -> str:
    hours, minutes = _duration_to_hours_and_minutes(duration)
    return f'{hours:{max_hour_digits}d}h{f" {minutes}m" if minutes else "    "}'


class RelativeDateRange(str, Enum):
    TODAY = 'today'
    LAST_SEVEN_DAYS = 'last_7_days'
    WEEK = 'week'
    LAST_30_DAYS = 'last_30_days'
    MONTH = 'month'
    YEAR = 'year'
    YESTERDAY = 'yesterday'
    LAST_WEEK = 'last_week'
    LAST_MONTH = 'last_month'
    LAST_YEAR = 'last_year'


relative_date_range_abbreviations = {
    RelativeDateRange.TODAY: {'day', 'd'},
    RelativeDateRange.LAST_SEVEN_DAYS: {'l7'},
    RelativeDateRange.WEEK: {'w'},
    RelativeDateRange.LAST_30_DAYS: {'l30'},
    RelativeDateRange.MONTH: {'m'},
    RelativeDateRange.YESTERDAY: {'y'},
    RelativeDateRange.LAST_WEEK: {'lw'},
    RelativeDateRange.LAST_MONTH: {'lm'},
    RelativeDateRange.LAST_YEAR: {'ly'},
}


def resolve_relative_date_range(v: str) -> RelativeDateRange:
    if any(v in syn for syn in relative_date_range_abbreviations.values()):
        v = next(k for k, syn in relative_date_range_abbreviations.items() if v in syn)
    else:
        v = RelativeDateRange(v)
    return v


def parse_relative_date_range(v: RelativeDateRange | str) -> tuple[date, date]:
    today = date.today()
    v = resolve_relative_date_range(v)
    if v == RelativeDateRange.TODAY:
        return today, today
    elif v == RelativeDateRange.YESTERDAY:
        yesterday = today - timedelta(days=1)
        return yesterday, yesterday
    elif v == RelativeDateRange.LAST_SEVEN_DAYS:
        return today - timedelta(weeks=1), today
    elif v == RelativeDateRange.WEEK:
        return last_monday(), today
    elif v == RelativeDateRange.LAST_WEEK:
        monday_last_week = last_monday() - timedelta(weeks=1)
        return monday_last_week, monday_last_week + timedelta(days=6)
    elif v == RelativeDateRange.LAST_30_DAYS:
        return today - timedelta(days=30), today
    elif v == RelativeDateRange.MONTH:
        first_day_of_this_month = today.replace(day=1)
        return first_day_of_this_month, today
    elif v == RelativeDateRange.LAST_MONTH:
        last_day_of_last_month = today.replace(day=1) - timedelta(days=1)
        first_day_of_last_month = last_day_of_last_month.replace(day=1)
        return first_day_of_last_month, last_day_of_last_month
    elif v == RelativeDateRange.YEAR:
        first_day_of_year = today.replace(month=1, day=1)
        return first_day_of_year, today
    elif v == RelativeDateRange.LAST_YEAR:
        first_day_of_last_year = today.replace(year=today.year - 1, month=1, day=1)
        last_day_of_last_year = today.replace(year=today.year - 1, month=12, day=31)
        return first_day_of_last_year, last_day_of_last_year
    else:
        raise ValueError(f'Unknown date range: {v}')


def format_date_relative(d: date):
    today = date.today()
    if d == today:
        return 'today'
    if d == today - timedelta(days=1):
        return 'yesterday'
    if d.year == date.today().year:
        return d.strftime('%-d.%-m')
    return d.strftime('%-d.%-m.%-Y')
