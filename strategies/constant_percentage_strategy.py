from datetime import datetime
from utils.utils import is_market_open
from utils.logger import logger
from database.models import Balance, Position
from strategies.base_strategy import BaseStrategy
import asyncio
from datetime import timedelta


class ConstantPercentageStrategy(BaseStrategy):
    def __init__(self, broker, stock_allocations, cash_percentage, rebalance_interval_minutes, starting_capital):
        self.stock_allocations = stock_allocations
        self.rebalance_interval_minutes = rebalance_interval_minutes
        self.cash_percentage = cash_percentage
        self.rebalance_interval = timedelta(minutes=rebalance_interval_minutes)
        self.starting_capital = starting_capital
        self.strategy_name = 'constant_percentage'
        super().__init__(broker)
        logger.info(
            f"Initialized {self.strategy_name} strategy with starting capital {self.starting_capital}")

    async def initialize(self):
        # Ensure positions are synced on initialization
        await self.sync_positions_with_broker()

    async def rebalance(self):
        logger.debug("Starting rebalance process")
        # Ensure positions are synced before rebalancing
        await self.sync_positions_with_broker()

        account_info = self.broker.get_account_info()
        cash_balance = account_info.get('cash_available')
        logger.debug(f"Account info: {account_info}")

        with self.broker.Session() as session:
            balance = session.query(Balance).filter_by(
                strategy=self.strategy_name,
                broker=self.broker.broker_name,
                type='cash'
            ).first()
            if balance is None:
                logger.error(
                    f"Strategy balance not initialized for {self.strategy_name} strategy on {self.broker.broker_name}.")
                raise ValueError(
                    f"Strategy balance not initialized for {self.strategy_name} strategy on {self.broker.broker_name}.")
            total_balance = balance.balance
            logger.debug(f"Total balance retrieved: {total_balance}")

            # Query for current positions in the database
            current_db_positions = session.query(Position).filter_by(
                strategy=self.strategy_name,
                broker=self.broker.broker_name
            ).all()
            current_db_positions_dict = {
                pos.symbol: pos.quantity for pos in current_db_positions if pos.quantity > 0}
            logger.debug(f"Current DB positions: {current_db_positions_dict}")

        target_cash_balance = total_balance * self.cash_percentage
        target_investment_balance = total_balance - target_cash_balance
        logger.debug(
            f"Target cash balance: {target_cash_balance}, Target investment balance: {target_investment_balance}")

        current_positions = self.get_current_positions()
        logger.debug(f"Current positions: {current_positions}")

        for stock, allocation in self.stock_allocations.items():
            target_balance = target_investment_balance * allocation
            current_position = current_positions.get(stock, 0)
            # async price fetcher
            if self.broker.broker_name == 'tastytrade':
                current_price = await self.broker.get_current_price(stock)
            else:
                current_price = self.broker.get_current_price(stock)
            target_quantity = target_balance // current_price
            logger.debug(
                f"Stock: {stock}, Allocation: {allocation}, Target balance: {target_balance}, Current position: {current_position}, Current price: {current_price}, Target quantity: {target_quantity}")
            if current_position < target_quantity:
                if is_market_open():
                    if asyncio.iscoroutinefunction(self.broker.place_order):
                        await self.broker.place_order(stock, target_quantity - current_position, 'buy', self.strategy_name)
                    else:
                        self.broker.place_order(
                            stock, target_quantity - current_position, 'buy', self.strategy_name)
                    logger.info(
                        f"Placed buy order for {stock}: {target_quantity - current_position} shares")
                else:
                    logger.info(
                        f"Market is closed, not buying {stock}: {target_quantity - current_position} shares")
            elif current_position > target_quantity:
                if is_market_open():
                    if asyncio.iscoroutinefunction(self.broker.place_order):
                        await self.broker.place_order(stock, current_position - target_quantity, 'sell', self.strategy_name)
                    else:
                        self.broker.place_order(
                            stock, current_position - target_quantity, 'sell', self.strategy_name)
                    logger.info(
                        f"Placed sell order for {stock}: {current_position - target_quantity} shares")
                else:
                    logger.info(
                        f"Market is closed, not selling {stock}: {current_position - target_quantity} shares")

        # Sell positions that aren't part of the current intended stock allocation
        for stock, quantity in current_db_positions_dict.items():
            if stock not in self.stock_allocations:
                if is_market_open():
                    if asyncio.iscoroutinefunction(self.broker.place_order):
                        await self.broker.place_order(stock, quantity, 'sell', self.strategy_name)
                    else:
                        self.broker.place_order(
                            stock, quantity, 'sell', self.strategy_name)
                    logger.info(
                        f"Placed sell order for {stock}: {quantity} shares")
                else:
                    logger.info(
                        f"Market is closed, not selling {stock}: {quantity} shares")

    def get_current_positions(self):
        positions = self.broker.get_positions()
        positions_dict = {
            position: positions[position]['quantity'] for position in positions}
        logger.debug(f"Retrieved current positions: {positions_dict}")
        return positions_dict

    # TODO: can we abstract this method across strategies?

    async def sync_positions_with_broker(self):
        logger.debug("Syncing positions with broker")

        broker_positions = self.broker.get_positions()
        logger.debug(f"Broker positions: {broker_positions}")

        with self.broker.Session() as session:
            # Get the actual positions from the broker
            for symbol, data in broker_positions.items():
                if asyncio.iscoroutinefunction(self.broker.get_current_price):
                    current_price = await self.broker.get_current_price(symbol)
                else:
                    current_price = self.broker.get_current_price(symbol)
                target_quantity = self.should_own(symbol, current_price)
                if target_quantity > 0:
                    # We should own this, let's see if we know about it
                    position = session.query(Position).filter_by(
                        broker=self.broker.broker_name,
                        strategy=None,
                        symbol=symbol
                    ).first()
                    if not position:
                        position = session.query(Position).filter_by(
                            broker=self.broker.broker_name,
                            strategy=self.strategy_name,
                            symbol=symbol
                        ).first()
                    if position:
                        position.strategy = self.strategy_name
                        position.quantity = data['quantity']
                        position.latest_price = current_price
                        position.last_updated = datetime.utcnow()
                        logger.info(
                            f"Updated uncategorized position for {symbol} to strategy {self.strategy_name} with quantity {data['quantity']} and price {current_price}")
                    else:
                        # Create a new position
                        position = Position(
                            broker=self.broker.broker_name,
                            strategy=self.strategy_name,
                            symbol=symbol,
                            quantity=data['quantity'],
                            latest_price=current_price,
                            last_updated=datetime.utcnow()
                        )
                        session.add(position)
                        logger.info(
                            f"Created new position for {symbol} with quantity {data['quantity']} and price {current_price}")
            session.commit()
            logger.debug("Positions synced with broker")

    def should_own(self, symbol, current_price):
        """Determine the quantity of the given symbol that should be owned according to the strategy."""
        with self.broker.Session() as session:
            balance = session.query(Balance).filter_by(
                strategy=self.strategy_name,
                broker=self.broker.broker_name,
                type='cash'
            ).first()
        allocation = self.stock_allocations.get(symbol, 0)
        total_balance = balance.balance
        target_investment_balance = total_balance * (1 - self.cash_percentage)
        target_quantity = target_investment_balance * allocation / current_price
        return target_quantity
