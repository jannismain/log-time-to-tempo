import re
from datetime import date, datetime, time, timedelta
from enum import Enum
from pathlib import Path

from calendar import MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY  # isort: skip (keep weekdays in order)


def parse_duration(s):
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
        return parse_past_weekday_relative(value)


def parse_date_dot(value: str) -> date:
    value = value.removesuffix('.')  # 22.2. -> 22.2
    parts = [int(x) for x in value.split('.')]
    date_args = {k: v for k, v in zip(['day', 'month', 'year'], parts)}
    if 'year' in date_args and date_args['year'] < 100:
        date_args['year'] += date.today().year // 100 * 100
    return date.today().replace(**date_args)


def parse_past_weekday_relative(value: str) -> date:
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
        raise ValueError(f'Unknown relative date: {value}')
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


def format_duration(duration: timedelta) -> str:
    hours, remainder = divmod(duration.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    return f'{hours}h{f" {minutes}m" if minutes else ""}'


class RelativeDateRange(str, Enum):
    TODAY = 'today'
    WEEK = 'week'
    WEEK_TO_DATE = 'week_to_date'
    MONTH = 'month'
    MONTH_TO_DATE = 'month_to_date'
    YEAR_TO_DATE = 'year'
    YESTERDAY = 'yesterday'
    LAST_WEEK = 'last_week'
    LAST_MONTH = 'last_month'
    LAST_YEAR = 'last_year'


def parse_relative_date_range(v: RelativeDateRange) -> tuple[date, date]:
    today = date.today()
    if v == RelativeDateRange.TODAY:
        return today, today
    elif v == RelativeDateRange.YESTERDAY:
        yesterday = today - timedelta(days=1)
        return yesterday, yesterday
    elif v == RelativeDateRange.WEEK:
        return today - timedelta(weeks=1), today
    elif v == RelativeDateRange.WEEK_TO_DATE:
        return last_monday(), today
    elif v == RelativeDateRange.LAST_WEEK:
        monday_last_week = last_monday() - timedelta(weeks=1)
        return monday_last_week, monday_last_week + timedelta(days=6)
    elif v == RelativeDateRange.MONTH:
        return today - timedelta(days=30), today
    elif v == RelativeDateRange.MONTH_TO_DATE:
        first_day_of_this_month = today.replace(day=1)
        return first_day_of_this_month, today
    elif v == RelativeDateRange.LAST_MONTH:
        last_day_of_last_month = today.replace(day=1) - timedelta(days=1)
        first_day_of_last_month = last_day_of_last_month.replace(day=1)
        return first_day_of_last_month, last_day_of_last_month
    elif v == RelativeDateRange.YEAR_TO_DATE:
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
