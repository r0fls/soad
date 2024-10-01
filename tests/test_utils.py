import pytest
from unittest.mock import patch
from utils.utils import futures_contract_size, is_futures_market_open, is_futures_symbol
from freezegun import freeze_time

# Test Futures Contract Size
def test_is_futures_symbol():
    # Test cases for valid futures option symbols
    assert is_futures_symbol('./ESU4') is True
    assert is_futures_symbol('./MNQU4D4DN4 240725P19300') is True
    assert is_futures_symbol('./CLU4 240725P19300') is True
    # Test cases for invalid futures option symbols
    assert is_futures_symbol('AAPL') is False
    # TODO: fix
    #assert is_futures_symbol('./INVALID SYMBOL') is False
    assert is_futures_symbol('ESU4') is False


def test_known_symbols():
    assert futures_contract_size('./ESU4') == 50
    assert futures_contract_size('./NQU4') == 20
    assert futures_contract_size('./MESU4') == 5
    assert futures_contract_size('./MNQU4') == 2
    assert futures_contract_size('./RTYU4') == 50
    assert futures_contract_size('./M2KU4') == 10
    assert futures_contract_size('./YMU4') == 5
    assert futures_contract_size('./MYMU4') == 2
    assert futures_contract_size('./ZBU4') == 1000
    assert futures_contract_size('./ZNU4') == 1000
    assert futures_contract_size('./ZTU4') == 2000
    assert futures_contract_size('./ZFU4') == 1000
    assert futures_contract_size('./ZCU4') == 50
    assert futures_contract_size('./ZSU4') == 50
    assert futures_contract_size('./ZWU4') == 50
    assert futures_contract_size('./ZLU4') == 50
    assert futures_contract_size('./ZMU4') == 50
    assert futures_contract_size('./ZRU4') == 50
    assert futures_contract_size('./ZKU4') == 50
    assert futures_contract_size('./ZOU4') == 50
    assert futures_contract_size('./ZVU4') == 1000
    assert futures_contract_size('./HEU4') == 40000
    assert futures_contract_size('./LEU4') == 40000
    assert futures_contract_size('./CLU4') == 1000
    assert futures_contract_size('./GCU4') == 100
    assert futures_contract_size('./SIU4') == 5000
    assert futures_contract_size('./6EU4') == 125000

@patch('utils.utils.logger')
def test_unknown_symbol(mock_logger):
    assert futures_contract_size('./XYZU4') == 1
    mock_logger.error.assert_called_once_with("Unknown future symbol: ./XYZU4")


# Test Futures Market Open
@freeze_time("2024-07-22 13:00:00")  # A Monday at 1:00 PM Eastern Time
def test_futures_market_open():
    assert is_futures_market_open() is True

@freeze_time("2024-07-22 18:00:00")  # A Monday at 6:00 PM Eastern Time
def test_futures_market_open_evening():
    assert is_futures_market_open() is True

@freeze_time("2024-07-20 13:00:00")  # A Saturday at 1:00 PM Eastern Time
def test_futures_market_closed_saturday():
    assert is_futures_market_open() is False

@freeze_time("2024-07-21 17:00:00")  # A Sunday at 5:00 PM Eastern Time
def test_futures_market_closed_sunday_before_open():
    assert is_futures_market_open() is False

# TODO: fix
@pytest.mark.skip(reason="Test needs to be fixed")
@freeze_time("2024-07-21 18:30:00")  # A Sunday at 6:30 PM Eastern Time
def test_futures_market_open_sunday_evening():
    assert is_futures_market_open() is True

@pytest.mark.skip(reason="Test needs to be fixed")
@freeze_time("2024-07-23 17:30:00")  # A Tuesday at 5:30 PM Eastern Time
def test_futures_market_closed_weekday_after_close():
    assert is_futures_market_open() is False

@freeze_time("2024-07-23 16:30:00")  # A Tuesday at 4:30 PM Eastern Time
def test_futures_market_open_weekday_afternoon():
    assert is_futures_market_open() is True
