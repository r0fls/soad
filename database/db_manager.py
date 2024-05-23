from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import Base, Trade, AccountInfo

DATABASE_URL = "sqlite:///trades.db"

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

class DBManager:
    def __init__(self):
        self.session = Session()

    def add_trade(self, trade):
        self.session.add(trade)
        self.session.commit()

    def add_account_info(self, account_info):
        existing_info = self.session.query(AccountInfo).first()
        if existing_info:
            self.session.delete(existing_info)
            self.session.commit()
        self.session.add(account_info)
        self.session.commit()

    def get_trade(self, trade_id):
        return self.session.query(Trade).filter_by(id=trade_id).first()

    def get_all_trades(self):
        return self.session.query(Trade).all()
