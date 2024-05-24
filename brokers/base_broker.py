from abc import ABC, abstractmethod
from database.db_manager import DBManager
from database.models import Trade, AccountInfo
from datetime import datetime

class BaseBroker(ABC):
    def __init__(self, api_key, secret_key, brokerage_name):
        self.api_key = api_key
        self.secret_key = secret_key
        self.brokerage_name = brokerage_name
        self.db_manager = DBManager()

    @abstractmethod
    def connect(self):
        pass

    @abstractmethod
    def _get_account_info(self):
        pass

    @abstractmethod
    def _place_order(self, symbol, quantity, order_type, price=None):
        pass

    @abstractmethod
    def _get_order_status(self, order_id):
        pass

    @abstractmethod
    def _cancel_order(self, order_id):
        pass

    @abstractmethod
    def _get_options_chain(self, symbol, expiration_date):
        pass

    def get_account_info(self):
        account_info = self._get_account_info()
        self.db_manager.add_account_info(AccountInfo(data=account_info))
        return account_info

    def place_order(self, symbol, quantity, order_type, strategy, price=None):
        order_info = self._place_order(symbol, quantity, order_type, price)
        trade = Trade(
            symbol=symbol,
            quantity=quantity,
            price=price,
            order_type=order_type,
            status=order_info.get('status', 'unknown'),
            timestamp=datetime.now(),
            brokerage=self.brokerage_name,
            strategy=strategy,
            success=None,
            profit_loss=None,
            executed_price=None  # Set initially to None
        )
        self.db_manager.add_trade(trade)
        self.update_trade(trade.id, order_info)
        return order_info

    def get_order_status(self, order_id):
        order_status = self._get_order_status(order_id)
        trade = self.db_manager.get_trade(order_id)
        if trade:
            self.update_trade(trade.id, order_status)
        return order_status

    def cancel_order(self, order_id):
        cancel_status = self._cancel_order(order_id)
        trade = self.db_manager.get_trade(order_id)
        if trade:
            self.update_trade(trade.id, cancel_status)
        return cancel_status

    def get_options_chain(self, symbol, expiration_date):
        return self._get_options_chain(symbol, expiration_date)

    def update_trade(self, trade_id, order_info):
        session = self.db_manager.Session()  # Ensure session is active
        trade = session.query(Trade).filter_by(id=trade_id).first()
        if not trade:
            session.close()
            return

        executed_price = order_info.get('executed_price', trade.price)  # Fallback to order price if executed_price not available
        profit_loss = self.db_manager.calculate_profit_loss(trade)
        success = "success" if profit_loss > 0 else "failure"

        trade.executed_price = executed_price
        trade.success = success
        trade.profit_loss = profit_loss
        session.commit()
        session.close()

    @abstractmethod
    def get_current_price(self, symbol):
        pass
