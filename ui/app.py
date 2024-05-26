from flask import Flask, jsonify, render_template
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, func
from database.models import Trade, AccountInfo
import os

app = Flask("TradingAPI", template_folder='ui/templates')

DATABASE_URL = "sqlite:///trading.db"
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

@app.route('/')
def index():
    try:
        return render_template('index.html')
    except Exception as e:
        app.logger.error(f"Error rendering index.html: {e}")
        return "Internal Server Error", 500

# Static files are served automatically from the 'static' folder

@app.route('/trades_per_strategy')
def trades_per_strategy():
    trades_count = session.query(Trade.strategy, Trade.brokerage, func.count(Trade.id)).group_by(Trade.strategy, Trade.brokerage).all()
    trades_count_serializable = [{"strategy": strategy, "brokerage": brokerage, "count": count} for strategy, brokerage, count in trades_count]
    return jsonify({"trades_per_strategy": trades_count_serializable})

@app.route('/historic_value_per_strategy')
def historic_value_per_strategy():
    historical_values = session.query(
        Trade.strategy,
        Trade.brokerage,
        func.strftime('%Y-%m-%d %H', Trade.timestamp).label('hour'),
        func.sum(Trade.profit_loss).label('total_profit_loss')
    ).group_by(Trade.strategy, Trade.brokerage, 'hour').all()
    
    historical_values_serializable = [
        {"strategy": strategy, "brokerage": brokerage, "hour": hour, "total_profit_loss": total_profit_loss}
        for strategy, brokerage, hour, total_profit_loss in historical_values
    ]
    return jsonify({"historic_value_per_strategy": historical_values_serializable})

@app.route('/account_values')
def account_values():
    accounts = session.query(AccountInfo).all()
    accounts_data = {account.broker: account.value for account in accounts}
    return jsonify({"account_values": accounts_data})

@app.route('/trade_success_rate')
def trade_success_rate():
    strategies_and_brokers = session.query(Trade.strategy, Trade.brokerage).distinct().all()
    success_rate_by_strategy_and_broker = []

    for strategy, brokerage in strategies_and_brokers:
        total_trades = session.query(func.count(Trade.id)).filter(Trade.strategy == strategy, Trade.brokerage == brokerage).scalar()
        successful_trades = session.query(func.count(Trade.id)).filter(Trade.strategy == strategy, Trade.brokerage == brokerage, Trade.profit_loss > 0).scalar()
        failed_trades = total_trades - successful_trades

        success_rate_by_strategy_and_broker.append({
            "strategy": strategy,
            "brokerage": brokerage,
            "total_trades": total_trades,
            "successful_trades": successful_trades,
            "failed_trades": failed_trades
        })

    return jsonify({"trade_success_rate": success_rate_by_strategy_and_broker})

def create_app():
    return app
