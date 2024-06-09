from abc import ABC, abstractmethod
from database.models import Balance
from utils.logger import logger  # Import the logger

class BaseStrategy(ABC):
    def __init__(self, broker):
        self.broker = broker
        self.initialize_starting_balance()

    @abstractmethod
    def rebalance(self):
        pass

    def initialize_starting_balance(self):
        logger.debug("Initializing starting balance")
        
        account_info = self.broker.get_account_info()
        buying_power = account_info.get('buying_power')
        logger.debug(f"Account info: {account_info}")

        if buying_power < self.starting_capital:
            logger.error(f"Not enough cash available. Required: {self.starting_capital}, Available: {buying_power}")
            raise ValueError("Not enough cash available to initialize the strategy with the desired starting capital.")

        with self.broker.Session() as session:
            strategy_balance = session.query(Balance).filter_by(
                strategy=self.strategy_name,
                broker=self.broker.broker_name,
                type='cash'
            ).first()

            if strategy_balance is None:
                strategy_balance = Balance(
                    strategy=self.strategy_name,
                    broker=self.broker.broker_name,
                    type='cash',
                    balance=self.starting_capital
                )
                session.add(strategy_balance)
                session.commit()
                logger.info(f"Initialized starting balance for {self.strategy_name} strategy with {self.starting_capital}")
            else:
                logger.info(f"Existing balance found for {self.strategy_name} strategy: {strategy_balance.balance}")
