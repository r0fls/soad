from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import Base, Trade, AccountInfo

DATABASE_URL = "sqlite:///trades.db"

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

class DBManager:
    def __init__(self):
        self.engine = engine
        self.Session = Session

    def add_trade(self, trade):
        session = self.Session()
        try:
            session.add(trade)
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def add_account_info(self, account_info):
        session = self.Session()
        try:
            existing_info = session.query(AccountInfo).first()
            if existing_info:
                session.delete(existing_info)
                session.commit()
            session.add(account_info)
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

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
