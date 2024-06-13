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

    def update_latest_prices(session):
        positions = session.query(Position).all()
        for position in positions:
            broker_instance = get_broker_instance(position.broker)
            latest_price = broker_instance.get_current_price(position.symbol)
            position.latest_price = latest_price
            position.last_updated = datetime.utcnow()
        session.commit()

    def update_position_balances(session):
        balances = session.query(Balance).filter_by(type='positions').all()
        for balance in balances:
            positions = session.query(Position).filter_by(balance_id=balance.id).all()
            total_value = sum(position.quantity * position.latest_price for position in positions)
            balance.balance = total_value
            balance.timestamp = datetime.utcnow()
        session.commit()

    def update_cash_and_total_balances(session):
        brokers = session.query(Balance.broker).distinct().all()
        for broker in brokers:
            broker_name = broker[0]
            # Update cash balance
            cash_balance = session.query(Balance).filter_by(broker=broker_name, type='cash').first()
            if cash_balance:
                # Assuming you have a way to get the actual cash balance
                actual_cash_balance = get_broker_instance(broker_name).get_cash_balance()  # Replace with actual method
                cash_balance.balance = actual_cash_balance
                cash_balance.timestamp = datetime.utcnow()

            # Update total account balance
            total_balance = session.query(Balance).filter_by(broker=broker_name, strategy=None, type='positions').first()
            if total_balance:
                positions_balance = session.query(Balance).filter_by(broker=broker_name, type='positions').all()
                positions_total = sum(balance.balance for balance in positions_balance)
                total_balance.balance = positions_total + (cash_balance.balance if cash_balance else 0.0)
                total_balance.timestamp = datetime.utcnow()

        session.commit()

    while True:
        try:
            update_latest_prices(session)
            update_position_balances(session)
            update_cash_and_total_balances(session)
            logger.info('Sync worker completed an iteration')
        except Exception as e:
            logger.error('Error in sync worker iteration', extra={'error': str(e)})

        await asyncio.sleep(300)
