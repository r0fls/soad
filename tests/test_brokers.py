import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime
from database.models import Trade, Position, Base
from database.db_manager import DBManager
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from brokers.base_broker import BaseBroker

class MockBroker(BaseBroker):
    async def connect(self):
        pass

    async def get_positions(self):
        return ['AAPL', 'GOOGL']

    async def get_current_price(self, symbol):
        return 150.0

    async def execute_trade(self, *args):
        pass

    async def _get_account_info(self):
        return {'profile': {'account': {'account_number': '12345', 'value': 10000.0}}}

    async def _place_option_order(self, symbol, quantity, order_type, price=None):
        return {'status': 'filled', 'filled_price': 150.0}

    async def _place_future_option_order(self, symbol, quantity, order_type, price=None):
        return {'status': 'filled', 'filled_price': 150.0}

    async def _place_order(self, symbol, quantity, order_type, price=None):
        return {'status': 'filled', 'filled_price': 150.0}

    async def _get_order_status(self, order_id):
        return {'status': 'completed'}

    async def _cancel_order(self, order_id):
        return {'status': 'cancelled'}

    async def _get_options_chain(self, symbol, expiration_date):
        return {'options': 'chain'}

class TestTrading(unittest.IsolatedAsyncioTestCase):
    @classmethod
    async def asyncSetUpClass(cls):
        pass

    @classmethod
    async def asyncTearDownClass(cls):
        pass

    async def asyncSetUp(self):
        # Create an in-memory SQLite database with async engine
        self.engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        self.Session = sessionmaker(bind=self.engine, class_=AsyncSession)
        self.db_manager = DBManager(self.engine)

        # Initialize the session and broker for each test
        self.session = self.Session()
        # Drop all tables in the teardown
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

        # Use async context to create tables
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        self.broker = MockBroker(api_key="dummy_api_key", secret_key="dummy_secret_key", broker_name="dummy_broker", engine=self.engine)

    async def asyncTearDown(self):
        await self.session.close()
        await self.engine.dispose()

    async def test_has_bought_today(self):
        async with self.session.begin():
            self.session.add(Trade(symbol="AAPL", quantity=10, price=150.0, executed_price=150.0, order_type="buy", timestamp=datetime.now(), status='filled', broker='dummy_broker'))
        await self.session.commit()

        result = await self.broker.has_bought_today("AAPL")
        self.assertTrue(result)

        await self.session.query(Trade).delete()
        await self.session.commit()

        result = await self.broker.has_bought_today("AAPL")
        self.assertFalse(result)

    async def test_update_positions_buy(self):
        trade = Trade(symbol="AAPL", quantity=10, price=150.0, executed_price=150.0, order_type="buy", timestamp=datetime.now(), status='filled', broker='dummy_broker')
        async with self.session.begin():
            self.session.add(trade)
        await self.session.commit()

        await self.broker.update_positions(self.session, trade)

        position = await self.session.get(Position, {"symbol": "AAPL"})
        self.assertIsNotNone(position)
        self.assertEqual(position.symbol, "AAPL")
        self.assertEqual(position.quantity, 10)
        self.assertEqual(position.latest_price, 150.0)
        self.assertEqual(position.cost_basis, 1500.0)

    async def test_update_positions_sell(self):
        position = Position(symbol="AAPL", broker="dummy_broker", quantity=10, latest_price=150.0, cost_basis=1500.0)
        async with self.session.begin():
            self.session.add(position)
        await self.session.commit()

        trade = Trade(symbol="AAPL", quantity=5, price=155.0, executed_price=155.0, order_type="sell", timestamp=datetime.now(), status='filled', broker='dummy_broker')
        async with self.session.begin():
            self.session.add(trade)
        await self.session.commit()

        await self.broker.update_positions(self.session, trade)

        position = await self.session.get(Position, {"symbol": "AAPL"})
        self.assertEqual(position.quantity, 5)
        self.assertEqual(position.latest_price, 155.0)
        self.assertAlmostEqual(position.cost_basis, 750.0)

    async def test_multiple_buys_update_cost_basis(self):
        trade1 = Trade(symbol="AAPL", quantity=10, price=150.0, executed_price=150.0, order_type="buy", timestamp=datetime.now(), status='filled', broker='dummy_broker')
        async with self.session.begin():
            self.session.add(trade1)
        await self.session.commit()

        await self.broker.update_positions(self.session, trade1)

        position = await self.session.get(Position, {"symbol": "AAPL"})
        self.assertEqual(position.symbol, "AAPL")
        self.assertEqual(position.quantity, 10)
        self.assertEqual(position.latest_price, 150.0)
        self.assertEqual(position.cost_basis, 1500.0)

        trade2 = Trade(symbol="AAPL", quantity=5, price=160.0, executed_price=160.0, order_type="buy", timestamp=datetime.now(), status='filled', broker='dummy_broker')
        async with self.session.begin():
            self.session.add(trade2)
        await self.session.commit()

        await self.broker.update_positions(self.session, trade2)

        position = await self.session.get(Position, {"symbol": "AAPL"})
        self.assertEqual(position.quantity, 15)
        self.assertEqual(position.latest_price, 160.0)
        self.assertAlmostEqual(position.cost_basis, 2300.0)

    async def test_full_sell_removes_position(self):
        trade1 = Trade(symbol="AAPL", quantity=10, price=150.0, executed_price=150.0, order_type="buy", timestamp=datetime.now(), status='filled', broker='dummy_broker')
        async with self.session.begin():
            self.session.add(trade1)
        await self.session.commit()

        await self.broker.update_positions(self.session, trade1)

        trade2 = Trade(symbol="AAPL", quantity=10, price=155.0, executed_price=155.0, order_type="sell", timestamp=datetime.now(), status='filled', broker='dummy_broker')
        async with self.session.begin():
            self.session.add(trade2)
        await self.session.commit()

        await self.broker.update_positions(self.session, trade2)

        position = await self.session.get(Position, {"symbol": "AAPL"})
        self.assertIsNone(position)

    async def test_edge_case_zero_quantity(self):
        trade = Trade(symbol="AAPL", quantity=0, price=150.0, executed_price=150.0, order_type="buy", timestamp=datetime.now(), status='filled', broker='dummy_broker')
        async with self.session.begin():
            self.session.add(trade)
        await self.session.commit()

        await self.broker.update_positions(self.session, trade)

        position = await self.session.get(Position, {"symbol": "AAPL"})
        self.assertIsNone(position)

    async def test_pl_calculation_buy_trade(self):
        trade = Trade(
            symbol="AAPL",
            quantity=10,
            price=150.0,
            executed_price=150.0,
            order_type="buy",
            status="executed",
            timestamp=datetime.now(),
            broker="dummy_broker",
            strategy="test_strategy",
            profit_loss=None,
            success="yes"
        )
        async with self.session.begin():
            self.session.add(trade)
        await self.session.commit()

        profit_loss = await self.db_manager.calculate_profit_loss(trade)
        self.assertIsNone(profit_loss)

    async def test_pl_calculation_option_full_sell_trade(self):
        position = Position(
            symbol="QQQ240726P00470000",
            broker="dummy_broker",
            quantity=10,
            latest_price=150.0,
            cost_basis=1500.0,
            last_updated=datetime.now(),
            strategy="test_strategy"
        )
        async with self.session.begin():
            self.session.add(position)
        await self.session.commit()

        trade = Trade(
            symbol="QQQ240726P00470000",
            quantity=10,
            price=155.0,
            executed_price=155.0,
            order_type="sell",
            status="executed",
            timestamp=datetime.now(),
            broker="dummy_broker",
            strategy="test_strategy",
            profit_loss=None,
            success="yes"
        )
        async with self.session.begin():
            self.session.add(trade)
        await self.session.commit()

        profit_loss = await self.db_manager.calculate_profit_loss(trade)
        self.assertEqual(profit_loss, 5000.0)

    async def test_pl_calculation_full_sell_trade(self):
        position = Position(
            symbol="AAPL",
            broker="dummy_broker",
            quantity=10,
            latest_price=150.0,
            cost_basis=1500.0,
            last_updated=datetime.now(),
            strategy="test_strategy"
        )
        async with self.session.begin():
            self.session.add(position)
        await self.session.commit()

        trade = Trade(
            symbol="AAPL",
            quantity=10,
            price=155.0,
            executed_price=155.0,
            order_type="sell",
            status="executed",
            timestamp=datetime.now(),
            broker="dummy_broker",
            strategy="test_strategy",
            profit_loss=None,
            success="yes"
        )
        async with self.session.begin():
            self.session.add(trade)
        await self.session.commit()

        profit_loss = await self.db_manager.calculate_profit_loss(trade)
        self.assertEqual(profit_loss, 50.0)

    async def test_pl_calculation_sell_trade(self):
        position = Position(
            symbol="AAPL",
            broker="dummy_broker",
            quantity=10,
            latest_price=150.0,
            cost_basis=1500.0,
            last_updated=datetime.now(),
            strategy="test_strategy"
        )
        async with self.session.begin():
            self.session.add(position)
        await self.session.commit()

        trade = Trade(
            symbol="AAPL",
            quantity=5,
            price=155.0,
            executed_price=155.0,
            order_type="sell",
            status="executed",
            timestamp=datetime.now(),
            broker="dummy_broker",
            strategy="test_strategy",
            profit_loss=None,
            success="yes"
        )
        async with self.session.begin():
            self.session.add(trade)
        await self.session.commit()

        profit_loss = await self.db_manager.calculate_profit_loss(trade)
        self.assertEqual(profit_loss, 25.0)

    async def test_pl_calculation_no_position(self):
        trade = Trade(
            symbol="AAPL",
            quantity=5,
            price=155.0,
            executed_price=155.0,
            order_type="sell",
            status="executed",
            timestamp=datetime.now(),
            broker="dummy_broker",
            strategy="test_strategy",
            profit_loss=None,
            success="yes"
        )
        async with self.session.begin():
            self.session.add(trade)
        await self.session.commit()

        profit_loss = await self.db_manager.calculate_profit_loss(trade)
        self.assertIsNone(profit_loss)

if __name__ == '__main__':
    unittest.main()
