from datetime import datetime, time, date
import re
import pytz
from decimal import Decimal
import math

OPTION_MULTIPLIER = 100

def is_ticker(symbol):
    '''
    Check if the input symbol is a valid stock ticker.
    '''
    pattern = re.compile(r'^[A-Z]{1,5}(\.[A-Z]{1,2})?$')
    return pattern.match(symbol)

def is_option(symbol):
    '''
    Check if the input symbol is a valid option symbol.
    '''
    pattern = re.compile(r'^[A-Z]{1,5}\d{6}[CP]\d{8}$')
    return pattern.match(symbol)

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

def black_scholes_delta_theta(position):
    """
    Calculate Black-Scholes delta and theta for an option based on a Position object.
    """
    option_fields = extract_option_details(position.symbol)
    if not option_fields:
        return None, None  # Unable to parse option symbol

    S = float(position.latest_price)
    underlying, expiration_date, option_type, K = option_fields
    T = (expiration_date - datetime.now().date()).days / 365.0
    r = 0.04
    sigma = float(position.underlying_volatility)

    d1 = (math.log(S / float(K)) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)

    delta = 0
    theta = 0
    if option_type == 'call':
        delta = norm.cdf(d1)
        theta = (-S * norm.pdf(d1) * sigma / (2 * math.sqrt(T)) - r * K * math.exp(-r * T) * norm.cdf(d2)) / 365
    elif option_type == 'put':
        delta = -norm.cdf(-d1)
        theta = (-S * norm.pdf(d1) * sigma / (2 * math.sqrt(T)) + r * K * math.exp(-r * T) * norm.cdf(-d2)) / 365

    return delta, theta
