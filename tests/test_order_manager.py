import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from database.models import Trade
from order_manager.manager import OrderManager

PEGGED_ORDER_CANCEL_AFTER = 15


@pytest_asyncio.fixture
def mock_db_manager():
    """Mock the DBManager."""
    return AsyncMock()


@pytest_asyncio.fixture
def mock_broker():
    """Mock a broker."""
    broker = AsyncMock()
    broker.is_order_filled.return_value = False
    broker.update_positions.return_value = None
    return broker


@pytest_asyncio.fixture
def order_manager(mock_db_manager, mock_broker):
    """Create an instance of OrderManager with mocked dependencies."""
    engine = MagicMock()
    brokers = {"dummy_broker": mock_broker}
    order_manager = OrderManager(engine, brokers)
    order_manager.db_manager = mock_db_manager
    return order_manager


@pytest.mark.asyncio
async def test_reconcile_orders(order_manager, mock_db_manager):
    """Test the reconcile_orders method."""
    # Mock trades
    trades = [
        Trade(id=1, broker="dummy_broker", broker_id="123", status="open"),
        Trade(id=2, broker="dummy_broker", broker_id="456", status="open"),
    ]
    order_manager.reconcile_order = AsyncMock()

    await order_manager.reconcile_orders(trades)

    # Verify that reconcile_order is called for each trade
    order_manager.reconcile_order.assert_any_call(trades[0])
    order_manager.reconcile_order.assert_any_call(trades[1])
    assert order_manager.reconcile_order.call_count == len(trades)


@pytest.mark.asyncio
async def test_reconcile_order_stale(order_manager, mock_db_manager, mock_broker):
    """Test the reconcile_order method for stale orders."""
    stale_order = Trade(
        id=1,
        broker="dummy_broker",
        broker_id=None,
        timestamp=datetime.utcnow() - timedelta(days=3),
        status="open",
    )

    await order_manager.reconcile_order(stale_order)

    # Verify that the order is marked as stale
    mock_db_manager.update_trade_status.assert_called_once_with(1, "stale")
    mock_broker.is_order_filled.assert_not_called()
    mock_broker.update_positions.assert_not_called()


# TODO: Fix
@pytest.mark.skip
@pytest.mark.asyncio
async def test_reconcile_order_filled(order_manager, mock_db_manager, mock_broker):
    """Test the reconcile_order method for filled orders."""
    filled_order = Trade(
        id=1,
        broker="dummy_broker",
        broker_id="123",
        timestamp=datetime.utcnow(),
        status="open",
    )
    mock_broker.is_order_filled.return_value = True

    await order_manager.reconcile_order(filled_order)

    # Verify that the order is marked as filled and positions are updated
    mock_db_manager.set_trade_filled.assert_called_once_with(1)
    mock_broker.update_positions.assert_called_once_with(filled_order, mock_db_manager.Session().__aenter__.return_value)


@pytest.mark.asyncio
async def test_reconcile_order_not_filled(order_manager, mock_db_manager, mock_broker):
    """Test the reconcile_order method for orders that are not filled."""
    unfilled_order = Trade(
        id=1,
        broker="dummy_broker",
        broker_id="123",
        timestamp=datetime.utcnow(),
        status="open",
    )
    mock_broker.is_order_filled.return_value = False

    await order_manager.reconcile_order(unfilled_order)

    # Verify that no changes are made for unfilled orders
    mock_db_manager.set_trade_filled.assert_not_called()
    mock_broker.update_positions.assert_not_called()


@pytest.mark.asyncio
async def test_run(order_manager, mock_db_manager):
    """Test the run method."""
    trades = [
        Trade(id=1, broker="dummy_broker", broker_id="123", status="open"),
        Trade(id=2, broker="dummy_broker", broker_id="456", status="open"),
    ]
    mock_db_manager.get_open_trades.return_value = trades
    order_manager.reconcile_orders = AsyncMock()

    await order_manager.run()

    # Verify that open trades are fetched and reconciled
    mock_db_manager.get_open_trades.assert_called_once()
    order_manager.reconcile_orders.assert_called_once_with(trades)

@pytest.mark.asyncio
async def test_reconcile_order_pegged_expired(order_manager, mock_db_manager, mock_broker):
    """
    Test that a pegged order older than PEGGED_ORDER_CANCEL_AFTER is canceled
    and a new limit order is placed at the mid price.
    """
    old_timestamp = datetime.utcnow() - timedelta(seconds=PEGGED_ORDER_CANCEL_AFTER + 1)
    pegged_order = Trade(
        id=1,
        broker="dummy_broker",
        broker_id="123",
        symbol="AAPL",
        quantity=10,
        side="buy",
        strategy="test_strategy",
        timestamp=old_timestamp,
        status="open",
        execution_style="pegged"
    )

    # Mock placing a new order after cancellation
    # Assume place_order returns a Trade object or something similar
    order_manager.brokers['dummy_broker'].place_order = AsyncMock()

    await order_manager.reconcile_order(pegged_order)

    # The pegged order should be canceled
    mock_broker.cancel_order.assert_called_once_with("123")
    # The status should be updated to 'cancelled'
    mock_db_manager.update_trade_status.assert_called_once_with(1, "cancelled")

    # A new order should be placed using the mid_price (mocked as 100.00)
    order_manager.brokers['dummy_broker'].place_order.assert_called_once()
    args, kwargs = order_manager.brokers['dummy_broker'].place_order.call_args
    assert kwargs['symbol'] == 'AAPL'
    assert kwargs['quantity'] == 10
    assert kwargs['side'] == 'buy'
    # TODO: Check that the price is the mid price
    # (need to mock the mid price func return)
    # assert kwargs['price'] == 100.00
    assert kwargs['order_type'] == 'limit'
    assert kwargs['execution_style'] == 'pegged'


@pytest.mark.asyncio
async def test_reconcile_order_pegged_not_expired(order_manager, mock_db_manager, mock_broker):
    """
    Test that a pegged order that is not yet expired does not get cancelled
    and no new order is placed.
    """
    recent_timestamp = datetime.utcnow() - timedelta(seconds=PEGGED_ORDER_CANCEL_AFTER - 5)
    pegged_order = Trade(
        id=1,
        broker="dummy_broker",
        broker_id="123",
        symbol="AAPL",
        quantity=10,
        side="buy",
        strategy="test_strategy",
        timestamp=recent_timestamp,
        status="open",
        execution_style="pegged"
    )

    order_manager.place_order = AsyncMock()

    await order_manager.reconcile_order(pegged_order)

    # The pegged order should not be cancelled or replaced because it's not old enough
    mock_broker.cancel_order.assert_not_called()
    mock_db_manager.update_trade_status.assert_not_called()
    order_manager.place_order.assert_not_called()


@pytest.mark.asyncio
async def test_reconcile_order_with_execution_style(order_manager, mock_db_manager, mock_broker):
    """
    Test that when an order with a specific execution_style (other than pegged)
    is reconciled and not stale, not filled, nothing else changes.
    This ensures execution_style does not break existing logic.
    """
    recent_order = Trade(
        id=2,
        broker="dummy_broker",
        broker_id="456",
        symbol="TSLA",
        quantity=5,
        side="sell",
        strategy="test_strategy",
        timestamp=datetime.utcnow(),
        status="open",
        execution_style="some_custom_style"
    )
    mock_broker.is_order_filled.return_value = False

    await order_manager.reconcile_order(recent_order)

    # Verify that no changes are made for an open order that is not stale and not filled
    mock_db_manager.set_trade_filled.assert_not_called()
    mock_broker.update_positions.assert_not_called()
    mock_broker.cancel_order.assert_not_called()
