from abc import ABC, abstractmethod

class BaseStrategy(ABC):
    def __init__(self, broker):
        self.broker = broker

    @abstractmethod
    def rebalance(self):
        pass
