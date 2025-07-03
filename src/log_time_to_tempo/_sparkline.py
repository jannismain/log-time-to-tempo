"""Sparkline utilities for visualizing time data."""

from datetime import date, timedelta
from typing import Dict, List, Optional

# ASCII characters for sparklines - fallback if sparklines package is not available
SPARKLINE_CHARS = ' ▁▂▃▄▅▆▇█'


def generate_sparkline_from_daily_data(
    daily_data: Dict[str, Dict[str, int]], 
    from_date: date, 
    to_date: date
) -> str:
    """Generate a sparkline from daily time data.
    
    Args:
        daily_data: Dictionary with date strings as keys (e.g., '15.12') and 
                   values containing 'timeSpentSeconds' 
        from_date: Start date for the sparkline
        to_date: End date for the sparkline
        
    Returns:
        String representation of the sparkline
    """
    try:
        # Try to use the sparklines package if available
        from sparklines import sparklines
        
        # Generate list of values for each day in the range
        daily_values = []
        current_date = from_date
        
        while current_date <= to_date:
            date_str = current_date.strftime('%d.%m')
            time_spent = daily_data.get(date_str, {}).get('timeSpentSeconds', 0)
            daily_values.append(time_spent)
            current_date += timedelta(days=1)
        
        if not daily_values or all(v == 0 for v in daily_values):
            return ''
        
        # Convert to hours for better visualization
        daily_hours = [v / 3600 for v in daily_values]
        
        # Generate sparkline
        return sparklines(daily_hours)[0]
        
    except ImportError:
        # Fallback to ASCII implementation if sparklines package is not available
        return _generate_ascii_sparkline(daily_data, from_date, to_date)


def _generate_ascii_sparkline(
    daily_data: Dict[str, Dict[str, int]], 
    from_date: date, 
    to_date: date
) -> str:
    """Generate ASCII sparkline fallback."""
    # Generate list of values for each day in the range
    daily_values = []
    current_date = from_date
    
    while current_date <= to_date:
        date_str = current_date.strftime('%d.%m')
        time_spent = daily_data.get(date_str, {}).get('timeSpentSeconds', 0)
        daily_values.append(time_spent)
        current_date += timedelta(days=1)
    
    if not daily_values or all(v == 0 for v in daily_values):
        return ''
    
    # Convert to hours for better visualization
    daily_hours = [v / 3600 for v in daily_values]
    
    # Normalize values to fit sparkline character range
    max_value = max(daily_hours)
    if max_value == 0:
        return ''
    
    # Map values to sparkline characters
    sparkline = []
    for value in daily_hours:
        if value == 0:
            sparkline.append(' ')
        else:
            # Map value to character index (0-8)
            char_index = min(int((value / max_value) * 8), 7)
            sparkline.append(SPARKLINE_CHARS[char_index + 1])
    
    return ''.join(sparkline)