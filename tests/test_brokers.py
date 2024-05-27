import unittes
from datetime import datetime
from database.models import Trade, Balance
from base_test import BaseTes
from your_broker_module import BaseBroker  # Replace with the actual impor

class TestTrading(BaseTest):
    def setUp(self):
        super().setUp()  # Call the setup from BaseTes

        # Additional setup
        additional_fake_trades = [
            Trade(symbol='MSFT', quantity=8, price=200.0, executed_price=202.0, order_type='buy', status='executed', timestamp=datetime.utcnow(), brokerage='Tastytrade', strategy='RSI', profit_loss=16.0, success='yes'),
        ]
        self.session.add_all(additional_fake_trades)
        self.session.commit()

    def test_execute_trade(self):
        # Example trade data
        trade_data = {
            'symbol': 'AAPL',
            'quantity': 10,
            'price': 150.0,
            'executed_price': 151.0,
            'order_type': 'buy',
            'status': 'executed',
            'timestamp': datetime.utcnow(),
            'brokerage': 'E*TRADE',
            'strategy': 'SMA',
            'profit_loss': 10.0,
            'success': 'yes'
        }

        # Execute the trade
        broker = BaseBroker('api_key', 'secret_key', 'E*TRADE')
        broker.execute_trade(self.session, trade_data)

        # Verify the trade was inserted
        trade = self.session.query(Trade).filter_by(symbol='AAPL').first()
        self.assertIsNotNone(trade)

        # Verify the balance was updated
        balance = self.session.query(Balance).filter_by(brokerage='E*TRADE', strategy='SMA').first()
        self.assertIsNotNone(balance)
        self.assertEqual(balance.total_balance, 1510.0)

if __name__ == '__main__':
    unittest.main()
