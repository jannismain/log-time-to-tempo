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
        # Verify week labels are present (format: W followed by week number)
        assert 'W' in labels
        # Verify tickmarks are present for week labels
        assert '⎸' in labels

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
        # Verify tickmarks are present for month labels
        assert '⎸' in labels

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
        assert len(labels) <= workdays

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

    def test_axis_labels_dont_overflow(self):
        """Test that axis labels don't overflow the sparkline width."""
        # Create a very short range that would cause label cutoff
        from_date = date(2024, 10, 21)  # Monday
        to_date = date(2024, 10, 25)  # Friday (5 workdays)

        labels = generate_axis_labels(from_date, to_date, 'monthly')

        # Should have tickmark but no label text if it doesn't fit
        # The range is only 5 characters wide, so W43 (3 chars) + tickmark (1 char) = 4 chars
        # This should fit, but let's verify the length constraint
        assert len(labels) <= 5  # 5 workdays in the range

        # Create an even shorter range that would definitely cause cutoff
        from_date = date(2024, 10, 21)  # Monday
        to_date = date(2024, 10, 22)  # Tuesday (2 workdays)

        labels = generate_axis_labels(from_date, to_date, 'monthly')

        # Should have tickmark but no label text since W43 doesn't fit in 2 chars
        assert len(labels) <= 2  # 2 workdays in the range

    def test_axis_labels_align_with_sparkline(self):
        """Test that axis labels align properly with sparkline positions."""
        # Create a range that starts on Monday and spans multiple weeks
        from_date = date(2024, 10, 21)  # Monday
        to_date = date(2024, 11, 1)  # Friday (3 weeks)

        # Generate axis labels
        labels = generate_axis_labels(from_date, to_date, 'monthly')

        # Generate sparkline for the same range
        daily_data = {
            '21.10': {'timeSpentSeconds': 8 * 3600},
            '22.10': {'timeSpentSeconds': 6 * 3600},
            '23.10': {'timeSpentSeconds': 7 * 3600},
            '24.10': {'timeSpentSeconds': 8 * 3600},
            '25.10': {'timeSpentSeconds': 6 * 3600},
            '28.10': {'timeSpentSeconds': 7 * 3600},  # Monday of week 2
            '29.10': {'timeSpentSeconds': 8 * 3600},
            '30.10': {'timeSpentSeconds': 6 * 3600},
            '31.10': {'timeSpentSeconds': 7 * 3600},
            '01.11': {'timeSpentSeconds': 8 * 3600},  # Friday of week 3
        }
        sparkline = generate_sparkline_from_daily_data(daily_data, from_date, to_date)

        # Both should have the same length (number of workdays)
        assert len(sparkline) == len(labels)

        # Check that tickmarks align with week boundaries
        # The first tickmark should be at position 0 (first Monday)
        assert labels[0] == '⎸'
        # The second tickmark should be at position 5 (second Monday, after 5 workdays)
        assert labels[5] == '⎸'


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
