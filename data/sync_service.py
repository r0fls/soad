import time
from datetime import datetime
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, func
from database.models import Trade, Position, Balance
from utils.config import parse_config, initialize_brokers

# Initialize the database and brokers
def initialize(config, engine):
    Session = sessionmaker(bind=engine)
    session = Session()
    brokers = initialize_brokers(config)
    return session, brokers

# Function to sync positions from brokers
def sync_positions(session, brokers):
    for broker_name, broker in brokers.items():
        account_info = broker.get_account_info()
        account_id = account_info['account_id']
        broker_positions = broker.get_positions()
        for bp in broker_positions:
            position = session.query(Position).filter_by(broker=broker_name, symbol=bp).first()
            latest_price = broker.get_current_price(bp)
            if not position:
                # Add uncategorized positions
                position = Position(
                    cost=round(broker_positions[bp]['cost_basis']/broker_positions[bp]['quantity'], 2),
                    broker=broker_name,
                    strategy='uncategorized',
                    symbol=bp,
                    quantity=broker_positions[bp]['quantity'],
                    latest_price=latest_price,
                    last_updated=datetime.now()
                )
                session.add(position)
            else:
                # Update existing position
                position.quantity = broker_positions[bp]['quantity']
                position.cost = round(broker_positions[bp]['cost_basis']/broker_positions[bp]['quantity'], 2)
                position.price = latest_price
                position.timestamp = datetime.now()
        # Update balances for each broker/strategy
        balances = session.query(Balance).filter(
                func.lower(Balance.broker)==func.lower(broker_name)
                ).all()
        for balance in balances:
            positions = session.query(Position).filter_by(broker=broker_name).all()
            balance.value = sum(p.quantity * p.latest_price for p in positions if p.strategy == balance.strategy)
            session.commit()
        session.commit()


# Main function to run the sync service
def run_sync_service(config, engine):
    session, brokers = initialize(config, engine)
    sync_positions(session, brokers)
    #while True:
    #    sync_positions(session, brokers)
    #    update_prices_and_balances(session, brokers)
    #    time.sleep(300)  # Wait for 5 minutes before the next sync
