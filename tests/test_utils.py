import pytest
from unittest.mock import patch
from utils.utils import futures_contract_size, is_futures_market_open, is_futures_symbol
from freezegun import freeze_time
from unittest.mock import MagicMock, AsyncMock
import utils.config as config_module

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

@pytest.fixture
def mock_config():
    return {
        "database": {"url": "sqlite+aiosqlite:///test.db"},
        "brokers": {
            "tradier": {"api_key": "test_key"},
            "alpaca": {"api_key": "test_key", "secret_key": "test_secret"}
        },
        "strategies": {
            "test_strategy": {
                "type": "constant_percentage",
                "broker": "tradier",
                "stock_allocations": {"AAPL": 0.5},
                "cash_percentage": 0.5,
                "rebalance_interval_minutes": 60,
                "starting_capital": 10000
            }
        }
    }

@pytest.mark.asyncio
@patch("utils.config.create_async_engine", return_value=MagicMock())
def skip_test_initialize_brokers(mock_create_engine, mock_config):
    brokers = config_module.initialize_brokers(mock_config)

    # Assertions
    assert "tradier" in brokers
    assert "alpaca" in brokers
    mock_create_engine.assert_called_once_with(mock_config["database"]["url"])

@pytest.mark.asyncio
@patch("utils.config.load_strategy_class", return_value=MagicMock())
@patch("utils.config.logger")
async def test_load_custom_strategy_success(mock_logger, mock_load_strategy):
    mock_broker = MagicMock()
    strategy_config = {
        "file_path": "dummy_path.py",
        "class_name": "DummyStrategy",
        "starting_capital": 10000,
        "rebalance_interval_minutes": 30,
        "strategy_params": {"param1": "value1"}
    }

    strategy = config_module.load_custom_strategy(mock_broker, "test_strategy", strategy_config)

    # Assertions
    mock_load_strategy.assert_called_once_with("dummy_path.py", "DummyStrategy")
    mock_logger.info.assert_called()
    assert strategy is not None

@pytest.mark.asyncio
@patch("utils.config.load_strategy_class", side_effect=Exception("Load error"))
@patch("utils.config.logger")
async def test_load_custom_strategy_failure(mock_logger, mock_load_strategy):
    mock_broker = MagicMock()
    strategy_config = {
        "file_path": "dummy_path.py",
        "class_name": "DummyStrategy",
        "starting_capital": 10000,
        "rebalance_interval_minutes": 30
    }

    with pytest.raises(Exception, match="Load error"):
        config_module.load_custom_strategy(mock_broker, "test_strategy", strategy_config)

    mock_load_strategy.assert_called_once_with("dummy_path.py", "DummyStrategy")
    mock_logger.error.assert_called_once()

def skip_test_parse_config():
    mock_open = patch("builtins.open", new_callable=MagicMock).start()
    mock_open.return_value.__enter__.return_value.read.return_value = "database:\n  url: sqlite:///test.db\n"

    config = config_module.parse_config("dummy_config.yaml")

    # Assertions
    assert config["database"]["url"] == "sqlite:///test.db"

    mock_open.stop()

@pytest.mark.asyncio
@patch("utils.config.initialize_brokers", return_value={"tradier": MagicMock()})
@patch("utils.config.initialize_strategies", return_value=AsyncMock())
async def test_initialize_system_components(mock_initialize_strategies, mock_initialize_brokers, mock_config):
    brokers, strategies = await config_module.initialize_system_components(mock_config)

    # Assertions
    mock_initialize_brokers.assert_called_once_with(mock_config)
    mock_initialize_strategies.assert_called_once_with(mock_initialize_brokers.return_value, mock_config)
    assert "tradier" in brokers
    assert strategies is not None

@pytest.mark.asyncio
@patch("utils.config.create_async_engine", return_value=MagicMock())
@patch("utils.config.DBManager.rename_strategy", side_effect=Exception("Rename failed"))
@patch("utils.config.initialize_system_components", return_value=(AsyncMock(), AsyncMock()))
async def skip_test_initialize_brokers_and_strategies_with_rename_failure(mock_initialize_components, mock_rename_strategy, mock_create_engine, mock_config):
    mock_config["rename_strategies"] = [{"broker": "tradier", "old_strategy_name": "old", "new_strategy_name": "new"}]

    brokers, strategies = await config_module.initialize_brokers_and_strategies(mock_config)

    # Assertions
    mock_create_engine.assert_called_once()
    mock_rename_strategy.assert_called_once()
    mock_initialize_components.assert_called_once_with(mock_config)
    assert brokers is not None
    assert strategies is not None

@pytest.mark.asyncio
@patch("utils.config.create_async_engine", return_value=MagicMock())
async def test_create_database_engine(mock_create_engine, mock_config):
    engine = config_module.create_database_engine(mock_config)

    # Assertions
    mock_create_engine.assert_called_once_with(mock_config["database"]["url"])
    assert engine is not None

@pytest.mark.asyncio
@patch("utils.config.init_db", new_callable=AsyncMock)
@patch("utils.config.logger")
async def test_initialize_database(mock_logger, mock_init_db):
    mock_engine = MagicMock()

    await config_module.initialize_database(mock_engine)

    # Assertions
    mock_init_db.assert_called_once_with(mock_engine)
    mock_logger.info.assert_called_once()
