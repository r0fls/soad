# soad/strategies/simple_strategy.py
from .base_strategy import BaseStrategy

class SimpleStrategy(BaseStrategy):
    def __init__(self, broker, buy_threshold, sell_threshold):
        super().__init__(broker, 'simple_strategy', 10000)  # Initial balance of 10000
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold

    async def should_buy(self, symbol, price):
        return price < self.buy_threshold

    async def should_sell(self, symbol, price):
        return price > self.sell_threshold

    async def rebalance(self):
        positions = await self.broker.get_positions()
        for symbol, position in positions.items():
            current_price = await self.broker.get_current_price(symbol)

            if await self.should_sell(symbol, current_price):
                await self.place_order(symbol, position['quantity'], 'sell', current_price)
            elif await self.should_buy(symbol, current_price):
                # Calculate how many shares to buy based on available cash
                cash = (await self.broker.get_account_info())['buying_power']
                quantity = int(cash / current_price)  # Simple calculation
                if quantity > 0:
                    await self.place_order(symbol, quantity, 'buy', current_price)
