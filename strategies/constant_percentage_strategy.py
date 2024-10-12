import asyncio
from datetime import timedelta
from database.models import Balance
from utils.utils import is_market_open
from utils.logger import logger
from strategies.base_strategy import BaseStrategy
import asyncio
from sqlalchemy import select

class ConstantPercentageStrategy(BaseStrategy):
    def __init__(self, broker, strategy_name, stock_allocations, cash_percentage, rebalance_interval_minutes, starting_capital, buffer=0.1):
        self.stock_allocations = stock_allocations
        self.cash_percentage = cash_percentage
        self.rebalance_interval_minutes = rebalance_interval_minutes
        self.rebalance_interval = timedelta(minutes=rebalance_interval_minutes)
        self.buffer = buffer
        super().__init__(broker, strategy_name, starting_capital)
        logger.info(
            f"Initialized {self.strategy_name} strategy with starting capital {self.starting_capital}")

    async def initialize(self):
        await self.initialize_starting_balance()
        await self.sync_positions_with_broker()

    async def rebalance(self):
        logger.debug("Starting rebalance process")
        await self.sync_positions_with_broker()

        account_info = await self.get_account_info()
        cash_balance = account_info.get('cash_available')

        async with self.broker.Session() as session:
            # Using async session and query execution
            result = await session.execute(
                select(Balance).filter_by(
                    strategy=self.strategy_name,
                    broker=self.broker.broker_name,
                    type='cash'
                ).order_by(Balance.timestamp.desc())
            )
            balance = result.scalars().first()
            if balance is None:
                logger.error(
                    f"Strategy balance not initialized for {self.strategy_name} strategy on {self.broker.broker_name}.")
                raise ValueError(
                    f"Strategy balance not initialized for {self.strategy_name} strategy on {self.broker.broker_name}.")
            total_balance = balance.balance

            current_db_positions_dict = await self.fetch_current_db_positions()

        target_cash_balance, target_investment_balance = self.calculate_target_balances(total_balance, self.cash_percentage)

        current_positions = await self.current_positions()

        for stock, allocation in self.stock_allocations.items():
            target_balance = target_investment_balance * allocation
            current_position = 0
            for positions in current_positions:
                if position.symbol == stock:
                    current_position = position.quantity
            current_price = await self.broker.get_current_price(stock) if asyncio.iscoroutinefunction(self.broker.get_current_price) else self.broker.get_current_price(stock)
            target_quantity = target_balance // current_price
            # If we own less than the target quantity plus or minus the buffer, buy more
            if current_position < target_quantity * (1 - self.buffer):
                await self.place_order(stock, target_quantity - current_position, 'buy', current_price)
            # If we own more than the target quantity plus or minus the buffer, sell the excess
            elif current_position > target_quantity * (1 + self.buffer):
                await self.place_order(stock, current_position - target_quantity, 'sell', current_price)

        for stock, quantity in current_db_positions_dict.items():
            if stock not in self.stock_allocations:
                await self.place_order(stock, quantity, 'sell')

    async def should_own(self, symbol, current_price):
        pass
