from datetime import datetime, time, date
import re
import pytz
from decimal import Decimal
import math
from scipy.stats import norm
from utils.logger import logger

OPTION_MULTIPLIER = 100

def futures_contract_size(symbol):
    # TODO: get these dynamically
    # Check if the symbol starts with a valid futures symbol
    if symbol.startswith('./ESU4'):
        return 50
    elif symbol.startswith('./NQU4'):
        return 20
    elif symbol.startswith('./MESU4'):
        return 5
    elif symbol.startswith('./MNQU4'):
        return 2
    elif symbol.startswith('./RTYU4'):
        return 50
    elif symbol.startswith('./M2KU4'):
        return 10
    elif symbol.startswith('./YMU4'):
        return 5
    elif symbol.startswith('./MYMU4'):
        return 2
    elif symbol.startswith('./ZBU4'):
        return 1000
    elif symbol.startswith('./ZNU4'):
        return 1000
    elif symbol.startswith('./ZTU4'):
        return 2000
    elif symbol.startswith('./ZFU4'):
        return 1000
    elif symbol.startswith('./ZCU4'):
        return 50
    elif symbol.startswith('./ZSU4'):
        return 50
    elif symbol.startswith('./ZWU4'):
        return 50
    elif symbol.startswith('./ZLU4'):
        return 50
    elif symbol.startswith('./ZMU4'):
        return 50
    elif symbol.startswith('./ZRU4'):
        return 50
    elif symbol.startswith('./ZKU4'):
        return 50
    elif symbol.startswith('./ZOU4'):
        return 50
    elif symbol.startswith('./ZVU4'):
        return 1000
    # Why not lol 🤷
    elif symbol.startswith('./HEU4'):  # Lean Hogs 🐖
        return 40000
    elif symbol.startswith('./LEU4'):  # Live Cattle 🐄
        return 40000
    elif symbol.startswith('./CLU4'):  # Crude Oil 🛢️
        return 1000
    elif symbol.startswith('./GCU4'):  # Gold
        return 100
    elif symbol.startswith('./SIU4'):  # Silver
        return 5000
    elif symbol.startswith('./6EU4'):  # Euro FX
        return 125000
    else:
        logger.error(f"Unknown future symbol: {symbol}")
        return 1

# TODO: review this
def is_futures_symbol(symbol):
    """
    Check if the input symbol is a valid futures option symbol.
    A valid futures option symbol starts with './' followed by letters and numbers,
    and can include spaces and additional alphanumeric characters.
    """
    pattern = r'^\./[A-Z0-9]+(\s+[A-Z0-9]+)*$'
    return bool(re.match(pattern, symbol))

def is_ticker(symbol):
    '''
    Check if the input symbol is a valid stock ticker.
    '''
    pattern = re.compile(r'^[A-Z]{1,5}(\.[A-Z]{1,2})?$')
    return bool(pattern.match(symbol))

def is_option(symbol):
    '''
    Check if the input symbol is a valid option symbol.
    '''
    pattern = re.compile(r'^[A-Z]{1,5}\d{6}[CP]\d{8}$')
    return bool(pattern.match(symbol))

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

# TODO: enhance/fix
def is_futures_market_open():
    # Futures market open and close times (6:00 PM to 5:00 PM Eastern Time, Sunday to Friday)
    market_open_time = time(18, 0)  # 6:00 PM
    market_close_time = time(17, 0)  # 5:00 PM

    # Get current time in Eastern Time
    eastern = pytz.timezone('US/Eastern')
    current_time = datetime.now(eastern)

    # Check if today is Saturday
    if current_time.weekday() == 5:  # 5 = Saturday
        return False

    # Check if today is Sunday
    if current_time.weekday() == 6:  # 6 = Sunday
        if current_time.time() < market_open_time:
            return False
        return True

    # For other days, check if the time is within the market open and close times
    if current_time.weekday() in [0, 1, 2, 3, 4]:  # Monday to Friday
        if current_time.time() < market_close_time:
            return True
        if current_time.time() >= market_open_time:
            return True
        return False

    return False

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
    try:
        option_fields = extract_option_details(position.symbol)
        if not option_fields:
            return 0, 0

        S = float(position.underlying_latest_price)
        underlying, expiration_date, option_type, K = option_fields
        T = (expiration_date - datetime.now().date()).days / 365.0
        r = 0.04
        sigma = float(position.underlying_volatility)

        d1 = (math.log(S / float(K)) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)

        print(f"S: {S}, K: {float(K)}, T: {T}, r: {r}, sigma: {sigma}, d1: {d1}, d2: {d2}")

        delta = 0.0
        theta = 0.0
        if option_type == 'C':
            delta = norm.cdf(d1)
            theta = (-S * norm.pdf(d1) * sigma / (2 * math.sqrt(T)) - r * float(K) * math.exp(-r * T) * norm.cdf(d2)) / 365.0
        elif option_type == 'P':
            delta = -norm.cdf(-d1)
            theta = (-S * norm.pdf(d1) * sigma / (2 * math.sqrt(T)) + r * float(K) * math.exp(-r * T) * norm.cdf(-d2)) / 365.0

        print(f"delta: {delta}, theta: {theta}")

        return delta, theta
    except Exception as e:
        logger.error(f"Error calculating Black-Scholes delta and theta: {e}")
        return 0, 0
