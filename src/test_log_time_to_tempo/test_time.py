from datetime import date, time, timedelta

import pytest
from hypothesis import given
from hypothesis.strategies import dates, none

import log_time_to_tempo._time as _time


@pytest.mark.parametrize(
    'given,expected',
    [
        ('8h', timedelta(hours=8)),
        ('8h22m', timedelta(hours=8, minutes=22)),
        ('8h 22m', timedelta(hours=8, minutes=22)),
        ('8.75', timedelta(hours=8, minutes=45)),
        ('8', timedelta(hours=8)),
    ],
)
def test_parse_duration(given, expected):
    assert _time.parse_duration(given) == expected


@pytest.mark.parametrize(
    'duration,expected',
    [
        (timedelta(hours=8), '8h'),
        (timedelta(hours=8, minutes=22), '8h 22m'),
    ],
)
def test_format_duration(duration: timedelta, expected: str):
    assert _time.format_duration(duration) == expected


@pytest.mark.parametrize(
    'given,expected',
    [
        ('22', date(year=date.today().year, month=date.today().month, day=22)),
        ('23', date(year=date.today().year, month=date.today().month, day=23)),
        ('22.2', date(year=date.today().year, month=2, day=22)),
        ('22.3', date(year=date.today().year, month=3, day=22)),
        ('22.4.23', date(year=2023, month=4, day=22)),
        ('22.5.2023', date(year=2023, month=5, day=22)),
        # trailing dot should be stripped before parsing
        ('22.2.', date(year=date.today().year, month=2, day=22)),
        # default values might be None or date object -> should be passed through.
        (None, None),
        (date(year=2022, month=2, day=22), date(year=2022, month=2, day=22)),
        ('today', date.today()),
        ('yesterday', date.today() - timedelta(days=1)),
    ],
)
def test_parse_date(given, expected):
    assert _time.parse_date(given) == expected


@pytest.mark.parametrize(
    'given,expected',
    [
        ('0:00', time(0, 0)),
        ('9:00', time(9, 0)),
        ('23:59', time(23, 59)),
        ('9', time(9, 0)),
        ('18', time(18, 0)),
        # default values might be None or time object -> should be passed through.
        (None, None),
        (time(18, 0), time(18, 0)),
    ],
)
def test_parse_time(given, expected):
    assert _time.parse_time(given) == expected


@pytest.mark.parametrize(
    'given, exception_type',
    [
        ('24:01', ValueError),  # hour out of range
        ('12:67', ValueError),  # minute out of range
        ('12:5', ValueError),  # minute is missing leading zero
        ('24', ValueError),  # hour out of range
        ('12.1', ValueError),  # not a time string
    ],
)
def test_parse_time_failures(given, exception_type):
    with pytest.raises(exception_type):
        print(_time.parse_time(given))


def test_modified_within(tmp_path):
    new_file = tmp_path / 'new_file'
    new_file.touch()
    assert _time.modified_within(new_file, days=1), 'should be modified within last day'
    assert not _time.modified_within(new_file, days=-1), 'should not be modified within *next* day'


@given(dates() | none())
def test_last_monday(day):
    last_monday = _time.last_monday(day)

    if day is None:
        day = date.today()

    # last monday is never more than a week away
    assert day - last_monday < timedelta(weeks=1)


def test_parse_relative_date_range():
    # ranges that cover a single day
    for rng in [_time.RelativeDateRange.TODAY, _time.RelativeDateRange.YESTERDAY]:
        start, end = _time.parse_relative_date_range(rng)
        assert start == end

    # week-based ranges
    for rng in [_time.RelativeDateRange.LAST_WEEK, _time.RelativeDateRange.WEEK_TO_DATE]:
        start, end = _time.parse_relative_date_range(rng)
        assert end - start < timedelta(days=7), 'should never exceed a week'
        assert start.weekday() == 0, 'week should start on a Monday'

    start, end = _time.parse_relative_date_range(_time.RelativeDateRange.WEEK_TO_DATE)
    assert start == _time.last_monday(), 'week to date should start with last monday'

    start, end = _time.parse_relative_date_range(_time.RelativeDateRange.LAST_WEEK)
    assert start == _time.last_monday(date.today()) - timedelta(weeks=1), 'should start with Monday'

    # month-based ranges
    for rng in [_time.RelativeDateRange.LAST_MONTH, _time.RelativeDateRange.MONTH_TO_DATE]:
        start, end = _time.parse_relative_date_range(rng)
        assert end - start < timedelta(days=31), 'should never exceed a month'
        assert start.day == 1, 'month should start on the 1st'

    # year-based ranges
    for rng in [_time.RelativeDateRange.LAST_YEAR, _time.RelativeDateRange.YEAR_TO_DATE]:
        start, end = _time.parse_relative_date_range(rng)
        assert end - start < timedelta(days=366), 'should never exceed a year'
        assert start.day == 1 and start.month == 1, 'year should start on 1st of January'

    start, end = _time.parse_relative_date_range(_time.RelativeDateRange.LAST_YEAR)
    assert end.day == 31 and end.month == 12, 'last year should end on the 31st of December'

    # ranges that end with today
    for rng in [
        _time.RelativeDateRange.TODAY,
        _time.RelativeDateRange.WEEK_TO_DATE,
        _time.RelativeDateRange.MONTH_TO_DATE,
        _time.RelativeDateRange.YEAR_TO_DATE,
    ]:
        start, end = _time.parse_relative_date_range(rng)
        assert end == date.today(), 'x to date should end with today'

    with pytest.raises(ValueError):
        _time.parse_relative_date_range(None)


@pytest.mark.parametrize(
    'd, expected',
    [
        (date.today(), 'today'),
        (date.today() - timedelta(days=1), 'yesterday'),
        (date(year=date.today().year, month=3, day=12), '12.3'),
        (date(year=date.today().year - 1, month=3, day=12), f'12.3.{date.today().year-1}'),
    ],
)
def test_format_date_relative(d, expected):
    assert _time.format_date_relative(d) == expected
