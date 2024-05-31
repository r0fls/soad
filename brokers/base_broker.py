from abc import ABC, abstractmethod
from sqlalchemy.orm import sessionmaker
from database.db_manager import DBManager
from database.models import Trade, AccountInfo, Balance
from datetime import datetime

class BaseBroker(ABC):
    def __init__(self, api_key, secret_key, brokerage_name, engine):
        self.api_key = api_key
        self.secret_key = secret_key
        self.brokerage_name = brokerage_name
        self.db_manager = DBManager(engine)
        self.Session = sessionmaker(bind=engine)
        self.account_id = None

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

    @abstractmethod
    def get_current_price(self, symbol):
        pass

    def get_account_info(self):
        account_info = self._get_account_info()
        self.db_manager.add_account_info(AccountInfo(broker=self.brokerage_name, value=account_info['value']))
        return account_info

    def place_order(self, symbol, quantity, order_type, strategy, price=None):
        order_info = self._place_order(symbol, quantity, order_type, price)
        with self.Session() as session:
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
            session.add(trade)
            session.commit()
            self.update_trade(session, trade.id, order_info)
        return order_info

    def get_order_status(self, order_id):
        order_status = self._get_order_status(order_id)
        with self.Session() as session:
            trade = session.query(Trade).filter_by(id=order_id).first()
            if trade:
                self.update_trade(session, trade.id, order_status)
        return order_status

    def cancel_order(self, order_id):
        cancel_status = self._cancel_order(order_id)
        with self.Session() as session:
            trade = session.query(Trade).filter_by(id=order_id).first()
            if trade:
                self.update_trade(session, trade.id, cancel_status)
        return cancel_status

    def get_options_chain(self, symbol, expiration_date):
        return self._get_options_chain(symbol, expiration_date)

    def update_trade(self, session, trade_id, order_info):
        trade = session.query(Trade).filter_by(id=trade_id).first()
        if not trade:
            return

        executed_price = order_info.get('filled_price', trade.price)  # Match the correct key
        if executed_price is None:
            executed_price = trade.price  # Ensure we have a valid executed price

        trade.executed_price = executed_price
        profit_loss = self.db_manager.calculate_profit_loss(trade)
        success = "success" if profit_loss > 0 else "failure"

        trade.executed_price = executed_price
        trade.success = success
        trade.profit_loss = profit_loss
        session.commit()
