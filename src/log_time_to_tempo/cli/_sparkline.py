"""Sparkline utilities for visualizing time data."""

from datetime import date, timedelta
from typing import Dict

from sparklines import sparklines


def generate_sparkline_from_daily_data(
    daily_data: Dict[str, Dict[str, int]],
    from_date: date,
    to_date: date,
    **kwargs,
) -> str:
    """Generate a sparkline from daily time data.

    Args:
        daily_data: Dictionary with date strings as keys (e.g., '15.12') and
                   values containing 'timeSpentSeconds'
        from_date: Start date for the sparkline
        to_date: End date for the sparkline
        kwargs: Additional keyword arguments for sparklines

    Returns:
        String representation of the sparkline
    """
    # Generate list of values for each day in the range
    daily_values = []
    current_date = from_date

    while current_date <= to_date:
        if current_date.weekday() < 5:  # skip weekends
            date_str = current_date.strftime('%d.%m')
            time_spent = daily_data.get(date_str, {}).get('timeSpentSeconds', 0)
            daily_values.append(time_spent)
        current_date += timedelta(days=1)

    if not daily_values or all(v == 0 for v in daily_values):
        return ''

    # Convert to hours for better visualization
    daily_hours = [v / 3600 for v in daily_values]

    # Generate sparkline
    return sparklines(daily_hours, **kwargs)[0]


def determine_date_range_type(from_date: date, to_date: date) -> str:
    """Determine if the date range is yearly, monthly, or weekly.

    Args:
        from_date: Start date of the range
        to_date: End date of the range

    Returns:
        'yearly' if range spans multiple months/years
        'monthly' if range spans multiple weeks within ~1-2 months
        'weekly' if range is a week or less
    """
    duration = (to_date - from_date).days

    # If the range spans more than 60 days, consider it yearly
    if duration >= 60:
        return 'yearly'
    # If the range spans more than 2 weeks but less than 60 days, consider it monthly
    elif duration >= 14:
        return 'monthly'
    # Otherwise, consider it weekly (no axis needed)
    else:
        return 'weekly'


def generate_axis_labels(from_date: date, to_date: date, range_type: str) -> str:
    """Generate axis labels for the sparkline.

    Args:
        from_date: Start date of the range
        to_date: End date of the range
        range_type: Type of range ('yearly', 'monthly', 'weekly')

    Returns:
        String with axis labels formatted appropriately for sparkline width
    """
    if range_type == 'weekly':
        return ''  # No axis for weekly ranges

    # First, calculate the actual workdays that will appear in the sparkline
    workdays = []
    current_date = from_date
    while current_date <= to_date:
        if current_date.weekday() < 5:  # weekdays only
            workdays.append(current_date)
        current_date += timedelta(days=1)

    if not workdays:
        return ''

    sparkline_width = len(workdays)  # Each workday = 1 character

    if range_type == 'yearly':
        # Generate month labels positioned at appropriate character positions
        month_positions = {}

        for i, day in enumerate(workdays):
            month_key = day.strftime('%b')
            if month_key not in month_positions:
                month_positions[month_key] = i

        # Create spacing for axis labels
        axis_chars = [' '] * sparkline_width

        # Place month labels at their first occurrence positions
        # But space them out so they don't overlap
        months_to_show = list(month_positions.keys())

        for month in months_to_show:
            pos = month_positions[month]
            # Only place if there's room (avoid overlapping with previous labels)
            if pos + 2 < sparkline_width:  # Need room for 3-char month abbreviation
                # Check if we have space (no other labels nearby)
                space_available = True
                for check_pos in range(max(0, pos - 2), min(sparkline_width, pos + 3)):
                    if axis_chars[check_pos] != ' ':
                        space_available = False
                        break

                if space_available:
                    # Add tickmark at the label position
                    axis_chars[pos] = '⎸'
                    # Place the month label only if there's room for the entire label
                    if pos + len(month) < sparkline_width:
                        for j, char in enumerate(month):
                            if pos + j + 1 < sparkline_width:
                                axis_chars[pos + j + 1] = char

        return ''.join(axis_chars)

    elif range_type == 'monthly':
        # Generate week labels at the start of each week
        axis_chars = [' '] * sparkline_width

        for i, day in enumerate(workdays):
            # Mark start of each week (Monday)
            if day.weekday() == 0:  # Monday
                # Get actual ISO week number
                week_num = day.isocalendar()[1]
                week_label = f'W{week_num}'
                # Add tickmark at the label position
                axis_chars[i] = '⎸'
                # Place week label only if there's room for the entire label
                if i + len(week_label) < sparkline_width:
                    for j, char in enumerate(week_label):
                        if i + j + 1 < sparkline_width:
                            axis_chars[i + j + 1] = char

        return ''.join(axis_chars)

    return ''
