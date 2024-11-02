from flask import Flask, jsonify, request
from flask_jwt_extended import JWTManager, create_access_token, jwt_required
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy import func, text
from database.models import Trade, AccountInfo, Balance, Position
from flask_cors import CORS
import numpy as np
from scipy.stats import norm
import os
from datetime import timedelta, datetime, UTC
from utils.utils import is_option, black_scholes_delta_theta, extract_option_details, OPTION_MULTIPLIER, is_futures_symbol, futures_contract_size
from utils.logger import logger


app = Flask("TradingAPI")
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "http://localhost:3000")

# Configure CORS
CORS(app, resources={r"/*": {"origins": DASHBOARD_URL}},
     supports_credentials=True)

app.config['JWT_SECRET_KEY'] = os.environ.get(
    'JWT_SECRET_KEY', 'super-secret')  # Change this!
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=12)
jwt = JWTManager(app)

USERNAME = os.environ.get('APP_USERNAME', 'emperor')
PASSWORD = os.environ.get('APP_PASSWORD', 'fugazi')


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


@app.route('/account_values')
@jwt_required()
def account_values():
    try:
        accounts = app.session.query(AccountInfo).all()
        accounts_data = {account.broker: account.value for account in accounts}
        return jsonify({"account_values": accounts_data})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        app.session.remove()


@app.route('/get_brokers_strategies', methods=['GET'])
@jwt_required()
def get_brokers_strategies():
    try:
        # Subquery to get the latest cash balance record for each broker and strategy
        cash_subquery = app.session.query(
            Balance.broker,
            Balance.strategy,
            func.max(Balance.timestamp).label('latest_cash_timestamp')
        ).filter_by(type='cash').group_by(Balance.broker, Balance.strategy).subquery()

        # Fetch the latest cash balances
        latest_cash_balances = app.session.query(
            Balance.broker,
            Balance.strategy,
            Balance.balance
        ).join(
            cash_subquery,
            (Balance.broker == cash_subquery.c.broker) &
            (Balance.strategy == cash_subquery.c.strategy) &
            (Balance.timestamp == cash_subquery.c.latest_cash_timestamp)
        ).filter(Balance.type == 'cash').all()

        # Create a dictionary to store the results
        broker_strategy_balances = {}
        for broker, strategy, cash_balance in latest_cash_balances:
            broker_strategy_balances[(broker, strategy)] = {
                'cash_balance': cash_balance,
                'positions_balance': 0
            }

        # Fetch the latest positions balance record for each broker and strategy
        positions_subquery = app.session.query(
            Balance.broker,
            Balance.strategy,
            func.max(Balance.timestamp).label('latest_positions_timestamp')
        ).filter_by(type='positions').group_by(Balance.broker, Balance.strategy).subquery()

        latest_positions_balances = app.session.query(
            Balance.broker,
            Balance.strategy,
            Balance.balance
        ).join(
            positions_subquery,
            (Balance.broker == positions_subquery.c.broker) &
            (Balance.strategy == positions_subquery.c.strategy) &
            (Balance.timestamp == positions_subquery.c.latest_positions_timestamp)
        ).filter(Balance.type == 'positions').all()

        # Update the dictionary with the positions balances
        for broker, strategy, positions_balance in latest_positions_balances:
            if (broker, strategy) in broker_strategy_balances:
                broker_strategy_balances[(
                    broker, strategy)]['positions_balance'] = positions_balance
            else:
                broker_strategy_balances[(broker, strategy)] = {
                    'cash_balance': 0,
                    'positions_balance': positions_balance
                }

        # Calculate total balance for each broker and strategy
        for (broker, strategy), balances in broker_strategy_balances.items():
            if balances['positions_balance'] == 0:
                positions = app.session.query(Position).filter_by(
                    strategy=strategy, broker=broker
                ).all()
                positions_balance = sum(
                    p.quantity * p.latest_price for p in positions)
                balances['positions_balance'] = positions_balance

            balances['total_balance'] = balances['cash_balance'] + \
                balances['positions_balance']

        # Prepare the response
        response = [
            {
                'broker': broker,
                'strategy': strategy,
                'total_balance': balances['total_balance']
            }
            for (broker, strategy), balances in broker_strategy_balances.items()
        ]

        return jsonify(response), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        app.session.remove()


@app.route('/delete_strategy', methods=['POST'])
@jwt_required()
def delete_strategy():
    data = request.get_json()
    broker = data.get('broker')
    strategy_name = data.get('strategy_name')

    try:
        # Check for open positions for the specified strategy and broker
        open_positions = app.session.query(Position).filter_by(
            strategy=strategy_name, broker=broker
        ).all()

        if open_positions:
            # if there are open positions, switch them to be uncategorized
            for position in open_positions:
                position.strategy = 'uncategorized'
                app.session.add(position)
            app.session.commit()

        # Delete all balance records associated with the specified strategy and broker
        delete_count = app.session.query(Balance).filter_by(
            strategy=strategy_name, broker=broker
        ).delete(synchronize_session=False)
        # Commit the transaction
        app.session.commit()
        logger.info(f"Deleted {delete_count} balance records for strategy {strategy_name}")

        return jsonify({'status': 'success', 'message': f'Strategy {strategy_name} deleted successfully'}), 200

    except Exception as e:
        app.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

    finally:
        app.session.remove()


@app.route('/adjust_balance', methods=['POST'])
@jwt_required()
def adjust_balance():
    data = request.get_json()
    broker = data.get('broker')
    strategy_name = data.get('strategy_name')
    new_total_balance = data.get('new_total_balance')
    now = datetime.now(UTC)

    if new_total_balance is None or new_total_balance <= 0:
        return jsonify({'status': 'error', 'message': 'Invalid balance amount'}), 400

    try:
        # Fetch the latest positions balance for the strategy
        positions_balance_record = app.session.query(Balance).filter_by(
            strategy=strategy_name, broker=broker, type='positions'
        ).order_by(Balance.timestamp.desc()).first()

        if not positions_balance_record:
            positions_balance = 0
            # Calculate positions balance if not found
            positions = app.session.query(Position).filter_by(
                strategy=strategy_name, broker=broker
            ).all()
            for position in positions:
                if is_option(position.symbol):
                    balance_contribution = position.quantity * \
                        position.latest_price * OPTION_MULTIPLIER
                elif is_futures_symbol(position.symbol):
                    contract_size = futures_contract_size(position.symbol)
                    balance_contribution = position.quantity * position.latest_price * contract_size
                else:
                    balance_contribution = position.quantity * position.latest_price
                positions_balance += balance_contribution
        else:
            positions_balance = positions_balance_record.balance
        # Create an updated positions balance record
        new_positions_balance_record = Balance(
            strategy=strategy_name,
            broker=broker,
            type='positions',
            balance=positions_balance,
            timestamp=now
        )

        # Calculate the current total balance and the adjustment
        cash_balance_record = app.session.query(Balance).filter_by(
            strategy=strategy_name, broker=broker, type='cash'
        ).order_by(Balance.timestamp.desc()).first()

        if cash_balance_record:
            current_total_balance = cash_balance_record.balance + positions_balance
        else:
            current_total_balance = positions_balance

        adjustment = new_total_balance - current_total_balance
        new_cash_balance = (
            cash_balance_record.balance if cash_balance_record else 0) + adjustment

        # Create a new cash balance record
        new_cash_balance_record = Balance(
            strategy=strategy_name,
            broker=broker,
            type='cash',
            balance=new_cash_balance,
            timestamp=now
        )
        # Subtract from the uncatagorized cash balance for this broker
        uncatagorized_cash_balance_record = app.session.query(Balance).filter_by(
            strategy='uncategorized', broker=broker, type='cash'
        ).order_by(Balance.timestamp.desc()).first()
        if uncatagorized_cash_balance_record:
            uncatagorized_cash_balance_record.balance -= adjustment
        else:
            uncatagorized_cash_balance_record = Balance(
                strategy='uncategorized',
                broker=broker,
                type='uncatagorized_cash',
                balance=-adjustment,
                timestamp=now
            )

        app.session.add(uncatagorized_cash_balance_record)
        app.session.add(new_cash_balance_record)
        app.session.commit()

        return jsonify({'status': 'success', 'new_cash_balance': new_cash_balance}), 200
    except Exception as e:
        app.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        app.session.remove()


@app.route('/trades_per_strategy')
@jwt_required()
def trades_per_strategy(methods=['GET']):
    try:
        trades_count = app.session.query(Trade.strategy, Trade.broker, func.count(
            Trade.id)).group_by(Trade.strategy, Trade.broker).all()
        trades_count_serializable = [{"strategy": strategy, "broker": broker,
                                      "count": count} for strategy, broker, count in trades_count]
        return jsonify({"trades_per_strategy": trades_count_serializable})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        app.session.remove()


@app.route('/historic_balance_per_strategy')
@jwt_required()
def historic_balance_per_strategy(methods=['GET']):
    try:
        if app.session.bind.dialect.name == 'postgresql':
            query = """
            WITH one_week_ago AS (
                SELECT NOW() - INTERVAL '7 days' AS ts
            ),
            latest_cash_subquery AS (
                SELECT
                    broker,
                    strategy,
                    to_char(timestamp, 'YYYY-MM-DD HH24:MI') AS interval,
                    MAX(timestamp) AS latest_cash_timestamp
                FROM balances
                WHERE type = 'cash' AND timestamp >= (SELECT ts FROM one_week_ago)
                GROUP BY broker, strategy, to_char(timestamp, 'YYYY-MM-DD HH24:MI')
            ),
            latest_positions_subquery AS (
                SELECT
                    broker,
                    strategy,
                    to_char(timestamp, 'YYYY-MM-DD HH24:MI') AS interval,
                    MAX(timestamp) AS latest_positions_timestamp
                FROM balances
                WHERE type = 'positions' AND timestamp >= (SELECT ts FROM one_week_ago)
                GROUP BY broker, strategy, to_char(timestamp, 'YYYY-MM-DD HH24:MI')
            ),
            latest_cash_balances AS (
                SELECT
                    b.broker,
                    b.strategy,
                    to_char(b.timestamp, 'YYYY-MM-DD HH24:MI') AS interval,
                    b.balance AS cash_balance
                FROM balances b
                JOIN latest_cash_subquery lcs
                    ON b.broker = lcs.broker
                    AND b.strategy = lcs.strategy
                    AND b.timestamp = lcs.latest_cash_timestamp
                WHERE b.type = 'cash'
            ),
            latest_positions_balances AS (
                SELECT
                    b.broker,
                    b.strategy,
                    to_char(b.timestamp, 'YYYY-MM-DD HH24:MI') AS interval,
                    b.balance AS positions_balance
                FROM balances b
                JOIN latest_positions_subquery lps
                    ON b.broker = lps.broker
                    AND b.strategy = lps.strategy
                    AND b.timestamp = lps.latest_positions_timestamp
                WHERE b.type = 'positions'
            )
            SELECT
                lcb.broker,
                lcb.strategy,
                lcb.interval,
                COALESCE(lcb.cash_balance, 0) AS cash_balance,
                COALESCE(lpb.positions_balance, 0) AS positions_balance,
                (COALESCE(lcb.cash_balance, 0) + COALESCE(lpb.positions_balance, 0)) AS total_balance
            FROM latest_cash_balances lcb
            FULL OUTER JOIN latest_positions_balances lpb
                ON lcb.broker = lpb.broker
                AND lcb.strategy = lpb.strategy
                AND lcb.interval = lpb.interval;
            """
        elif app.session.bind.dialect.name == 'sqlite':
            query = """
            WITH one_week_ago AS (
                SELECT datetime('now', '-7 days') AS ts
            ),
            latest_cash_subquery AS (
                SELECT
                    broker,
                    strategy,
                    strftime('%Y-%m-%d %H:%M', timestamp) AS interval,
                    MAX(timestamp) AS latest_cash_timestamp
                FROM balances
                WHERE type = 'cash' AND timestamp >= (SELECT ts FROM one_week_ago)
                GROUP BY broker, strategy, strftime('%Y-%m-%d %H:%M', timestamp)
            ),
            latest_positions_subquery AS (
                SELECT
                    broker,
                    strategy,
                    strftime('%Y-%m-%d %H:%M', timestamp) AS interval,
                    MAX(timestamp) AS latest_positions_timestamp
                FROM balances
                WHERE type = 'positions' AND timestamp >= (SELECT ts FROM one_week_ago)
                GROUP BY broker, strategy, strftime('%Y-%m-%d %H:%M', timestamp)
            ),
            latest_cash_balances AS (
                SELECT
                    b.broker,
                    b.strategy,
                    strftime('%Y-%m-%d %H:%M', b.timestamp) AS interval,
                    b.balance AS cash_balance
                FROM balances b
                JOIN latest_cash_subquery lcs
                    ON b.broker = lcs.broker
                    AND b.strategy = lcs.strategy
                    AND b.timestamp = lcs.latest_cash_timestamp
                WHERE b.type = 'cash'
            ),
            latest_positions_balances AS (
                SELECT
                    b.broker,
                    b.strategy,
                    strftime('%Y-%m-%d %H:%M', b.timestamp) AS interval,
                    b.balance AS positions_balance
                FROM balances b
                JOIN latest_positions_subquery lps
                    ON b.broker = lps.broker
                    AND b.strategy = lps.strategy
                    AND b.timestamp = lps.latest_positions_timestamp
                WHERE b.type = 'positions'
            )
            SELECT
                lcb.broker,
                lcb.strategy,
                lcb.interval,
                COALESCE(lcb.cash_balance, 0) AS cash_balance,
                COALESCE(lpb.positions_balance, 0) AS positions_balance,
                (COALESCE(lcb.cash_balance, 0) + COALESCE(lpb.positions_balance, 0)) AS total_balance
            FROM latest_cash_balances lcb
            LEFT JOIN latest_positions_balances lpb
                ON lcb.broker = lpb.broker
                AND lcb.strategy = lpb.strategy
                AND lcb.interval = lpb.interval
            UNION
            SELECT
                lpb.broker,
                lpb.strategy,
                lpb.interval,
                COALESCE(lcb.cash_balance, 0) AS cash_balance,
                COALESCE(lpb.positions_balance, 0) AS positions_balance,
                (COALESCE(lcb.cash_balance, 0) + COALESCE(lpb.positions_balance, 0)) AS total_balance
            FROM latest_positions_balances lpb
            LEFT JOIN latest_cash_balances lcb
                ON lpb.broker = lcb.broker
                AND lpb.strategy = lcb.strategy
                AND lpb.interval = lcb.interval;
            """
        else:
            return jsonify({'status': 'error', 'message': 'Unsupported database type'}), 500

        result = app.session.execute(text(query))
        combined_balances = result.fetchall()

        # Prepare the response
        historical_balances_serializable = []
        for row in combined_balances:
            broker, strategy, interval, cash_balance, positions_balance, total_balance = row
            historical_balances_serializable.append({
                "strategy": strategy,
                "broker": broker,
                "interval": interval,
                "cash_balance": round(cash_balance, 2),
                "positions_balance": round(positions_balance, 2),
                "total_balance": round(total_balance, 2)
            })

        return jsonify({"historic_balance_per_strategy": historical_balances_serializable})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        app.session.remove()


@app.route('/trade_success_rate')
@jwt_required()
def trade_success_rate():
    try:
        strategies_and_brokers = app.session.query(
            Trade.strategy, Trade.broker).distinct().all()
        success_rate_by_strategy_and_broker = []

        for strategy, broker in strategies_and_brokers:
            total_trades = app.session.query(func.count(Trade.id)).filter(
                Trade.strategy == strategy, Trade.broker == broker).scalar()
            successful_trades = app.session.query(func.count(Trade.id)).filter(
                Trade.strategy == strategy, Trade.broker == broker, Trade.profit_loss > 0).scalar()
            failed_trades = total_trades - successful_trades

            success_rate_by_strategy_and_broker.append({
                "strategy": strategy,
                "broker": broker,
                "total_trades": total_trades,
                "successful_trades": successful_trades,
                "failed_trades": failed_trades
            })

        return jsonify({"trade_success_rate": success_rate_by_strategy_and_broker})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        app.session.remove()


@app.route('/positions')
@jwt_required()
def get_positions():
    try:
        # Fetch positions
        positions = app.session.query(Position).all()
        positions_data = []
        total_delta = 0
        total_theta = 0
        total_stocks_value = 0
        total_options_value = 0

        # Calculate positions values and total delta/theta
        for position in positions:
            delta, theta = (0, 0)
            if is_option(position.symbol):
                delta, theta = black_scholes_delta_theta(position)
                if delta is not None and theta is not None:
                    delta *= position.quantity * OPTION_MULTIPLIER
                    theta *= position.quantity * OPTION_MULTIPLIER
                total_options_value += position.quantity * \
                    position.latest_price * OPTION_MULTIPLIER
            else:
                delta = position.quantity
                theta = 0
                total_stocks_value += position.quantity * position.latest_price
            total_delta += delta
            total_theta += theta

            positions_data.append({
                'broker': position.broker,
                'strategy': position.strategy,
                'symbol': position.symbol,
                'quantity': position.quantity,
                'latest_price': position.latest_price,
                'cost_basis': position.cost_basis,
                'timestamp': position.last_updated,
                'delta': delta,
                'theta': theta,
                'is_option': is_option(position.symbol)
            })

        # Fetch latest cash balance per strategy and broker
        cash_subquery = app.session.query(
            Balance.broker,
            Balance.strategy,
            func.max(Balance.timestamp).label('latest_cash_timestamp')
        ).filter_by(type='cash').group_by(Balance.broker, Balance.strategy).subquery()

        latest_cash_balances = app.session.query(
            Balance.broker,
            Balance.strategy,
            Balance.balance
        ).join(
            cash_subquery,
            (Balance.broker == cash_subquery.c.broker) &
            (Balance.strategy == cash_subquery.c.strategy) &
            (Balance.timestamp == cash_subquery.c.latest_cash_timestamp)
        ).filter(Balance.type == 'cash').all()

        cash_balances = {f"{balance.broker}_{balance.strategy}": round(
            balance.balance, 2) for balance in latest_cash_balances}

        return jsonify({
            'positions': positions_data,
            'total_delta': total_delta,
            'total_theta': total_theta,
            'total_stocks_value': round(total_stocks_value, 2),
            'total_options_value': round(total_options_value, 2),
            'cash_balances': cash_balances
        })
    except Exception as e:
        logger.error(f'Error fetching positions: {str(e)}')
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        app.session.remove()


@app.route('/trades', methods=['GET'])
@jwt_required()
def get_trades():
    try:
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
            'side': trade.side,
            'price': trade.price,
            'profit_loss': trade.profit_loss,
            'timestamp': trade.timestamp
        } for trade in trades]

        return jsonify({'trades': trades_data})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        app.session.remove()


@app.route('/trade_stats', methods=['GET'])
@jwt_required()
def get_trade_stats():
    try:
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
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        app.session.remove()


@app.route('/var', methods=['GET'])
@jwt_required()
def get_var():
    try:
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
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        app.session.remove()


@app.route('/max_drawdown', methods=['GET'])
@jwt_required()
def get_max_drawdown():
    try:
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
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        app.session.remove()


@app.route('/sharpe_ratio', methods=['GET'])
@jwt_required()
def get_sharpe_ratio():
    try:
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
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        app.session.remove()


def create_app(engine):
    Session = sessionmaker(bind=engine)
    app.session = scoped_session(Session)
    return app
