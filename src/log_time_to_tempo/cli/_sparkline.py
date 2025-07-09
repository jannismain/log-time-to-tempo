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
