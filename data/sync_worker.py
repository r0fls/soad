import asyncio
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from utils.logger import logger
from utils.utils import is_option, is_market_open, OPTION_MULTIPLIER
from database.models import Position, Balance


# Hack for unit testing
def position_exists(broker, symbol):
    return broker.position_exists(symbol)


async def sync_worker(engine, brokers):
    Session = sessionmaker(bind=engine)
    session = Session()

    def get_broker_instance(broker_name):
        logger.debug(f'Getting broker instance for {broker_name}')
        return brokers[broker_name]

    async def update_latest_prices(session, timestamp=None):
        if timestamp is None:
            timestamp = datetime.utcnow()
        now = timestamp
        logger.info('Updating latest prices for positions')
        positions = session.query(Position).all()
        for position in positions:
            latest_price = await get_latest_price(position)
            if latest_price is None:
                logger.error(f'Could not get latest price for {position.symbol}')
                continue
            logger.debug(f'Updated latest price for {position.symbol} to {latest_price}')
            position.latest_price = latest_price
            position.last_updated = now
        session.commit()
        logger.info('Completed updating latest prices')

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
            new_uncategorized_balance = Balance(
                broker=broker[0],
                strategy='uncategorized',
                type='cash',
                balance=uncategorized_balance,
                timestamp=now
            )
            session.add(new_uncategorized_balance)
            logger.debug(f'Added new uncategorized balance for broker {broker[0]}: {uncategorized_balance}')

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
                # Get the current total quantity we have of this position in the database across all strategies
                total_quantity = session.query(Position).filter_by(broker=broker[0], symbol=position['symbol']).all()
                total_quantity = sum([p.quantity for p in total_quantity])
                if total_quantity > 0:
                    uncategorized_quantity = position['quantity'] - total_quantity
                if uncategorized_quantity <= 0:
                    continue
                new_position = Position(
                    broker=broker[0],
                    symbol=position['symbol'],
                    quantity=uncategorized_quantity,
                    latest_price=position['latest_price'],
                    cost_basis=position['cost_basis'],
                    last_updated=now
                )
                session.add(new_position)
                logger.debug(f'Added new uncategorized position {position["symbol"]}')

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
                    # check if we still have the position in the broker account
                    if not position_exists(get_broker_instance(position.broker), position.symbol):
                        logger.debug(f'Position {position.symbol} does not exist in broker {position.broker}, should be deleted from database')
                        continue
                    latest_price = await get_latest_price(position)
                    multiplier = 1
                    if is_option(position.symbol):
                        multiplier = OPTION_MULTIPLIER
                    position_balance = position.quantity * latest_price * multiplier
                    positions_total += position_balance
                    logger.debug(f'Updated position balance for {position.symbol}: {position_balance}')

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
        await update_latest_prices(session, now)
        await add_uncategorized_positions(session, now)
        logger.info('Sync worker completed an iteration')
    except Exception as e:
        logger.error('Error in sync worker iteration', extra={'error': str(e)})
