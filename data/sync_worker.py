import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from datetime import datetime, timezone
from utils.logger import logger
from utils.utils import is_option, extract_option_details, OPTION_MULTIPLIER, futures_contract_size, is_futures_symbol
from database.models import Position, Balance
import yfinance as yf
import sqlalchemy


class BrokerService:
    def __init__(self, brokers):
        self.brokers = brokers

    def get_broker_instance(self, broker_name):
        logger.debug(f'Getting broker instance for {broker_name}')
        return self.brokers[broker_name]

    async def get_latest_price(self, broker_name, symbol):
        broker_instance = self.get_broker_instance(broker_name)
        # check if get_current_price is a coroutine function
        if asyncio.iscoroutinefunction(broker_instance.get_current_price):
            return await broker_instance.get_current_price(symbol)
        else:
            return broker_instance.get_current_price(symbol)


class PositionService:
    def __init__(self, broker_service):
        self.broker_service = broker_service

    async def reconcile_positions(self, session, broker, timestamp=None):
        logger.info(f"Reconciling positions for broker: {broker}")
        now = timestamp or datetime.now()

        # Get positions from the broker
        broker_instance = self.broker_service.get_broker_instance(broker)
        broker_positions = await broker_instance.get_positions()  # Assuming this returns a list of positions

        # Get positions from the database
        db_positions = await session.execute(
            select(Position).filter_by(broker=broker)
        )
        db_positions = {pos.symbol: pos for pos in db_positions.scalars()}

        # Remove positions in the DB that are not in the broker's list
        broker_symbols = {pos['symbol'] for pos in broker_positions}
        db_symbols = set(db_positions.keys())

        # Positions to remove from the database
        symbols_to_remove = db_symbols - broker_symbols
        if symbols_to_remove:
            await session.execute(
                sqlalchemy.delete(Position).where(Position.broker == broker, Position.symbol.in_(symbols_to_remove))
            )
            logger.info(f"Removed positions from DB for broker {broker}: {symbols_to_remove}")

        # Add positions from the broker that aren't in the database
        symbols_to_add = broker_symbols - db_symbols
        for broker_pos in broker_positions:
            if broker_pos['symbol'] in symbols_to_add:
                # Add the missing position to the database as uncategorized
                new_position = Position(
                    broker=broker,
                    strategy='uncategorized',
                    symbol=broker_pos['symbol'],
                    quantity=broker_pos['quantity'],
                    latest_price=broker_pos['latest_price'],
                    last_updated=now,
                )
                session.add(new_position)
                logger.info(f"Added uncategorized position to DB: {new_position}")

        await session.commit()
        logger.info(f"Reconciliation for broker {broker} completed.")

    async def update_position_prices_and_volatility(self, session, positions, timestamp):
        now = timestamp or datetime.now()

        now_naive = now.replace(tzinfo=None)

        for position in positions:
            try:
                await self._update_position_price(session, position, now_naive)
            except Exception as e:
                logger.exception(f"Error processing position {position.symbol}")

        await session.commit()
        logger.info('Completed updating latest prices and volatility')

    async def _update_position_price(self, session, position, now_naive):
        latest_price = await self.broker_service.get_latest_price(position.broker, position.symbol)
        if latest_price is None:
            logger.error(f'Could not get latest price for {position.symbol}')
            return

        logger.debug(f'Updated latest price for {position.symbol} to {latest_price}')
        position.latest_price = latest_price
        position.last_updated = now_naive

        underlying_symbol = self._get_underlying_symbol(position)
        latest_underlying_price = await self.broker_service.get_latest_price(position.broker, underlying_symbol)
        volatility = await self._calculate_historical_volatility(underlying_symbol)

        if volatility is None:
            logger.error(f'Could not calculate volatility for {underlying_symbol}')
            return

        logger.debug(f'Updated volatility for {position.symbol} to {volatility}')
        position.underlying_volatility = float(volatility)
        position.underlying_latest_price = float(latest_underlying_price)

    @staticmethod
    def _get_underlying_symbol(position):
        return extract_option_details(position.symbol)[0] if is_option(position.symbol) else position.symbol

    @staticmethod
    async def _calculate_historical_volatility(symbol):
        logger.debug(f'Calculating historical volatility for {symbol}')
        try:
            stock = yf.Ticker(symbol)
            hist = stock.history(period="1y")
            hist['returns'] = hist['Close'].pct_change()
            volatility = hist['returns'].std() * (252 ** 0.5)  # Annualized volatility
            return volatility
        except Exception as e:
            logger.error(f'Error calculating volatility for {symbol}: {e}')
            return None


class BalanceService:
    def __init__(self, broker_service):
        self.broker_service = broker_service

    async def update_uncategorized_balances(self, session, timestamp):
        now = timestamp or datetime.now()
        logger.info('Updating uncategorized balances')
        brokers = await session.execute(select(Balance.broker).distinct())
        for broker in brokers.scalars():
            await self._process_broker_balances(session, broker, now)

        await session.commit()
        logger.info('Completed updating uncategorized balances')

    async def _process_broker_balances(self, session, broker, timestamp):
        broker_instance = self.broker_service.get_broker_instance(broker)
        account_info = await broker_instance.get_account_info()
        total_value = account_info['value']
        uncategorized_balance = total_value

        strategies = await session.execute(select(Balance.strategy).filter_by(broker=broker).distinct())
        for strategy in strategies.scalars():
            uncategorized_balance -= await self._get_strategy_balances(session, broker, strategy)

        uncategorized_position_balance = await session.execute(
            select(Balance).
            filter_by(broker=broker, strategy='uncategorized', type='positions').
            order_by(Balance.timestamp.desc()).
            limit(1)
        )
        uncategorized_position_balance = uncategorized_position_balance.scalar()
        uncategorized_balance -= uncategorized_position_balance.balance if uncategorized_position_balance else 0.0

        if uncategorized_balance < 0:
            logger.error(f'Uncategorized balance for broker {broker} is negative: {uncategorized_balance}. Setting to 0.')
            uncategorized_balance = 0

        new_uncategorized_balance = Balance(
            broker=broker,
            strategy='uncategorized',
            type='cash',
            balance=uncategorized_balance,
            timestamp=timestamp
        )
        session.add(new_uncategorized_balance)
        logger.debug(f'Added new uncategorized balance for broker {broker}: {uncategorized_balance}')

    async def _get_strategy_balances(self, session, broker, strategy):
        cash_balance = await session.execute(
                select(Balance).
                filter_by(broker=broker, strategy=strategy, type='cash').
                order_by(Balance.timestamp.desc()).
                limit(1)
        )
        cash_balance = cash_balance.scalar()
        cash_balance = cash_balance.balance if cash_balance else 0.0

        position_balance = await session.execute(
                select(Balance).filter_by(broker=broker, strategy=strategy, type='positions').
                order_by(Balance.timestamp.desc()).
                limit(1)
        )
        position_balance = position_balance.scalar()
        position_balance = position_balance.balance if position_balance else 0.0

        return cash_balance + position_balance


async def sync_worker(engine, brokers):
    # Check if engine is a string or an Engine object
    if isinstance(engine, str):
        # Create an async engine if the connection URL is provided
        async_engine = create_async_engine(engine)
    elif isinstance(engine, sqlalchemy.engine.Engine):
        # Error handling to ensure we don't pass a synchronous engine where async is required
        raise ValueError("AsyncEngine expected, but got a synchronous Engine.")
    elif isinstance(engine, sqlalchemy.ext.asyncio.AsyncEngine):
        # If it's already an AsyncEngine, use it directly
        async_engine = engine
    else:
        raise ValueError("Invalid engine type. Expected a connection string or an AsyncEngine object.")

    # Use the async engine to create sessionmaker
    Session = sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=True)

    broker_service = BrokerService(brokers)
    position_service = PositionService(broker_service)
    balance_service = BalanceService(broker_service)

    try:
        logger.info('Starting sync worker iteration')
        now = datetime.now()
        async with Session() as session:
            # Update position prices and volatility
            positions = await session.execute(select(Position))
            await position_service.update_position_prices_and_volatility(session, positions.scalars(), now)
            # Update uncategorized balances
            await balance_service.update_uncategorized_balances(session, now)
        logger.info('Sync worker completed an iteration')
    except Exception as e:
        logger.error('Error in sync worker iteration', extra={'error': str(e)})
