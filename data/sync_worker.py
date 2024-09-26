import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from utils.logger import logger
from utils.utils import is_option, is_market_open, extract_option_details, OPTION_MULTIPLIER, futures_contract_size, is_futures_symbol
from database.models import Position, Balance
import yfinance as yf

# Hack for unit testing
def position_exists(broker, symbol):
    return broker.position_exists(symbol)


async def sync_worker(engine, brokers):
    async_engine = create_async_engine(engine)
    Session = sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)

    def get_broker_instance(broker_name):
        logger.debug(f'Getting broker instance for {broker_name}')
        return brokers[broker_name]

    async def update_latest_prices_and_volatility(session, timestamp=None):
        if timestamp is None:
            timestamp = datetime.utcnow()
        now = timestamp
        logger.info('Updating latest prices and volatility for positions')
        positions = await session.execute(session.query(Position).all())
        for position in positions.scalars():
            try:
                latest_price = await get_latest_price(position)
                if latest_price is None:
                    logger.error(f'Could not get latest price for {position.symbol}')
                    continue
                logger.debug(f'Updated latest price for {position.symbol} to {latest_price}')
                position.latest_price = latest_price
                position.last_updated = now

                # Calculate historical volatility using yfinance
                underlying_symbol = extract_option_details(position.symbol)[0] if is_option(position.symbol) else position.symbol
                broker_instance = get_broker_instance(position.broker)
                latest_underlying_price = await get_latest_price_by_symbol(position.broker, underlying_symbol)
                volatility = await calculate_historical_volatility(underlying_symbol)
                if volatility is None:
                    logger.error(f'Could not calculate volatility for {underlying_symbol}')
                    continue
                logger.debug(f'Updated volatility for {position.symbol} to {volatility}')
                position.underlying_volatility = float(volatility)
                position.underlying_latest_price = float(latest_underlying_price)

            except Exception as e:
                logger.exception(f"Error processing position {position.symbol}")
        await session.commit()
        logger.info('Completed updating latest prices and volatility')

    async def calculate_historical_volatility(symbol):
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

    async def get_latest_price_by_symbol(broker, symbol):
        logger.debug(f'Getting latest price for {symbol} from broker {broker}')
        broker_instance = get_broker_instance(broker)
        latest_price = await broker_instance.get_current_price(symbol)
        logger.debug(f'Latest price for {symbol} is {latest_price}')
        return latest_price

    async def get_latest_price(position):
        logger.debug(f'Getting latest price for {position.symbol} from broker {position.broker}')
        broker_instance = get_broker_instance(position.broker)
        latest_price = await broker_instance.get_current_price(position.symbol)
        logger.debug(f'Latest price for {position.symbol} is {latest_price}')
        return latest_price

    async def update_uncategorized_balances(session, timestamp=None):
        if timestamp is None:
            timestamp = datetime.utcnow()
        now = timestamp
        logger.info('Updating uncategorized balances')
        brokers = await session.execute(session.query(Balance.broker).distinct())
        for broker in brokers.scalars():
            broker_instance = get_broker_instance(broker)
            account_info = broker_instance.get_account_info()
            logger.debug(f'Processing uncategorized balances for broker {broker}')
            total_value = account_info['value']
            uncategorized_balance = total_value

            strategies = await session.execute(session.query(Balance.strategy)
                                               .filter_by(broker=broker)
                                               .where(Balance.strategy != 'uncategorized').distinct())
            for strategy in strategies.scalars():
                cash_balance = await session.execute(session.query(Balance).filter_by(
                    broker=broker, strategy=strategy, type='cash'
                ).order_by(Balance.timestamp.desc()).first())
                cash_balance = cash_balance.scalar().balance if cash_balance.scalar() else 0.0

                position_balance = await session.execute(session.query(Balance).filter_by(
                    broker=broker, strategy=strategy, type='positions'
                ).order_by(Balance.timestamp.desc()).first())
                position_balance = position_balance.scalar().balance if position_balance.scalar() else 0.0

                uncategorized_balance -= (cash_balance + position_balance)

            uncategorized_position_balance = await session.execute(session.query(Balance).filter_by(
                broker=broker, strategy='uncategorized', type='positions'
            ).order_by(Balance.timestamp.desc()).first())
            uncategorized_position_balance = uncategorized_position_balance.scalar().balance if uncategorized_position_balance.scalar() else 0.0

            uncategorized_balance -= uncategorized_position_balance
            if uncategorized_balance < 0:
                logger.error(f'Uncategorized balance for broker {broker} is negative: {uncategorized_balance}. Setting to 0.')
                uncategorized_balance = 0

            new_uncategorized_balance = Balance(
                broker=broker,
                strategy='uncategorized',
                type='cash',
                balance=uncategorized_balance,
                timestamp=now
            )
            session.add(new_uncategorized_balance)
            logger.debug(f'Added new uncategorized balance for broker {broker}: {uncategorized_balance}')

        await session.commit()
        logger.info('Completed updating uncategorized balances')

    async def add_uncategorized_positions(session, timestamp=None):
        if timestamp is None:
            timestamp = datetime.utcnow()
        now = timestamp
        logger.info('Adding uncategorized positions')
        brokers = await session.execute(session.query(Balance.broker).distinct())
        for broker in brokers.scalars():
            broker_instance = get_broker_instance(broker)
            account_info = broker_instance.get_account_info()
            logger.debug(f'Processing uncategorized positions for broker {broker}')
            positions = broker_instance.get_positions()
            for position_symbol, position_data in positions.items():
                uncategorized_quantity = position_data['quantity']
                total_quantity = await session.execute(session.query(Position).filter_by(broker=broker, symbol=position_symbol).all())
                total_quantity = sum([p.quantity for p in total_quantity.scalars() if p.quantity > 0])
                uncategorized_quantity -= total_quantity

                if uncategorized_quantity > 0:
                    latest_price = await get_latest_price_by_symbol(broker, position_symbol)
                    new_position = Position(
                        broker=broker,
                        symbol=position_symbol,
                        strategy='uncategorized',
                        quantity=uncategorized_quantity,
                        latest_price=latest_price,
                        cost_basis=position_data.get('cost_basis', 0),
                        last_updated=now
                    )
                    session.add(new_position)
                    logger.debug(f'Added new uncategorized position {position_symbol}')

        await session.commit()
        logger.info('Completed adding uncategorized positions')

    async def update_cash_and_position_balances(session, timestamp=None):
        if timestamp is None:
            timestamp = datetime.utcnow()
        now = timestamp
        logger.info('Updating cash and position balances')
        brokers = await session.execute(session.query(Balance.broker).distinct())
        for broker in brokers.scalars():
            broker_name = broker
            logger.debug(f'Processing balances for broker {broker_name}')
            strategies = await session.execute(session.query(Balance.strategy).filter_by(broker=broker_name).distinct())
            for strategy in strategies.scalars():
                strategy_name = strategy
                logger.debug(f'Processing balances for strategy {strategy_name} of broker {broker_name}')

                previous_cash_balance = await session.execute(session.query(Balance).filter_by(
                    broker=broker_name, strategy=strategy_name, type='cash'
                ).order_by(Balance.timestamp.desc()).first())
                actual_cash_balance = previous_cash_balance.scalar().balance if previous_cash_balance.scalar() else 0.0

                new_cash_balance = Balance(
                    broker=broker_name,
                    strategy=strategy_name,
                    type='cash',
                    balance=actual_cash_balance,
                    timestamp=now
                )
                session.add(new_cash_balance)
                logger.debug(f'Added new cash balance for strategy {strategy_name} of broker {broker_name}: {actual_cash_balance}')

                positions = await session.execute(session.query(Position).filter_by(broker=broker_name, strategy=strategy_name).all())
                positions_total = 0.0

                for position in positions.scalars():
                    try:
                        if not position_exists(get_broker_instance(position.broker), position.symbol):
                            logger.debug(f'Position {position.symbol} does not exist in broker {position.broker}, deleting from database')
                            await session.delete(position)
                            continue
                        latest_price = await get_latest_price(position)
                        multiplier = 1
                        if is_futures_symbol(position.symbol):
                            multiplier = futures_contract_size(position.symbol)
                        if is_option(position.symbol):
                            multiplier = OPTION_MULTIPLIER
                        position_balance = position.quantity * latest_price * multiplier
                        positions_total += position_balance
                        logger.debug(f'Updated position balance for {position.symbol}: {position_balance}')
                    except Exception as e:
                        logger.error(f'Error updating position balance for {position.symbol}: {e}')
                        continue

                new_position_balance = Balance(
                    broker=broker_name,
                    strategy=strategy_name,
                    type='positions',
                    balance=positions_total,
                    timestamp=now
                )
                session.add(new_position_balance)
                logger.debug(f'Added new position balance for strategy {strategy_name} of broker {broker_name}: {positions_total}')

        await session.commit()
        logger.info('Completed updating cash and position balances')

    try:
        logger.info('Starting sync worker iteration')
        now = datetime.utcnow()
        async with Session() as session:
            await update_cash_and_position_balances(session, now)
            await update_uncategorized_balances(session, now)
            await update_latest_prices_and_volatility(session, now)
            await add_uncategorized_positions(session, now)
        logger.info('Sync worker completed an iteration')
    except Exception as e:
        logger.error('Error in sync worker iteration', extra={'error': str(e)})
