import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import Base, Trade, AccountInfo, Strategy, Position

DATABASE_URL = "sqlite:///trades.db"

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

class DBManager:
    def __init__(self, engine):
        self.Session = sessionmaker(bind=engine)

    def add_account_info(self, account_info):
        with self.Session() as session:
            existing_info = session.query(AccountInfo).filter_by(broker=account_info.broker).first()
            if existing_info:
                existing_info.value = account_info.value
            else:
                session.add(account_info)
            session.commit()

    def get_trade(self, trade_id):
        session = self.Session()
        try:
            return session.query(Trade).filter_by(id=trade_id).first()
        finally:
            session.close()

    def get_all_trades(self):
        session = self.Session()
        try:
            return session.query(Trade).all()
        finally:
            session.close()

    def calculate_profit_loss(self, trade):
        current_price = trade.executed_price
        if current_price is None:
            raise ValueError("Executed price is None, cannot calculate profit/loss")
        if trade.order_type.lower() == 'buy':
            return (current_price - trade.price) * trade.quantity
        elif trade.order_type.lower() == 'sell':
            return (trade.price - current_price) * trade.quantity

    def update_trade_status(self, trade_id, executed_price, success, profit_loss):
        session = self.Session()
        try:
            trade = session.query(Trade).filter_by(id=trade_id).first()
            if trade:
                trade.executed_price = executed_price
                trade.success = success
                trade.profit_loss = profit_loss
                session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def add_strategy(self, strategy_name):
        session = self.Session()
        try:
            strategy = session.query(Strategy).filter_by(name=strategy_name).first()
            if not strategy:
                strategy = Strategy(name=strategy_name)
                session.add(strategy)
                session.commit()
            return strategy
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def get_strategy(self, strategy_name):
        session = self.Session()
        try:
            return session.query(Strategy).filter_by(name=strategy_name).first()
        finally:
            session.close()

    def update_position(self, broker_name, strategy_id, symbol, quantity, latest_price, cost):
        session = self.Session()
        try:
            position = session.query(Position).filter_by(broker=broker_name, strategy_id=strategy_id, symbol=symbol).first()
            if position:
                position.quantity = quantity
                position.latest_price = latest_price
                position.cost = cost
                position.last_updated = datetime.now()
            else:
                position = Position(
                    broker=broker_name,
                    strategy_id=strategy_id,
                    symbol=symbol,
                    quantity=quantity,
                    latest_price=latest_price,
                    cost=cost,
                    last_updated=datetime.now()
                )
                session.add(position)
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def sync_positions(self, broker_name, positions_data):
        session = self.Session()
        try:
            # Fetch all existing positions for the broker
            existing_positions = session.query(Position).filter_by(broker=broker_name).all()
            existing_symbols = {pos.symbol for pos in existing_positions}

            # Update or add positions
            for symbol, data in positions_data.items():
                strategy_name = data['strategy']
                strategy = self.get_strategy(strategy_name)
                if strategy:
                    self.update_position(
                        broker_name,
                        strategy.id,
                        symbol,
                        data['quantity'],
                        data['cost_basis'] / data['quantity'],
                        data['cost_basis']
                    )
                    existing_symbols.discard(symbol)

            # Remove positions that are no longer in the broker data
            for symbol in existing_symbols:
                position = session.query(Position).filter_by(broker=broker_name, symbol=symbol).first()
                if position:
                    session.delete(position)
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
