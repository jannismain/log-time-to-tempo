"""Tests for sparkline axis functionality."""

from datetime import date, timedelta

from log_time_to_tempo.cli._sparkline import (
    determine_date_range_type,
    generate_axis_labels,
    generate_sparkline_from_daily_data,
)


class TestDateRangeType:
    """Test date range type determination."""

    def test_weekly_range(self):
        """Test identification of weekly ranges."""
        today = date.today()
        from_date = today - timedelta(days=6)
        to_date = today
        assert determine_date_range_type(from_date, to_date) == 'weekly'

    def test_monthly_range(self):
        """Test identification of monthly ranges."""
        today = date.today()
        from_date = today - timedelta(days=29)
        to_date = today
        assert determine_date_range_type(from_date, to_date) == 'monthly'

    def test_yearly_range(self):
        """Test identification of yearly ranges."""
        today = date.today()
        from_date = today - timedelta(days=364)
        to_date = today
        assert determine_date_range_type(from_date, to_date) == 'yearly'

    def test_edge_cases(self):
        """Test edge cases for range type determination."""
        today = date.today()

        # Exactly 14 days should be weekly
        from_date = today - timedelta(days=13)
        to_date = today
        assert determine_date_range_type(from_date, to_date) == 'weekly'

        # 15 days should be monthly
        from_date = today - timedelta(days=14)
        to_date = today
        assert determine_date_range_type(from_date, to_date) == 'monthly'

        # 60 days should be monthly
        from_date = today - timedelta(days=59)
        to_date = today
        assert determine_date_range_type(from_date, to_date) == 'monthly'

        # 61 days should be yearly
        from_date = today - timedelta(days=60)
        to_date = today
        assert determine_date_range_type(from_date, to_date) == 'yearly'


class TestAxisLabels:
    """Test axis label generation."""

    def test_weekly_axis_empty(self):
        """Test that weekly ranges return empty axis labels."""
        today = date.today()
        from_date = today - timedelta(days=6)
        to_date = today
        labels = generate_axis_labels(from_date, to_date, 'weekly')
        assert labels == ''

    def test_monthly_axis_has_weeks(self):
        """Test that monthly ranges return week labels."""
        today = date.today()
        from_date = today - timedelta(days=29)
        to_date = today
        labels = generate_axis_labels(from_date, to_date, 'monthly')
        assert 'W1' in labels
        assert 'W' in labels

    def test_yearly_axis_has_months(self):
        """Test that yearly ranges return month labels."""
        today = date.today()
        from_date = today.replace(month=1, day=1)
        to_date = today
        labels = generate_axis_labels(from_date, to_date, 'yearly')
        assert any(
            month in labels
            for month in [
                'Jan',
                'Feb',
                'Mar',
                'Apr',
                'May',
                'Jun',
                'Jul',
                'Aug',
                'Sep',
                'Oct',
                'Nov',
                'Dec',
            ]
        )

    def test_axis_labels_length_matches_workdays(self):
        """Test that axis labels align with workdays in range."""
        # Test a range that spans exactly one week (Mon-Fri)
        today = date.today()
        # Find the most recent Monday
        days_since_monday = today.weekday()
        monday = today - timedelta(days=days_since_monday)
        friday = monday + timedelta(days=4)

        labels = generate_axis_labels(monday, friday, 'monthly')

        # Count workdays in the range
        workdays = 0
        current = monday
        while current <= friday:
            if current.weekday() < 5:
                workdays += 1
            current += timedelta(days=1)

        # Axis labels should not exceed the number of workdays
        assert len(labels.rstrip()) <= workdays

    def test_no_workdays_returns_empty(self):
        """Test that ranges with no workdays return empty labels."""
        # Create a weekend-only range
        today = date.today()
        # Find a Saturday
        while today.weekday() != 5:  # 5 = Saturday
            today += timedelta(days=1)

        saturday = today
        sunday = saturday + timedelta(days=1)

        labels = generate_axis_labels(saturday, sunday, 'monthly')
        assert labels == ''


class TestSparklineIntegration:
    """Test sparkline generation with axis compatibility."""

    def test_sparkline_generation_still_works(self):
        """Test that existing sparkline generation is not broken."""
        # Create some test data
        daily_data = {
            '01.01': {'timeSpentSeconds': 8 * 3600},  # 8 hours
            '02.01': {'timeSpentSeconds': 6 * 3600},  # 6 hours
            '03.01': {'timeSpentSeconds': 4 * 3600},  # 4 hours
        }

        from_date = date(2024, 1, 1)  # Monday
        to_date = date(2024, 1, 3)  # Wednesday

        sparkline = generate_sparkline_from_daily_data(daily_data, from_date, to_date)

        # Should generate a 3-character sparkline (3 workdays)
        assert len(sparkline) == 3
        assert sparkline != ''
