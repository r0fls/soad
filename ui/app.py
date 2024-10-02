from functools import wraps
from sanic import Sanic, json
from sqlalchemy.ext.asyncio import create_async_engine
import jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker, scoped_session
from sanic_cors import CORS
from database.models import Trade, AccountInfo, Balance, Position
from sqlalchemy import func, text
import os
from datetime import timedelta, datetime, timezone
import numpy as np
from scipy.stats import norm
from utils.utils import is_option, black_scholes_delta_theta, OPTION_MULTIPLIER, is_futures_symbol, futures_contract_size
from utils.logger import logger


# Create Sanic app
app = Sanic("TradingAPI")
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "http://localhost:3000")

# Configure CORS
CORS(app, resources={r"/*": {"origins": DASHBOARD_URL}}, supports_credentials=True)

# Define secret key and token expiration
JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'super-secret')
JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=12)

# Define username and password for login
USERNAME = os.environ.get('APP_USERNAME', 'emperor')
PASSWORD = os.environ.get('APP_PASSWORD', 'fugazi')

# Helper function to create a JWT token
def create_access_token(identity):
    payload = {
        'identity': identity,
        'exp': datetime.utcnow() + JWT_ACCESS_TOKEN_EXPIRES,
        'iat': datetime.utcnow()
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm='HS256')

# Middleware to check for token and decode it
def check_auth_token(request):
    auth_header = request.headers.get('Authorization', None)
    if not auth_header:
        raise Unauthorized("Missing Authorization Header")

    try:
        token_type, token = auth_header.split()
        if token_type.lower() != 'bearer':
            raise Unauthorized("Invalid Token Type")
        decoded_token = jwt.decode(token, JWT_SECRET_KEY, algorithms=['HS256'])
        return decoded_token
    except Exception as e:
        raise Unauthorized(f"Invalid Token: {str(e)}")

# Decorator for routes requiring authentication
def jwt_required(f):
    @wraps(f)
    async def decorated_function(request, *args, **kwargs):
        request.ctx.user = check_auth_token(request)
        return await f(request, *args, **kwargs)
    return decorated_function

@app.route("/", methods=["GET"])
async def ok(request):
    return json({"status": "ok"}, status=200)

@app.route("/login", methods=["POST"])
async def login(request):
    if not request.json:
        return json({"msg": "Missing JSON in request"}, status=400)

    username = request.json.get('username', None)
    password = request.json.get('password', None)

    if username != USERNAME or password != PASSWORD:
        return json({"msg": "Bad username or password"}, status=401)

    # Generate JWT token
    access_token = create_access_token(identity=username)
    return json({"access_token": access_token}, status=200)

@jwt_required
@app.route('/account_values')
async def account_values(request):
    try:
        async with app.ctx.session() as session:
            result = await session.execute(select(AccountInfo))
            accounts = result.scalars().all()
            accounts_data = {account.broker: account.value for account in accounts}
        return json({"account_values": accounts_data})
    except Exception as e:
        return json({'status': 'error', 'message': str(e)}, status=500)

@jwt_required
@app.route('/get_brokers_strategies', methods=['GET'])
async def get_brokers_strategies(request):
    try:
        async with app.ctx.session() as session:
            cash_subquery = select(
                Balance.broker,
                Balance.strategy,
                func.max(Balance.timestamp).label('latest_cash_timestamp')
            ).filter_by(type='cash').group_by(Balance.broker, Balance.strategy).subquery()

            latest_cash_balances = await session.execute(
                select(Balance.broker, Balance.strategy, Balance.balance)
                .join(
                    cash_subquery,
                    (Balance.broker == cash_subquery.c.broker) &
                    (Balance.strategy == cash_subquery.c.strategy) &
                    (Balance.timestamp == cash_subquery.c.latest_cash_timestamp)
                ).filter(Balance.type == 'cash')
            )
            latest_cash_balances = latest_cash_balances.all()

            positions_subquery = select(
                Balance.broker,
                Balance.strategy,
                func.max(Balance.timestamp).label('latest_positions_timestamp')
            ).filter_by(type='positions').group_by(Balance.broker, Balance.strategy).subquery()

            latest_positions_balances = await session.execute(
                select(Balance.broker, Balance.strategy, Balance.balance)
                .join(
                    positions_subquery,
                    (Balance.broker == positions_subquery.c.broker) &
                    (Balance.strategy == positions_subquery.c.strategy) &
                    (Balance.timestamp == positions_subquery.c.latest_positions_timestamp)
                ).filter(Balance.type == 'positions')
            )
            latest_positions_balances = latest_positions_balances.all()

        broker_strategy_balances = {}
        for broker, strategy, cash_balance in latest_cash_balances:
            broker_strategy_balances[(broker, strategy)] = {
                'cash_balance': cash_balance,
                'positions_balance': 0
            }
        for broker, strategy, positions_balance in latest_positions_balances:
            if (broker, strategy) in broker_strategy_balances:
                broker_strategy_balances[(broker, strategy)]['positions_balance'] = positions_balance
            else:
                broker_strategy_balances[(broker, strategy)] = {
                    'cash_balance': 0,
                    'positions_balance': positions_balance
                }

        for (broker, strategy), balances in broker_strategy_balances.items():
            balances['total_balance'] = balances['cash_balance'] + balances['positions_balance']

        response = [
            {
                'broker': broker,
                'strategy': strategy,
                'total_balance': balances['total_balance']
            }
            for (broker, strategy), balances in broker_strategy_balances.items()
        ]

        return json(response, status=200)
    except Exception as e:
        return json({'status': 'error', 'message': str(e)}, status=500)

@jwt_required
@app.route('/adjust_balance', methods=['POST'])
async def adjust_balance(request):
    data = request.json
    broker = data.get('broker')
    strategy_name = data.get('strategy_name')
    new_total_balance = data.get('new_total_balance')
    now = datetime.now(timezone.utc)

    if new_total_balance is None or new_total_balance <= 0:
        return json({'status': 'error', 'message': 'Invalid balance amount'}, status=400)

    try:
        async with app.ctx.session() as session:
            positions_balance_record = await session.execute(
                select(Balance).filter_by(strategy=strategy_name, broker=broker, type='positions')
                .order_by(Balance.timestamp.desc())
            )
            positions_balance_record = positions_balance_record.scalar()

            if not positions_balance_record:
                positions_balance = 0
                positions = await session.execute(
                    select(Position).filter_by(strategy=strategy_name, broker=broker)
                )
                positions_balance = sum(
                    p.quantity * p.latest_price * (OPTION_MULTIPLIER if is_option(p.symbol) else futures_contract_size(p.symbol) if is_futures_symbol(p.symbol) else 1)
                    for p in positions.scalars()
                )
            else:
                positions_balance = positions_balance_record.balance

            new_positions_balance_record = Balance(
                strategy=strategy_name,
                broker=broker,
                type='positions',
                balance=positions_balance,
                timestamp=now
            )
            session.add(new_positions_balance_record)

            cash_balance_record = await session.execute(
                select(Balance).filter_by(strategy=strategy_name, broker=broker, type='cash')
                .order_by(Balance.timestamp.desc())
            )
            cash_balance_record = cash_balance_record.scalar()

            if cash_balance_record:
                current_total_balance = cash_balance_record.balance + positions_balance
            else:
                current_total_balance = positions_balance

            adjustment = new_total_balance - current_total_balance
            new_cash_balance = (cash_balance_record.balance if cash_balance_record else 0) + adjustment

            new_cash_balance_record = Balance(
                strategy=strategy_name,
                broker=broker,
                type='cash',
                balance=new_cash_balance,
                timestamp=now
            )
            session.add(new_cash_balance_record)

            uncatagorized_cash_balance_record = await session.execute(
                select(Balance).filter_by(strategy='uncategorized', broker=broker, type='cash')
                .order_by(Balance.timestamp.desc())
            )
            uncatagorized_cash_balance_record = uncatagorized_cash_balance_record.scalar()

            if uncatagorized_cash_balance_record:
                uncatagorized_cash_balance_record.balance -= adjustment
            else:
                uncatagorized_cash_balance_record = Balance(
                    strategy='uncategorized',
                    broker=broker,
                    type='cash',
                    balance=-adjustment,
                    timestamp=now
                )
            session.add(uncatagorized_cash_balance_record)
            await session.commit()

        return json({'status': 'success', 'new_cash_balance': new_cash_balance}, status=200)
    except Exception as e:
        return json({'status': 'error', 'message': str(e)}, status=500)

@jwt_required
@app.route('/trades_per_strategy', methods=['GET'])
async def trades_per_strategy(request):
    try:
        async with app.ctx.session() as session:
            trades_count = await session.execute(
                select(Trade.strategy, Trade.broker, func.count(Trade.id)).group_by(Trade.strategy, Trade.broker)
            )
            trades_count_serializable = [
                {"strategy": strategy, "broker": broker, "count": count}
                for strategy, broker, count in trades_count.fetchall()
            ]
        return json({"trades_per_strategy": trades_count_serializable})
    except Exception as e:
        return json({'status': 'error', 'message': str(e)}, status=500)

@jwt_required
@app.route('/historic_balance_per_strategy', methods=['GET'])
async def historic_balance_per_strategy(request):
    try:
        query = """
        WITH one_week_ago AS (SELECT NOW() - INTERVAL '7 days' AS ts),
        latest_cash_subquery AS (SELECT broker, strategy, to_char(timestamp, 'YYYY-MM-DD HH24:MI') AS interval, MAX(timestamp) AS latest_cash_timestamp
        FROM balances WHERE type = 'cash' AND timestamp >= (SELECT ts FROM one_week_ago) GROUP BY broker, strategy, to_char(timestamp, 'YYYY-MM-DD HH24:MI')),
        latest_positions_subquery AS (SELECT broker, strategy, to_char(timestamp, 'YYYY-MM-DD HH24:MI') AS interval, MAX(timestamp) AS latest_positions_timestamp
        FROM balances WHERE type = 'positions' AND timestamp >= (SELECT ts FROM one_week_ago) GROUP BY broker, strategy, to_char(timestamp, 'YYYY-MM-DD HH24:MI')),
        latest_cash_balances AS (SELECT b.broker, b.strategy, to_char(b.timestamp, 'YYYY-MM-DD HH24:MI') AS interval, b.balance AS cash_balance FROM balances b
        JOIN latest_cash_subquery lcs ON b.broker = lcs.broker AND b.strategy = lcs.strategy AND b.timestamp = lcs.latest_cash_timestamp WHERE b.type = 'cash'),
        latest_positions_balances AS (SELECT b.broker, b.strategy, to_char(b.timestamp, 'YYYY-MM-DD HH24:MI') AS interval, b.balance AS positions_balance
        FROM balances b JOIN latest_positions_subquery lps ON b.broker = lps.broker AND b.strategy = lps.strategy AND b.timestamp = lps.latest_positions_timestamp WHERE b.type = 'positions')
        SELECT lcb.broker, lcb.strategy, lcb.interval, COALESCE(lcb.cash_balance, 0) AS cash_balance, COALESCE(lpb.positions_balance, 0) AS positions_balance,
        (COALESCE(lcb.cash_balance, 0) + COALESCE(lpb.positions_balance, 0)) AS total_balance FROM latest_cash_balances lcb FULL OUTER JOIN latest_positions_balances lpb
        ON lcb.broker = lpb.broker AND lcb.strategy = lpb.strategy AND lcb.interval = lpb.interval;
        """
        async with app.ctx.session() as session:
            result = await session.execute(text(query))
            combined_balances = result.fetchall()

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

        return json({"historic_balance_per_strategy": historical_balances_serializable})
    except Exception as e:
        logger.error(f'Error fetching historic balance per strategy: {str(e)}')
        return json({'status': 'error', 'message': str(e)}, status=500)

@jwt_required
@app.route('/trade_success_rate', methods=['GET'])
async def trade_success_rate(request):
    try:
        async with app.ctx.session() as session:
            strategies_and_brokers = await session.execute(select(Trade.strategy, Trade.broker).distinct())
            strategies_and_brokers = strategies_and_brokers.fetchall()

            success_rate_by_strategy_and_broker = []
            for strategy, broker in strategies_and_brokers:
                total_trades = await session.execute(
                    select(func.count(Trade.id)).filter(Trade.strategy == strategy, Trade.broker == broker)
                )
                total_trades = total_trades.scalar()
                successful_trades = await session.execute(
                    select(func.count(Trade.id)).filter(Trade.strategy == strategy, Trade.broker == broker, Trade.profit_loss > 0)
                )
                successful_trades = successful_trades.scalar()
                failed_trades = total_trades - successful_trades

                success_rate_by_strategy_and_broker.append({
                    "strategy": strategy,
                    "broker": broker,
                    "total_trades": total_trades,
                    "successful_trades": successful_trades,
                    "failed_trades": failed_trades
                })

        return json({"trade_success_rate": success_rate_by_strategy_and_broker})
    except Exception as e:
        return json({'status': 'error', 'message': str(e)}, status=500)

@jwt_required
@app.route('/positions', methods=['GET'])
async def get_positions(request):
    try:
        async with app.ctx.session() as session:
            positions = await session.execute(select(Position))
            positions = positions.scalars().all()

            positions_data = []
            total_delta = 0
            total_theta = 0
            total_stocks_value = 0
            total_options_value = 0

            for position in positions:
                delta, theta = (0, 0)
                if is_option(position.symbol):
                    delta, theta = black_scholes_delta_theta(position)
                    if delta is not None and theta is not None:
                        delta *= position.quantity * OPTION_MULTIPLIER
                        theta *= position.quantity * OPTION_MULTIPLIER
                    total_options_value += position.quantity * position.latest_price * OPTION_MULTIPLIER
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

            cash_subquery = select(
                Balance.broker,
                Balance.strategy,
                func.max(Balance.timestamp).label('latest_cash_timestamp')
            ).filter_by(type='cash').group_by(Balance.broker, Balance.strategy).subquery()

            latest_cash_balances = await session.execute(
                select(Balance.broker, Balance.strategy, Balance.balance)
                .join(
                    cash_subquery,
                    (Balance.broker == cash_subquery.c.broker) &
                    (Balance.strategy == cash_subquery.c.strategy) &
                    (Balance.timestamp == cash_subquery.c.latest_cash_timestamp)
                ).filter(Balance.type == 'cash')
            )
            latest_cash_balances = latest_cash_balances.all()

            cash_balances = {f"{balance.broker}_{balance.strategy}": round(balance.balance, 2) for balance in latest_cash_balances}

            return json({
                'positions': positions_data,
                'total_delta': total_delta,
                'total_theta': total_theta,
                'total_stocks_value': round(total_stocks_value, 2),
                'total_options_value': round(total_options_value, 2),
                'cash_balances': cash_balances
            })
    except Exception as e:
        logger.error(f'Error fetching positions: {str(e)}')
        return json({'status': 'error', 'message': str(e)}, status=500)

@jwt_required
@app.route('/trades', methods=['GET'])
async def get_trades(request):
    try:
        brokers = request.args.getlist('brokers[]')
        strategies = request.args.getlist('strategies[]')

        async with app.ctx.session() as session:
            query = select(Trade)
            if brokers:
                query = query.filter(Trade.broker.in_(brokers))
            if strategies:
                query = query.filter(Trade.strategy.in_(strategies))

            trades = await session.execute(query)
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
            } for trade in trades.scalars().all()]

        return json({'trades': trades_data})
    except Exception as e:
        return json({'status': 'error', 'message': str(e)}, status=500)

@jwt_required
@app.route('/trade_stats', methods=['GET'])
async def get_trade_stats(request):
    try:
        brokers = request.args.getlist('brokers[]')
        strategies = request.args.getlist('strategies[]')

        async with app.ctx.session() as session:
            query = select(Trade)
            if brokers:
                query = query.filter(Trade.broker.in_(brokers))
            if strategies:
                query = query.filter(Trade.strategy.in_(strategies))

            trades = await session.execute(query)
            trades = trades.scalars().all()

            if not trades:
                return json({
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
                day = trade.timestamp.date().isoformat()
                if day not in trades_per_day:
                    trades_per_day[day] = 0
                trades_per_day[day] += 1

            average_profit_loss = total_profit_loss / number_of_trades

            return json({
                'average_profit_loss': average_profit_loss,
                'win_loss_rate': win_loss_rate,
                'number_of_trades': number_of_trades,
                'trades_per_day': trades_per_day
            })
    except Exception as e:
        return json({'status': 'error', 'message': str(e)}, status=500)

@jwt_required
@app.route('/var', methods=['GET'])
async def get_var(request):
    try:
        brokers = request.args.getlist('brokers[]')
        strategies = request.args.getlist('strategies[]')

        async with app.ctx.session() as session:
            query = select(Trade)
            if brokers:
                query = query.filter(Trade.broker.in_(brokers))
            if strategies:
                query = query.filter(Trade.strategy.in_(strategies))

            trades = await session.execute(query)
            trades = trades.scalars().all()

            if not trades:
                return json({'var': 0})

            returns = [trade.profit_loss for trade in trades]
            mean_return = np.mean(returns)
            std_dev_return = np.std(returns)
            var_95 = norm.ppf(0.05, mean_return, std_dev_return)

        return json({'var': var_95})
    except Exception as e:
        return json({'status': 'error', 'message': str(e)}, status=500)

@jwt_required
@app.route('/max_drawdown', methods=['GET'])
async def get_max_drawdown(request):
    try:
        brokers = request.args.getlist('brokers[]')
        strategies = request.args.getlist('strategies[]')

        async with app.ctx.session() as session:
            query = select(Trade)
            if brokers:
                query = query.filter(Trade.broker.in_(brokers))
            if strategies:
                query = query.filter(Trade.strategy.in_(strategies))

            trades = await session.execute(query)
            trades = trades.scalars().all()

            if not trades:
                return json({'max_drawdown': 0})

            cum_returns = np.cumsum([trade.profit_loss for trade in trades])
            running_max = np.maximum.accumulate(cum_returns)
            drawdowns = (running_max - cum_returns) / running_max
            max_drawdown = np.max(drawdowns)

        return json({'max_drawdown': max_drawdown})
    except Exception as e:
        return json({'status': 'error', 'message': str(e)}, status=500)

@jwt_required
@app.route('/sharpe_ratio', methods=['GET'])
async def get_sharpe_ratio(request):
    try:
        brokers = request.args.getlist('brokers[]')
        strategies = request.args.getlist('strategies[]')

        async with app.ctx.session() as session:
            query = select(Trade)
            if brokers:
                query = query.filter(Trade.broker.in_(brokers))
            if strategies:
                query = query.filter(Trade.strategy.in_(strategies))

            trades = await session.execute(query)
            trades = trades.scalars().all()

            if not trades:
                return json({'sharpe_ratio': 0})

            returns = [trade.profit_loss for trade in trades]
            mean_return = np.mean(returns)
            std_dev_return = np.std(returns)
            sharpe_ratio = mean_return / std_dev_return if std_dev_return != 0 else 0

        return json({'sharpe_ratio': sharpe_ratio})
    except Exception as e:
        return json({'status': 'error', 'message': str(e)}, status=500)

# Middleware to add and close session per request
@app.middleware('request')
async def add_session_to_request(request):
    request.ctx.session = app.ctx.session()

@app.middleware('response')
async def close_session(request, response):
    if hasattr(request.ctx, 'session'):
        await request.ctx.session.close()

@app.listener('before_server_start')
async def setup_db(app, loop):
    config = app.config.get("CUSTOM_CONFIG", {})  # Access custom config safely    
    engine = create_database_engine(config)
    async_session_factory = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    app.ctx.session = scoped_session(async_session_factory)

def create_database_engine(config, local_testing=False):
    if local_testing:
        return create_async_engine('sqlite+aiosqlite:///trading.db')
    if 'database' in config and 'url' in config['database']:
        return create_async_engine(config['database']['url'])
    return create_async_engine(os.environ.get("DATABASE_URL", 'sqlite+aiosqlite:///default_trading_system.db'))

def create_app(config):
    logger.info('Adding custom configuration to the app: %s', config)
    app.update_config({"CUSTOM_CONFIG": config})  
    return app
