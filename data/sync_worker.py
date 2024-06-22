import asyncio
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from utils.logger import logger
from database.models import Position, Balance

async def sync_worker(engine, brokers):
    Session = sessionmaker(bind=engine)
    session = Session()

    def get_broker_instance(broker_name):
        return brokers[broker_name]

    async def update_latest_prices(session):
        positions = session.query(Position).all()
        for position in positions:
            latest_price = await get_latest_price(position)
            position.latest_price = latest_price
            position.last_updated = datetime.utcnow()
        session.commit()


    async def get_latest_price(position):
        broker_instance = get_broker_instance(position.broker)
        if asyncio.iscoroutinefunction(broker_instance.get_current_price):
            latest_price = await broker_instance.get_current_price(position.symbol)
        else:
            latest_price = broker_instance.get_current_price(position.symbol)
        return latest_price

    async def update_cash_and_position_balances(session):
        brokers = session.query(Balance.broker).distinct().all()
        import pdb; pdb.set_trace()
        for broker in brokers:
            broker_name = broker[0]

            # Fetch the previous cash balance if it exists
            previous_cash_balance = session.query(Balance).filter_by(broker=broker_name, type='cash').order_by(Balance.timestamp.desc()).first()
            actual_cash_balance = previous_cash_balance.balance if previous_cash_balance else 0.0

            # Update cash balance if the actual cash balance has changed
            broker_instance = get_broker_instance(broker_name)
            if broker_instance:
                actual_cash_balance = broker_instance.cash

            new_cash_balance = Balance(
                broker=broker_name,
                strategy=None,
                type='cash',
                balance=actual_cash_balance,
                timestamp=datetime.utcnow()
            )
            session.add(new_cash_balance)

            # Fetch all positions balances and create new position balance entries
            positions = session.query(Position).filter_by(broker=broker_name).all()
            positions_total = 0.0

            for position in positions:
                latest_price = await get_latest_price(position)
                position_balance = position.quantity * latest_price
                positions_total += position_balance

                new_position_balance = Balance(
                    broker=broker_name,
                    strategy=position.strategy,
                    type='positions',
                    balance=position_balance,
                    timestamp=datetime.utcnow()
                )
                session.add(new_position_balance)

            # Create a new total balance entry
            total_balance_value = positions_total + actual_cash_balance
            new_total_balance = Balance(
                broker=broker_name,
                strategy=None,
                type='positions',
                balance=total_balance_value,
                timestamp=datetime.utcnow()
            )
            session.add(new_total_balance)

        session.commit()

    while True:
        try:
            await update_latest_prices(session)
            await update_cash_and_position_balances(session)
            logger.info('Sync worker completed an iteration')
        except Exception as e:
            logger.error('Error in sync worker iteration', extra={'error': str(e)})

        await asyncio.sleep(300)
