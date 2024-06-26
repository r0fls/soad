from datetime import datetime, time, date
import re
import pytz
from decimal import Decimal


def extract_option_details(option_symbol):
    # Example pattern: AAPL230721C00250000 (AAPL, 2023-07-21, Call, 250.00)
    match = re.match(r'^([A-Z]+)(\d{2})(\d{2})(\d{2})([CP])(\d{8})$', option_symbol)
    if match:
        underlying = match.group(1)
        year = int(match.group(2))
        month = int(match.group(3))
        day = int(match.group(4))
        option_type = match.group(5)
        strike_price = Decimal(match.group(6)) / 1000
        return underlying, date(2000 + year, month, day), option_type, strike_price
    else:
        return None


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
