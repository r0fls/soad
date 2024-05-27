import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.models import Base, Trade, AccountInfo, Balance
from datetime import datetime


class BaseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(cls.engine)
        cls.Session = sessionmaker(bind=cls.engine)

    def setUp(self):
        # Initialize the database
        Base.metadata.drop_all(self.engine)
        Base.metadata.create_all(self.engine)
        
        # Insert initial test data
        self.session = self.Session()
        now = datetime.utcnow()
        
        fake_trades = [
            Trade(symbol='AAPL', quantity=10, price=150.0, executed_price=151.0, order_type='buy', status='executed', timestamp=now, brokerage='E*TRADE', strategy='SMA', profit_loss=10.0, success='yes'),
            Trade(symbol='GOOG', quantity=5, price=1000.0, executed_price=995.0, order_type='sell', status='executed', timestamp=now, brokerage='Tradier', strategy='EMA', profit_loss=-25.0, success='no'),
        ]

        fake_balances = [
            Balance(brokerage='E*TRADE', strategy='SMA', initial_balance=1510.0, total_balance=1510.0),
            Balance(brokerage='Tradier', strategy='EMA', initial_balance=-4975.0, total_balance=-4975.0)
        ]

        fake_account_info = [
            AccountInfo(broker='E*TRADE', value=10000.0),
            AccountInfo(broker='Tradier', value=5000.0)
        ]

        self.session.add_all(fake_trades)
        self.session.add_all(fake_balances)
        self.session.add_all(fake_account_info)
        self.session.commit()

    def tearDown(self):
        self.session.close()
        Base.metadata.drop_all(self.engine)
