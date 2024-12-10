from abc import ABC, abstractmethod
from database.models import Balance, Position
from utils.logger import logger
from utils.utils import is_market_open, is_futures_symbol, is_futures_market_open
from datetime import datetime
import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from inspect import iscoroutine


class BaseStrategy(ABC):
    def __init__(self, broker, strategy_name, starting_capital, rebalance_interval_minutes=5, execution_style=''):
        self.broker = broker
        self.strategy_name = strategy_name
        self.starting_capital = starting_capital
        self.rebalance_interval_minutes = rebalance_interval_minutes
        self.initialized = False
        self.execution_style = execution_style

    @abstractmethod
    async def rebalance(self):
        pass

    async def initialize_starting_balance(self):
        if self.initialized:
            logger.debug("Starting balance already initialized",
                         extra={'strategy_name': self.strategy_name})
            return
        logger.debug("Initializing starting balance", extra={
                     'strategy_name': self.strategy_name})

        account_info = await self.broker.get_account_info()
        buying_power = account_info.get('buying_power')
        logger.debug(f"Account info: {account_info}", extra={
                     'strategy_name': self.strategy_name})

        if buying_power < self.starting_capital:
            logger.error(f"Not enough cash available. Required: {self.starting_capital}, Available: {buying_power}", extra={
                         'strategy_name': self.strategy_name})
            raise ValueError(
                "Not enough cash available to initialize the strategy with the desired starting capital.")

        async with self.broker.Session() as session:
            result = await session.execute(
                select(Balance).filter_by(
                    strategy=self.strategy_name,
                    broker=self.broker.broker_name,
                    type='cash'
                ).order_by(Balance.timestamp.desc())
            )
            strategy_balance = result.scalar()

            if strategy_balance is None:
                strategy_balance = Balance(
                    strategy=self.strategy_name,
                    broker=self.broker.broker_name,
                    type='cash',
                    balance=self.starting_capital
                )
                session.add(strategy_balance)
                await session.commit()
                logger.info(f"Initialized starting balance for {self.strategy_name} strategy with {self.starting_capital}", extra={
                            'strategy_name': self.strategy_name})
            else:
                logger.info(f"Existing balance found for {self.strategy_name} strategy: {strategy_balance.balance}", extra={
                            'strategy_name': self.strategy_name})
        self.initialized = True

    async def current_positions(self):
        async with self.broker.Session() as session:
            result = await session.execute(
                select(Position).filter_by(
                    strategy=self.strategy_name,
                    broker=self.broker.broker_name
                )
            )
            return result.scalars().all()  # Use scalars().all() for multiple rows

    async def current_balance(self):
        async with self.broker.Session() as session:
            result = await session.execute(
                select(Balance).filter_by(
                    strategy=self.strategy_name,
                    broker=self.broker.broker_name,
                    type='cash'
                ).order_by(Balance.timestamp.desc())
            )
            balance = result.scalar()  # Use scalar() to fetch the latest balance
            total_balance = balance.balance

            result_positions = await session.execute(
                select(Position).filter_by(
                    strategy=self.strategy_name,
                    broker=self.broker.broker_name
                )
            )
            positions = result_positions.scalars().all()

            for position in positions:
                total_balance += position.quantity * position.latest_price
            return total_balance

    async def cash(self):
        async with self.broker.Session() as session:
            result = await session.execute(
                select(Balance).filter_by(
                    strategy=self.strategy_name,
                    broker=self.broker.broker_name,
                    type='cash'
                ).order_by(Balance.timestamp.desc())
            )
            balance = result.scalar()
            return balance.balance

    async def investment_value(self):
        async with self.broker.Session() as session:
            result = await session.execute(
                select(Position).filter_by(
                    strategy=self.strategy_name,
                    broker=self.broker.broker_name
                )
            )
            positions = result.scalars().all()

            position_balance = 0
            for position in positions:
                position_balance += position.quantity * position.latest_price
            return position_balance

    async def sync_positions_with_broker(self):
        logger.debug("Syncing positions with broker", extra={
                     'strategy_name': self.strategy_name})

        broker_positions = self.broker.get_positions()  # Assuming this is synchronous
        logger.debug(f"Broker positions: {broker_positions}", extra={
                     'strategy_name': self.strategy_name})

        async with self.broker.Session() as session:
            for symbol, data in broker_positions.items():
                if is_futures_symbol(symbol):
                    logger.info(f"Skipping syncing positions for futures option {symbol}", extra={
                                'strategy_name': self.strategy_name})
                    continue

                current_price = self.broker.get_current_price(
                    symbol)  # Assuming this is synchronous
                target_quantity = await self.should_own(symbol, current_price)

                if target_quantity is not None and target_quantity > 0:
                    # We have a way of determining the target quantity for this strategy and symbol
                    # See if there are uncategorized positions for this symbol that we can update
                    result = await session.execute(
                        select(Position).filter_by(
                            broker=self.broker.broker_name,
                            strategy="uncategorized",
                            symbol=symbol
                        )
                    )
                    position = result.scalar()

                    if not position:
                        result = await session.execute(
                            select(Position).filter_by(
                                broker=self.broker.broker_name,
                                strategy=self.strategy_name,
                                symbol=symbol
                            )
                        )
                        position = result.scalar()

                    if position:
                        position.strategy = self.strategy_name
                        # Update the position with the minimum of the target quantity and the broker's quantity
                        # This is to handle the case where the broker has more shares than the strategy wants
                        position.quantity = min(
                            target_quantity, data['quantity'])
                        position.latest_price = current_price
                        position.last_updated = datetime.now()
                        logger.info(
                            f"Updated position for {symbol} with quantity {position.quantity} and price {current_price}",
                            extra={'strategy_name': self.strategy_name})
                    else:
                        position = Position(
                            broker=self.broker.broker_name,
                            strategy=self.strategy_name,
                            symbol=symbol,
                            quantity=min(target_quantity, data['quantity']),
                            latest_price=current_price,
                            last_updated=datetime.now()
                        )
                        session.add(position)
                        logger.info(
                            f"Created new position for {symbol} with quantity {data['quantity']} and price {current_price}",
                            extra={'strategy_name': self.strategy_name})
                    # Create uncategorized positions for the remaining quantity
                    if target_quantity < data['quantity']:
                        position = Position(
                            broker=self.broker.broker_name,
                            strategy="uncategorized",
                            symbol=symbol,
                            quantity=data['quantity'] - target_quantity,
                            latest_price=current_price,
                            last_updated=datetime.now()
                        )
                        session.add(position)
                        logger.info(
                            f"Created uncategorized position for {symbol} with quantity {data['quantity'] - target_quantity} and price {current_price}",
                            extra={'strategy_name': self.strategy_name})

            db_positions = await self.current_positions()
            logger.debug(f"DB positions: {db_positions}", extra={
                         'strategy_name': self.strategy_name})

            broker_symbols = set(broker_positions.keys())

            for position in db_positions:
                if position.symbol not in broker_symbols:
                    logger.info(f"Removing position for {position.symbol} as it's not in broker's positions", extra={
                                'strategy_name': self.strategy_name})
                    await session.delete(position)

            await session.commit()
            logger.debug("Positions synced with broker", extra={
                         'strategy_name': self.strategy_name})

    async def should_own(self, symbol, current_price):
        pass

    async def get_account_info(self):
        account_info = await self.broker.get_account_info()
        if not account_info:
            logger.error("Failed to fetch account information",
                         extra={'strategy_name': self.strategy_name})
            raise ValueError("Failed to fetch account information")
        logger.debug(f"Account info: {account_info}", extra={
                     'strategy_name': self.strategy_name})
        return account_info

    def calculate_target_balances(self, total_balance, cash_percentage):
        target_cash_balance = total_balance * cash_percentage
        target_investment_balance = total_balance - target_cash_balance
        logger.debug(
            f"Target cash balance: {target_cash_balance}, Target investment balance: {target_investment_balance}",
            extra={'strategy_name': self.strategy_name})
        return target_cash_balance, target_investment_balance

    async def fetch_current_db_positions(self):
        async with self.broker.Session() as session:
            result = await session.execute(
                select(Position).filter_by(
                    strategy=self.strategy_name,
                    broker=self.broker.broker_name
                )
            )
            current_db_positions = result.scalars().all()
        current_db_positions_dict = {
            pos.symbol: pos.quantity for pos in current_db_positions if pos.quantity > 0}
        logger.debug(f"Current DB positions: {current_db_positions_dict}", extra={
                     'strategy_name': self.strategy_name})
        return current_db_positions_dict

    async def place_future_option_order(self, symbol, quantity, side, price, wait_till_open=True, order_type='limit', execution_style=''):
        if execution_style == '':
            execution_style = self.execution_style
        if is_futures_market_open() or not wait_till_open:
            await self.broker.place_future_option_order(symbol, quantity, side, self.strategy_name, price, order_type, execution_style=execution_style)
            logger.info(f"Placed {side} order for {symbol}: {quantity} shares", extra={
                        'strategy_name': self.strategy_name, 'symbol': symbol, 'quantity': quantity, 'side': side, 'price': price, 'order_type': order_type})
        else:
            logger.info(f"Market is closed, not placing {side} order for {symbol}: {quantity} shares", extra={
                        'strategy_name': self.strategy_name, 'symbol': symbol, 'quantity': quantity, 'side': side, 'price': price, 'order_type': order_type})

    async def place_option_order(self, symbol, quantity, side, price, wait_till_open=True, order_type='limit', execution_style=''):
        if execution_style == '':
            execution_style = self.execution_style
        if is_market_open() or not wait_till_open:
            await self.broker.place_option_order(symbol, quantity, side, self.strategy_name, price, order_type, execution_style=execution_style)
            logger.info(f"Placed {side} order for {symbol}: {quantity} shares", extra={
                        'strategy_name': self.strategy_name, 'symbol': symbol, 'quantity': quantity, 'side': side, 'price': price, 'order_type': order_type})
        else:
            logger.info(f"Market is closed, not placing {side} order for {symbol}: {quantity} shares", extra={
                        'strategy_name': self.strategy_name, 'symbol': symbol, 'quantity': quantity, 'side': side, 'price': price, 'order_type': order_type})

    async def place_order(self, stock, quantity, side, price, wait_till_open=True, order_type='limit', execution_style=''):
        if execution_style == '':
            execution_style = self.execution_style
        if is_market_open() or not wait_till_open:
            await self.broker.place_order(stock, quantity, side, self.strategy_name, price, order_type, execution_style=execution_style)
            logger.info(f"Placed {side} order for {stock}: {quantity} shares", extra={
                        'strategy_name': self.strategy_name, 'stock': stock, 'quantity': quantity, 'side': side, 'price': price, 'order_type': order_type})
        else:
            logger.info(f"Market is closed, not placing {side} order for {stock}: {quantity} shares", extra={
                        'strategy_name': self.strategy_name, 'stock': stock, 'quantity': quantity, 'side': side, 'price': price, 'order_type': order_type})
