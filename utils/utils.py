from datetime import datetime, time
import pytz

def is_market_open():
    # Define market open and close times (e.g., 9:30 AM to 4:00 PM Eastern Time)
    market_open = time(9, 30)
    market_close = time(16, 0)

    # Get current time in Eastern Time
    eastern = pytz.timezone('US/Eastern')
    current_time = datetime.now(eastern).time()

    # Check if today is a weekend
    current_date = datetime.now(eastern).date()
    if current_date.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
        return False

    # Check if current time is within market hours
    if market_open <= current_time <= market_close:
        return True

    return False
