import unittest
from unittest.mock import MagicMock
from datetime import datetime, timezone
from database.models import Trade, Balance, Position, Base
from database.db_manager import DBManager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from brokers.base_broker import BaseBroker

class MockBroker(BaseBroker):
    def connect(self):
        pass

    def get_positions(self):
        pass

    def _get_account_info(self):
        return {'profile': {'account': {'account_number': '12345', 'value': 10000.0}}}

    def _place_option_order(self, symbol, quantity, order_type, price=None):
        return {'status': 'filled', 'filled_price': 150.0}

    def _place_order(self, symbol, quantity, order_type, price=None):
        return {'status': 'filled', 'filled_price': 150.0}

    def _get_order_status(self, order_id):
        return {'status': 'completed'}

    def _cancel_order(self, order_id):
        return {'status': 'cancelled'}

    def _get_options_chain(self, symbol, expiration_date):
        return {'options': 'chain'}

    def get_current_price(self, symbol):
        return 150.0

    def execute_trade(self, *args):
        pass

class TestTrading(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create an in-memory SQLite database
        cls.engine = create_engine('sqlite:///:memory:')
        cls.Session = sessionmaker(bind=cls.engine)
        cls.db_manager = DBManager(cls.engine)

    def setUp(self):
        Base.metadata.drop_all(self.engine)
        Base.metadata.create_all(self.engine)
        self.session = self.Session()
        self.broker = MockBroker(api_key="dummy_api_key", secret_key="dummy_secret_key", broker_name="dummy_broker", engine=self.engine, prevent_day_trading=True)

    def tearDown(self):
        self.session.close()

    def test_has_bought_today(self):
        today = datetime.now().date()
        self.session.add(Trade(symbol="AAPL", quantity=10, price=150.0, executed_price=150.0, order_type="buy", timestamp=datetime.now(), status='filled', broker='dummy_broker'))
        self.session.commit()

        result = self.broker.has_bought_today("AAPL")
        self.assertTrue(result)

        self.session.query(Trade).delete()
        self.session.commit()

        result = self.broker.has_bought_today("AAPL")
        self.assertFalse(result)

    def test_update_positions_buy(self):
        trade = Trade(symbol="AAPL", quantity=10, price=150.0, executed_price=150.0, order_type="buy", timestamp=datetime.now(), status='filled', broker='dummy_broker')
        self.session.add(trade)
        self.session.commit()

        self.broker.update_positions(self.session, trade)

        position = self.session.query(Position).filter_by(symbol="AAPL").first()
        self.assertIsNotNone(position)
        self.assertEqual(position.symbol, "AAPL")
        self.assertEqual(position.quantity, 10)
        self.assertEqual(position.latest_price, 150.0)
        self.assertEqual(position.cost_basis, 1500.0)

    def test_update_positions_sell(self):
        position = Position(symbol="AAPL", broker="dummy_broker", quantity=10, latest_price=150.0, cost_basis=1500.0)
        self.session.add(position)
        self.session.commit()

        trade = Trade(symbol="AAPL", quantity=5, price=155.0, executed_price=155.0, order_type="sell", timestamp=datetime.now(), status='filled', broker='dummy_broker')
        self.session.add(trade)
        self.session.commit()

        self.broker.update_positions(self.session, trade)

        position = self.session.query(Position).filter_by(symbol="AAPL").first()
        self.assertEqual(position.quantity, 5)
        self.assertEqual(position.latest_price, 155.0)
        self.assertAlmostEqual(position.cost_basis, 750.0)  # Half of the original cost basis

    def test_multiple_buys_update_cost_basis(self):
        # First Buy Trade
        trade1 = Trade(symbol="AAPL", quantity=10, price=150.0, executed_price=150.0, order_type="buy", timestamp=datetime.now(), status='filled', broker='dummy_broker')
        self.session.add(trade1)
        self.session.commit()

        self.broker.update_positions(self.session, trade1)

        position = self.session.query(Position).filter_by(symbol="AAPL").first()
        self.assertEqual(position.symbol, "AAPL")
        self.assertEqual(position.quantity, 10)
        self.assertEqual(position.latest_price, 150.0)
        self.assertEqual(position.cost_basis, 1500.0)

        trade2 = Trade(symbol="AAPL", quantity=5, price=160.0, executed_price=160.0, order_type="buy", timestamp=datetime.now(), status='filled', broker='dummy_broker')
        self.session.add(trade2)
        self.session.commit()

        self.broker.update_positions(self.session, trade2)

        position = self.session.query(Position).filter_by(symbol="AAPL").first()
        self.assertEqual(position.quantity, 15)
        self.assertEqual(position.latest_price, 160.0)
        self.assertAlmostEqual(position.cost_basis, 2300.0)  # 1500 + 5*160

    def test_full_sell_removes_position(self):
        # First Buy Trade
        trade1 = Trade(symbol="AAPL", quantity=10, price=150.0, executed_price=150.0, order_type="buy", timestamp=datetime.now(), status='filled', broker='dummy_broker')
        self.session.add(trade1)
        self.session.commit()

        self.broker.update_positions(self.session, trade1)

        # Full Sell Trade
        trade2 = Trade(symbol="AAPL", quantity=10, price=155.0, executed_price=155.0, order_type="sell", timestamp=datetime.now(), status='filled', broker='dummy_broker')
        self.session.add(trade2)
        self.session.commit()

        self.broker.update_positions(self.session, trade2)

        position = self.session.query(Position).filter_by(symbol="AAPL").first()
        self.assertEqual(position, None)

    def test_edge_case_zero_quantity(self):
        trade = Trade(symbol="AAPL", quantity=0, price=150.0, executed_price=150.0, order_type="buy", timestamp=datetime.now(), status='filled', broker='dummy_broker')
        self.session.add(trade)
        self.session.commit()

        self.broker.update_positions(self.session, trade)

        position = self.session.query(Position).filter_by(symbol="AAPL").first()
        self.assertIsNone(position)  # No position should be created

    def test_pl_calculation_buy_trade(self):
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
        self.session.add(trade)
        self.session.commit()

        profit_loss = self.db_manager.calculate_profit_loss(trade)
        self.assertIsNone(profit_loss, "Profit/Loss for a buy trade should be None")

    def test_pl_calculation_sell_trade(self):
        position = Position(
            symbol="AAPL",
            broker="dummy_broker",
            quantity=10,
            latest_price=150.0,
            cost_basis=1500.0,
            last_updated=datetime.now(),
            strategy="test_strategy"
        )
        self.session.add(position)
        self.session.commit()

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
        self.session.add(trade)
        self.session.commit()

        profit_loss = self.db_manager.calculate_profit_loss(trade)
        self.assertEqual(profit_loss, 25.0, "Profit/Loss calculation for sell trade is incorrect")

    def test_pl_calculation_no_position(self):
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
        self.session.add(trade)
        self.session.commit()

        profit_loss = self.db_manager.calculate_profit_loss(trade)
        self.assertIsNone(profit_loss, "Profit/Loss calculation should return None when no position exists")

class TestBaseBroker(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create an in-memory SQLite database
        cls.engine = create_engine('sqlite:///:memory:')
        cls.Session = sessionmaker(bind=cls.engine)
        cls.db_manager = DBManager(cls.engine)

    def setUp(self):
        self.broker = MockBroker(api_key="dummy_api_key", secret_key="dummy_secret_key", broker_name="dummy_broker", engine=self.engine, prevent_day_trading=True)
        self.broker.get_positions = MagicMock(return_value=['AAPL', 'GOOGL'])

    def test_position_exists(self):
        self.assertTrue(self.broker.position_exists('AAPL'))
        self.assertFalse(self.broker.position_exists('TSLA'))

if __name__ == '__main__':
    unittest.main()
