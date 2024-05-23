from abc import ABC, abstractmethod
import threading
from queue import Queue
from database.db_manager import DBManager
from database.models import Trade, AccountInfo
from datetime import datetime

class BaseBroker(ABC):
    def __init__(self, api_key, secret_key, brokerage_name):
        self.api_key = api_key
        self.secret_key = secret_key
        self.brokerage_name = brokerage_name
        self.db_manager = DBManager()
        self.db_queue = Queue()
        self.db_thread = threading.Thread(target=self._process_db_queue)
        self.db_thread.daemon = True
        self.db_thread.start()

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
        self.track_account_info(account_info)
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
            strategy=strategy
        )
        self.track_trade(trade)
        return order_info

    def get_order_status(self, order_id):
        return self._get_order_status(order_id)

    def cancel_order(self, order_id):
        return self._cancel_order(order_id)

    def get_options_chain(self, symbol, expiration_date):
        return self._get_options_chain(symbol, expiration_date)

    def _process_db_queue(self):
        while True:
            func, args = self.db_queue.get()
            func(*args)
            self.db_queue.task_done()

    def track_trade(self, trade):
        self.db_queue.put((self.db_manager.add_trade, (trade,)))

    def track_account_info(self, account_info):
        self.db_queue.put((self.db_manager.add_account_info, (account_info,)))
