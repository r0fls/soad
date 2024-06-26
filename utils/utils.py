from datetime import datetime, time
import re
import pytz

def extract_underlying_symbol(option_symbol):
    # Regex pattern to match the beginning of the symbol consisting of uppercase letters
    match = re.match(r'^([A-Z]+)', option_symbol)
    if match:
        return match.group(1)  # Return the matching part which is the underlying symbol
    else:
        return None  # Return None if no match is found

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
