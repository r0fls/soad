from flask import Flask, jsonify, request
from flask_jwt_extended import JWTManager, create_access_token, jwt_required
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, func
from database.models import Trade, AccountInfo, Balance, Position
from flask_cors import CORS
import numpy as np
from scipy.stats import norm
import os
from datetime import timedelta, datetime


app = Flask("TradingAPI")
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "http://localhost:3000")

# Configure CORS
CORS(app, resources={r"/*": {"origins": DASHBOARD_URL}}, supports_credentials=True)

app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'super-secret')  # Change this!
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=12)
jwt = JWTManager(app)

USERNAME = os.environ.get('APP_USERNAME', 'admin')
PASSWORD = os.environ.get('APP_PASSWORD', 'password')

@app.route('/', methods=['GET'])
def ok():
    return jsonify({"status": "ok"}), 200

@app.route('/login', methods=['POST'])
def login():
    if not request.is_json:
        return jsonify({"msg": "Missing JSON in request"}), 400

    username = request.json.get('username', None)
    password = request.json.get('password', None)
    if username != USERNAME or password != PASSWORD:
        return jsonify({"msg": "Bad username or password"}), 401

    access_token = create_access_token(identity=username)
    return jsonify(access_token=access_token), 200

@app.route('/get_brokers_strategies', methods=['GET'])
@jwt_required()
def get_brokers_strategies():
    try:
        # Fetch distinct brokers and strategies from the Balance table
        brokers_strategies = app.session.query(Balance.broker, Balance.strategy).distinct().all()
        response = [{'broker': broker, 'strategy': strategy} for broker, strategy in brokers_strategies]
        return jsonify(response), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/adjust_balance', methods=['POST'])
@jwt_required()
def adjust_balance():
    import pdb; pdb.set_trace()
    data = request.get_json()
    broker = data.get('broker')
    strategy_name = data.get('strategy_name')
    new_total_balance = data.get('new_total_balance')

    if new_total_balance is None or new_total_balance <= 0:
        return jsonify({'status': 'error', 'message': 'Invalid balance amount'}), 400

    try:
        # Fetch the positions balance for the strategy
        positions_balance_record = app.session.query(Balance).filter_by(
            strategy=strategy_name, broker=broker, type='positions'
        ).first()

        if not positions_balance_record:
            # Calculate positions balance if not found
            positions = app.session.query(Position).filter_by(
                strategy=strategy_name, broker=broker
            ).all()
            positions_balance = sum(p.quantity * p.latest_price for p in positions)
        else:
            positions_balance = positions_balance_record.balance

        # Calculate the current total balance and the adjustment
        cash_balance_record = app.session.query(Balance).filter_by(
            strategy=strategy_name, broker=broker, type='cash'
        ).order_by(Balance.timestamp.desc()).first()

        if cash_balance_record:
            current_total_balance = cash_balance_record.balance + positions_balance
        else:
            current_total_balance = positions_balance

        adjustment = new_total_balance - current_total_balance
        new_cash_balance = (cash_balance_record.balance if cash_balance_record else 0) + adjustment

        # Create a new cash balance record
        new_cash_balance_record = Balance(
            strategy=strategy_name,
            broker=broker,
            type='cash',
            balance=new_cash_balance,
            timestamp=datetime.utcnow()  # Assuming timestamp is a field in Balance
        )
        app.session.add(new_cash_balance_record)
        app.session.commit()

        return jsonify({'status': 'success', 'new_cash_balance': new_cash_balance}), 200
    except Exception as e:
        app.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/trades_per_strategy')
@jwt_required()
def trades_per_strategy():
    trades_count = app.session.query(Trade.strategy, Trade.broker, func.count(Trade.id)).group_by(Trade.strategy, Trade.broker).all()
    trades_count_serializable = [{"strategy": strategy, "broker": broker, "count": count} for strategy, broker, count in trades_count]
    return jsonify({"trades_per_strategy": trades_count_serializable})

@app.route('/historic_balance_per_strategy', methods=['GET'])
@jwt_required()
def historic_balance_per_strategy():
    try:
        if app.session.bind.dialect.name == 'postgresql':
            hour_expr = func.to_char(Balance.timestamp, 'YYYY-MM-DD HH24').label('hour')
        elif app.session.bind.dialect.name == 'sqlite':
            hour_expr = func.strftime('%Y-%m-%d %H', Balance.timestamp).label('hour')

        historical_balances = app.session.query(
            Balance.strategy,
            Balance.broker,
            hour_expr,
            func.sum(Balance.balance).label('balance')
        ).group_by(
            Balance.strategy,
            Balance.broker,
            hour_expr
        ).order_by(
            Balance.strategy,
            Balance.broker,
            hour_expr
        ).all()

        historical_balances_serializable = []
        for strategy, broker, hour, balance in historical_balances:
            historical_balances_serializable.append({
                "strategy": strategy,
                "broker": broker,
                "hour": hour,
                "balance": balance
            })
        return jsonify({"historic_balance_per_strategy": historical_balances_serializable})
    finally:
        app.session.close()

@app.route('/account_values')
@jwt_required()
def account_values():
    accounts = app.session.query(AccountInfo).all()
    accounts_data = {account.broker: account.value for account in accounts}
    return jsonify({"account_values": accounts_data})

@app.route('/trade_success_rate')
@jwt_required()
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
@jwt_required()
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
        # TODO: prune these
        if position.quantity != 0:
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
@jwt_required()
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
        'order_type': trade.order_type,
        'price': trade.price,
        'profit_loss': trade.profit_loss,
        'timestamp': trade.timestamp
    } for trade in trades]

    return jsonify({'trades': trades_data})


@app.route('/trade_stats', methods=['GET'])
@jwt_required()
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

@app.route('/var', methods=['GET'])
@jwt_required()
def get_var():
    brokers = request.args.getlist('brokers[]')
    strategies = request.args.getlist('strategies[]')

    query = app.session.query(Trade)

    if brokers:
        query = query.filter(Trade.broker.in_(brokers))
    if strategies:
        query = query.filter(Trade.strategy.in_(strategies))

    trades = query.all()

    if not trades:
        return jsonify({'var': 0})

    returns = [trade.profit_loss for trade in trades]
    mean_return = np.mean(returns)
    std_dev_return = np.std(returns)
    var_95 = norm.ppf(0.05, mean_return, std_dev_return)

    return jsonify({'var': var_95})

@app.route('/max_drawdown', methods=['GET'])
@jwt_required()
def get_max_drawdown():
    brokers = request.args.getlist('brokers[]')
    strategies = request.args.getlist('strategies[]')

    query = app.session.query(Trade)

    if brokers:
        query = query.filter(Trade.broker.in_(brokers))
    if strategies:
        query = query.filter(Trade.strategy.in_(strategies))

    trades = query.all()

    if not trades:
        return jsonify({'max_drawdown': 0})

    cum_returns = np.cumsum([trade.profit_loss for trade in trades])
    running_max = np.maximum.accumulate(cum_returns)
    drawdowns = (running_max - cum_returns) / running_max
    max_drawdown = np.max(drawdowns)

    return jsonify({'max_drawdown': max_drawdown})

@app.route('/sharpe_ratio', methods=['GET'])
@jwt_required()
def get_sharpe_ratio():
    brokers = request.args.getlist('brokers[]')
    strategies = request.args.getlist('strategies[]')

    query = app.session.query(Trade)

    if brokers:
        query = query.filter(Trade.broker.in_(brokers))
    if strategies:
        query = query.filter(Trade.strategy.in_(strategies))

    trades = query.all()

    if not trades:
        return jsonify({'sharpe_ratio': 0})

    returns = [trade.profit_loss for trade in trades]
    mean_return = np.mean(returns)
    std_dev_return = np.std(returns)
    sharpe_ratio = mean_return / std_dev_return if std_dev_return != 0 else 0

    return jsonify({'sharpe_ratio': sharpe_ratio})

def create_app(engine):
    Session = sessionmaker(bind=engine)
    app.session = Session()
    return app
