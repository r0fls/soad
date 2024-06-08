import time
from datetime import datetime
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, func
from database.models import Trade, Position, Balance, Strategy
from utils.config import parse_config

# Initialize the database and brokers
def initialize(config, engine):
    Session = sessionmaker(bind=engine)
    session = Session()
    brokers, strategies = initialize(config)
    return session, brokers

# Function to find a suitable strategy for a position
def find_strategy_for_position(position, session):
    strategies = session.query(Strategy).all()
    for strategy in strategies:
        if strategy.can_trade(position.symbol):  # Assuming the Strategy model has a can_trade method
            return strategy.name  # Assuming strategy has a name field
    return 'uncategorized'

# Function to sync positions from brokers
def sync_positions(session, brokers):
    for broker_name, broker in brokers:
        account_info = broker.get_account_info()
        account_id = account_info['account_id']
        broker_positions = broker.get_positions()

        # Create a map of broker positions
        brokerage_positions_map = {pos: broker_positions[pos] for pos in broker_positions}

        # Fetch all positions from the database for the current broker
        db_positions = session.query(Position).filter_by(broker=broker_name).all()

        # Remove positions from the DB that are not in brokerage accounts
        for db_pos in db_positions:
            if db_pos.symbol not in brokerage_positions_map:
                session.delete(db_pos)
            else:
                # Update existing position
                brokerage_pos = brokerage_positions_map[db_pos.symbol]
                latest_price = broker.get_current_price(db_pos.symbol)
                db_pos.quantity = brokerage_pos['quantity']
                db_pos.cost = round(brokerage_pos['cost_basis'] / brokerage_pos['quantity'], 2)
                db_pos.latest_price = latest_price
                db_pos.last_updated = datetime.now()
                session.add(db_pos)

        # Add new positions from brokerage to DB
        for bp in broker_positions:
            if bp not in [pos.symbol for pos in db_positions]:
                latest_price = broker.get_current_price(bp)
                new_position = Position(
                    cost=round(broker_positions[bp]['cost_basis'] / broker_positions[bp]['quantity'], 2),
                    broker=broker_name,
                    strategy=find_strategy_for_position(bp, session),
                    symbol=bp,
                    quantity=broker_positions[bp]['quantity'],
                    latest_price=latest_price,
                    last_updated=datetime.now()
                )
                session.add(new_position)

        # Update balances for each broker/strategy
        balances = session.query(Balance).filter(
            func.lower(Balance.broker) == func.lower(broker_name)
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
    while True:
        sync_positions(session, brokers)
        time.sleep(300) 
