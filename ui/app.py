from flask import Flask, jsonify, render_template, request
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, func
from database.models import Trade, AccountInfo, Balance, Position
from flask_cors import CORS
import os

app = Flask("TradingAPI")
CORS(app, origins=["http://localhost:3000"], supports_credentials=True)

@app.route('/trades_per_strategy')
def trades_per_strategy():
    trades_count = app.session.query(Trade.strategy, Trade.broker, func.count(Trade.id)).group_by(Trade.strategy, Trade.broker).all()
    trades_count_serializable = [{"strategy": strategy, "broker": broker, "count": count} for strategy, broker, count in trades_count]
    return jsonify({"trades_per_strategy": trades_count_serializable})

@app.route('/historic_balance_per_strategy', methods=['GET'])
def historic_balance_per_strategy():
    try:
        historical_balances = app.session.query(
            Balance.strategy,
            Balance.broker,
            func.strftime('%Y-%m-%d %H', Balance.timestamp).label('hour'),
            Balance.total_balance,
        ).group_by(
            Balance.strategy, Balance.broker, 'hour'
        ).order_by(
            Balance.strategy, Balance.broker, 'hour'
        ).all()
        historical_balances_serializable = []
        for strategy, broker, hour, total_balance in historical_balances:
            historical_balances_serializable.append({
                "strategy": strategy,
                "broker": broker,
                "hour": hour,
                "total_balance": total_balance
            })
        return jsonify({"historic_balance_per_strategy": historical_balances_serializable})
    finally:
        app.session.close()

@app.route('/account_values')
def account_values():
    accounts = app.session.query(AccountInfo).all()
    accounts_data = {account.broker: account.value for account in accounts}
    return jsonify({"account_values": accounts_data})

@app.route('/trade_success_rate')
def trade_success_rate():
    strategies_and_brokers = app.session.query(Trade.strategy, Trade.broker).distinct().all()
    success_rate_by_strategy_and_broker = []

    for strategy, broker in strategies_and_brokers:
        total_trades = app.session.query(func.count(Trade.id)).filter(Trade.strategy == strategy, Trade.broker == broker).scalar()
        successful_trades = app.session.query(func.count(Trade.id)).filter(Trade.strategy == strategy, Trade.broker == broker, Trade.profit_loss > 0).scalar()
        failed_trades = total_trades - successful_trades

        success_rate_by_strategy_and_broker.append({
            "strategy": strategy,
            "broker": broker,
            "total_trades": total_trades,
            "successful_trades": successful_trades,
            "failed_trades": failed_trades
        })

    return jsonify({"trade_success_rate": success_rate_by_strategy_and_broker})

@app.route('/positions')
def get_positions():
    brokers = request.args.getlist('brokers[]')
    strategies = request.args.getlist('strategies[]')

    query = app.session.query(Position)

    if brokers:
        query = query.filter(Position.broker.in_(brokers))
    if strategies:
        query = query.filter(Position.strategy.in_(strategies))

    positions = query.all()
    positions_data = []
    for position in positions:
        positions_data.append({
            'broker': position.broker,
            'strategy': position.strategy,
            'symbol': position.symbol,
            'quantity': position.quantity,
            'latest_price': position.latest_price,
            'timestamp': position.last_updated,
        })

    return jsonify({'positions': positions_data})

@app.route('/trades', methods=['GET'])
def get_trades():
    brokers = request.args.getlist('brokers[]')
    strategies = request.args.getlist('strategies[]')

    query = app.session.query(Trade)

    if brokers:
        query = query.filter(Trade.broker.in_(brokers))
    if strategies:
        query = query.filter(Trade.strategy.in_(strategies))

    trades = query.all()
    trades_data = [{
        'id': trade.id,
        'broker': trade.broker,
        'strategy': trade.strategy,
        'symbol': trade.symbol,
        'quantity': trade.quantity,
        'price': trade.price,
        'profit_loss': trade.profit_loss,
        'timestamp': trade.timestamp
    } for trade in trades]

    return jsonify({'trades': trades_data})


@app.route('/trade_stats', methods=['GET'])
def get_trade_stats():
    brokers = request.args.getlist('brokers[]')
    strategies = request.args.getlist('strategies[]')

    query = app.session.query(Trade)

    if brokers:
        query = query.filter(Trade.broker.in_(brokers))
    if strategies:
        query = query.filter(Trade.strategy.in_(strategies))

    trades = query.all()

    if not trades:
        return jsonify({
            'average_profit_loss': 0,
            'win_loss_rate': 0,
            'number_of_trades': 0,
            'trades_per_day': {}
        })

    total_profit_loss = sum(trade.profit_loss for trade in trades)
    number_of_trades = len(trades)
    wins = sum(1 for trade in trades if trade.profit_loss > 0)
    losses = sum(1 for trade in trades if trade.profit_loss <= 0)
    win_loss_rate = wins / number_of_trades if number_of_trades > 0 else 0

    trades_per_day = {}
    for trade in trades:
        day = trade.timestamp.date().isoformat()  # Convert date to string
        if day not in trades_per_day:
            trades_per_day[day] = 0
        trades_per_day[day] += 1

    average_profit_loss = total_profit_loss / number_of_trades

    return jsonify({
        'average_profit_loss': average_profit_loss,
        'win_loss_rate': win_loss_rate,
        'number_of_trades': number_of_trades,
        'trades_per_day': trades_per_day
    })

def create_app(engine):
    Session = sessionmaker(bind=engine)
    app.session = Session()
    return app
