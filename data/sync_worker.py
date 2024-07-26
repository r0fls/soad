import asyncio
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
    Session = sessionmaker(bind=engine)
    session = Session()

    def get_broker_instance(broker_name):
        logger.debug(f'Getting broker instance for {broker_name}')
        return brokers[broker_name]

    async def update_latest_prices_and_volatility(session, timestamp=None):
        if timestamp is None:
            timestamp = datetime.utcnow()
        now = timestamp
        logger.info('Updating latest prices and volatility for positions')
        positions = session.query(Position).all()
        for position in positions:
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
        session.add_all(positions)
        session.commit()
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
        if asyncio.iscoroutinefunction(broker_instance.get_current_price):
            latest_price = await broker_instance.get_current_price(symbol)
        else:
            latest_price = broker_instance.get_current_price(symbol)
        logger.debug(f'Latest price for {symbol} is {latest_price}')
        return latest_price


    async def get_latest_price(position):
        logger.debug(f'Getting latest price for {position.symbol} from broker {position.broker}')
        broker_instance = get_broker_instance(position.broker)
        if asyncio.iscoroutinefunction(broker_instance.get_current_price):
            latest_price = await broker_instance.get_current_price(position.symbol)
        else:
            latest_price = broker_instance.get_current_price(position.symbol)
        logger.debug(f'Latest price for {position.symbol} is {latest_price}')
        return latest_price

    async def update_uncategorized_balances(session, timestamp=None):
        """
        Update uncategorized balances for each strategy of each broker
        """
        if timestamp is None:
            timestamp = datetime.utcnow()
        now = timestamp
        logger.info('Updating uncategorized balances')
        brokers = session.query(Balance.broker).distinct().all()
        for broker in brokers:
            broker_instance = get_broker_instance(broker[0])
            account_info = broker_instance.get_account_info()
            logger.debug(f'Processing uncategorized balances for broker {broker[0]}')
            total_value = account_info['value']
            uncategorized_balance = total_value
            # Filter for all strategies of the broker except 'uncategorized'
            strategies = session.query(Balance.strategy).filter_by(broker=broker[0]).where(Balance.strategy != 'uncategorized').distinct().all()
            for strategy in strategies:
                strategy_name = strategy.strategy
                logger.debug(f'Processing uncategorized balances for strategy {strategy_name} of broker {broker[0]}')
                cash_balance = session.query(Balance).filter_by(
                    broker=broker[0], strategy=strategy_name, type='cash'
                ).order_by(Balance.timestamp.desc()).first()
                cash_balance = cash_balance.balance if cash_balance else 0.0
                position_balance = session.query(Balance).filter_by(
                    broker=broker[0], strategy=strategy_name, type='positions'
                ).order_by(Balance.timestamp.desc()).first()
                position_balance = position_balance.balance if position_balance else 0.0
                uncategorized_balance = uncategorized_balance - cash_balance - position_balance
            # Subtract any uncategorized position balances
            uncategorized_position_balance = session.query(Balance).filter_by(
                broker=broker[0], strategy='uncategorized', type='positions'
            ).order_by(Balance.timestamp.desc()).first()
            uncategorized_position_balance = uncategorized_position_balance.balance if uncategorized_position_balance else 0.0
            uncategorized_balance -= uncategorized_position_balance
            if uncategorized_balance < 0:
                logger.error(f'Uncategorized balance for broker {broker[0]} is negative: {uncategorized_balance}. Setting to 0. Consider reducing strategy balances.')
                uncategorized_balance = 0
            new_uncategorized_balance = Balance(
                broker=broker[0],
                strategy='uncategorized',
                type='cash',
                balance=uncategorized_balance,
                timestamp=now
            )
            session.add(new_uncategorized_balance)
            logger.debug(f'Added new uncategorized balance for broker {broker[0]}: {uncategorized_balance}')
        session.commit()
        logger.info('Completed updating uncategorized balances')

    async def add_uncategorized_positions(session, timestamp=None):
        """
        Add uncategorized positions to the database
        """
        if timestamp is None:
            timestamp = datetime.utcnow()
        now = timestamp
        logger.info('Adding uncategorized positions')
        brokers = session.query(Balance.broker).distinct().all()
        for broker in brokers:
            broker_instance = get_broker_instance(broker[0])
            account_info = broker_instance.get_account_info()
            logger.debug(f'Processing uncategorized positions for broker {broker[0]}')
            positions = broker_instance.get_positions()
            for position in positions:
                uncategorized_quantity = positions[position]['quantity']
                # Get the current total quantity we have of this position in the database across all strategies
                total_quantity = session.query(Position).filter_by(broker=broker[0], symbol=position).all()
                total_quantity = sum([p.quantity for p in total_quantity if p.quantity > 0])
                if total_quantity > 0:
                    uncategorized_quantity = uncategorized_quantity - total_quantity
                if uncategorized_quantity <= 0:
                    continue
                latest_price = await get_latest_price(position)
                new_position = Position(
                    broker=broker[0],
                    symbol=position,
                    strategy='uncategorized',
                    quantity=uncategorized_quantity,
                    latest_price=latest_price,
                    cost_basis=positions[position].get('cost_basis', 0),
                    last_updated=now
                )
                session.add(new_position)
                logger.debug(f'Added new uncategorized position {position}')
        session.commit()
        logger.info('Completed adding uncategorized positions')

    async def update_cash_and_position_balances(session, timestamp=None):
        if timestamp is None:
            timestamp = datetime.utcnow()
        now = timestamp
        logger.info('Updating cash and position balances')
        brokers = session.query(Balance.broker).distinct().all()
        for broker in brokers:
            broker_name = broker[0]
            logger.debug(f'Processing balances for broker {broker_name}')
            # Look in balances for strategies for now since we don't have a strategy table
            strategies = session.query(Balance.strategy).filter_by(broker=broker_name).distinct().all()
            for strategy in strategies:
                strategy_name = strategy[0]
                logger.debug(f'Processing balances for strategy {strategy_name} of broker {broker_name}')

                previous_cash_balance = session.query(Balance).filter_by(
                    broker=broker_name, strategy=strategy_name, type='cash'
                ).order_by(Balance.timestamp.desc()).first()
                actual_cash_balance = previous_cash_balance.balance if previous_cash_balance else 0.0

                new_cash_balance = Balance(
                    broker=broker_name,
                    strategy=strategy_name,
                    type='cash',
                    balance=actual_cash_balance,
                    timestamp=now
                )
                session.add(new_cash_balance)
                logger.debug(f'Added new cash balance for strategy {strategy_name} of broker {broker_name}: {actual_cash_balance}')

                positions = session.query(Position).filter_by(broker=broker_name, strategy=strategy_name).all()
                positions_total = 0.0

                for position in positions:
                    try:
                        # check if we still have the position in the broker account
                        if not position_exists(get_broker_instance(position.broker), position.symbol):
                            logger.debug(f'Position {position.symbol} does not exist in broker {position.broker}, will be deleted from database')
                            session.delete(position)
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

        session.commit()
        logger.info('Completed updating cash and position balances')

    try:
        logger.info('Starting sync worker iteration')
        now = datetime.utcnow()
        await update_cash_and_position_balances(session, now)
        await update_uncategorized_balances(session, now)
        await update_latest_prices_and_volatility(session, now)
        await add_uncategorized_positions(session, now)
        logger.info('Sync worker completed an iteration')
    except Exception as e:
        logger.error('Error in sync worker iteration', extra={'error': str(e)})
    finally:
        session.close()
