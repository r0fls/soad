import asyncio
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from utils.logger import logger
from database.models import Position, Balance

async def sync_worker(engine, brokers):
    Session = sessionmaker(bind=engine)
    session = Session()

    def get_broker_instance(broker_name):
        logger.debug(f'Getting broker instance for {broker_name}')
        return brokers[broker_name]

    async def update_latest_prices(session):
        logger.info('Updating latest prices for positions')
        positions = session.query(Position).all()
        for position in positions:
            latest_price = await get_latest_price(position)
            logger.debug(f'Updated latest price for {position.symbol} to {latest_price}')
            position.latest_price = latest_price
            position.last_updated = datetime.utcnow()
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

    async def update_cash_and_position_balances(session):
        logger.info('Updating cash and position balances')
        brokers = session.query(Balance.broker).distinct().all()
        for broker in brokers:
            broker_name = broker[0]
            logger.debug(f'Processing balances for broker {broker_name}')
            strategies = session.query(Position.strategy).filter_by(broker=broker_name).distinct().all()
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
                    timestamp=datetime.utcnow()
                )
                session.add(new_cash_balance)
                logger.debug(f'Added new cash balance for strategy {strategy_name} of broker {broker_name}: {actual_cash_balance}')

                positions = session.query(Position).filter_by(broker=broker_name, strategy=strategy_name).all()
                positions_total = 0.0

                for position in positions:
                    latest_price = await get_latest_price(position)
                    position_balance = position.quantity * latest_price
                    positions_total += position_balance
                    logger.debug(f'Updated position balance for {position.symbol}: {position_balance}')

                new_position_balance = Balance(
                    broker=broker_name,
                    strategy=strategy_name,
                    type='positions',
                    balance=positions_total,
                    timestamp=datetime.utcnow()
                )
                session.add(new_position_balance)
                logger.debug(f'Added new position balance for strategy {strategy_name} of broker {broker_name}: {positions_total}')

        session.commit()
        logger.info('Completed updating cash and position balances')

    while True:
        try:
            logger.info('Starting sync worker iteration')
            await update_latest_prices(session)
            await update_cash_and_position_balances(session)
            logger.info('Sync worker completed an iteration')
        except Exception as e:
            logger.error('Error in sync worker iteration', extra={'error': str(e)})

        await asyncio.sleep(300)
