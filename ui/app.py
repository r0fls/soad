from flask import Flask, jsonify, send_from_directory
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, func
from database.models import Trade, AccountInfo
import os

app = Flask("TradingAPI")

DATABASE_URL = "sqlite:///trading.db"
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

# Serve the HTML file
@app.route('/')
def index():
    return send_from_directory(os.path.dirname(__file__), 'index.html')

# Static files
@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('./static', filename)

@app.route('/trades_per_strategy')
def trades_per_strategy():
    trades_count = session.query(Trade.strategy, func.count(Trade.id)).group_by(Trade.strategy).all()
    return jsonify({"trades_per_strategy": trades_count})

@app.route('/historic_value_per_strategy')
def historic_value_per_strategy():
    # Assuming there is a historical value table or logic to calculate it
    return jsonify({"message": "Not implemented yet"})

@app.route('/account_values')
def account_values():
    accounts = session.query(AccountInfo).all()
    accounts_data = {account.broker: account.value for account in accounts}
    return jsonify({"account_values": accounts_data})

@app.route('/trade_success_rate')
def trade_success_rate():
    total_trades = session.query(func.count(Trade.id)).scalar()
    successful_trades = session.query(func.count(Trade.id)).filter(Trade.profit_loss > 0).scalar()
    failed_trades = total_trades - successful_trades
    return jsonify({"total_trades": total_trades, "successful_trades": successful_trades, "failed_trades": failed_trades})

def create_app():
    return app
