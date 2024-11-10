import asyncio
import yaml
import os
import importlib.util
from brokers.tradier_broker import TradierBroker
from brokers.tastytrade_broker import TastytradeBroker
from brokers.alpaca_broker import AlpacaBroker
from brokers.kraken_broker import KrakenBroker
from database.models import init_db
from database.db_manager import DBManager
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import create_engine
from strategies.constant_percentage_strategy import ConstantPercentageStrategy
from strategies.random_yolo_hedge_strategy import RandomYoloHedge
from strategies.black_swan_strategy import BlackSwanStrategy
from strategies.simple_strategy import SimpleStrategy
from .logger import logger

# Mapping of broker types to their constructors
# TODO: refactor
BROKER_MAP = {
    'tradier': lambda config, engine: TradierBroker(
        api_key=os.environ.get('TRADIER_API_KEY', config.get('api_key')),
        secret_key=None,
        engine=engine,
        prevent_day_trading=config.get('prevent_day_trading', False)
    ),
    'tastytrade': lambda config, engine: TastytradeBroker(
        username=os.environ.get('TASTYTRADE_USERNAME', config.get('username')),
        password=os.environ.get('TASTYTRADE_PASSWORD', config.get('password')),
        engine=engine,
        prevent_day_trading=config.get('prevent_day_trading', False)
    ),
    'alpaca': lambda config, engine: AlpacaBroker(
        api_key=os.environ.get('ALPACA_API_KEY', config.get('api_key')),
        secret_key=os.environ.get('ALPACA_SECRET_KEY', config.get('secret_key')),
        engine=engine,
        prevent_day_trading=config.get('prevent_day_trading', False)
    ),
    'kraken': lambda config, engine: KrakenBroker(
        api_key=os.environ.get('KRAKEN_API_KEY', config.get('api_key')),
        secret_key=os.environ.get('KRAKEN_SECRET_KEY', config.get('secret_key')),
        engine=engine
    )
}


# Mapping of strategy types to their constructors
STRATEGY_MAP = {
    'constant_percentage': lambda broker, strategy_name, config: ConstantPercentageStrategy(
        broker=broker,
        strategy_name=strategy_name,
        stock_allocations=config['stock_allocations'],
        cash_percentage=config['cash_percentage'],
        rebalance_interval_minutes=config['rebalance_interval_minutes'],
        starting_capital=config['starting_capital'],
        buffer=config.get('rebalance_buffer', 0.1)
    ),
    'random_yolo_hedge': lambda broker, strategy_name, config: RandomYoloHedge(
        broker=broker,
        strategy_name=strategy_name,
        rebalance_interval_minutes=config['rebalance_interval_minutes'],
        starting_capital=config['starting_capital'],
        max_spread_percentage=config.get('max_spread_percentage', 0.25),
        bet_percentage=config.get('bet_percentage', 0.2),
    ),
    'simple': lambda broker, strategy_name, config: SimpleStrategy(
        broker=broker,
        buy_threshold=config.get('buy_threshold', 0),
        sell_threshold=config.get('sell_threshold', 0)
    ),
    'black_swan': lambda broker, strategy_name, config: BlackSwanStrategy(
        broker=broker,
        strategy_name=strategy_name,
        rebalance_interval_minutes=config['rebalance_interval_minutes'],
        starting_capital=config['starting_capital'],
        symbol=config.get('symbol', 'SPY'),
        otm_percentage=config.get('otm_percentage', 0.05),
        expiry_days=config.get('expiry_days', 30),
        bet_percentage=config.get('bet_percentage', 0.1),
        holding_period_days=config.get('holding_period_days', 14),
        spike_percentage=config.get('spike_percentage', 500)
    ),
    'custom': lambda broker, strategy_name, config: load_custom_strategy(broker, strategy_name, config)
}

def load_strategy_class(file_path, class_name):
    logger.info(f"Attempting to load strategy class '{class_name}' from file '{file_path}'")
    try:
        spec = importlib.util.spec_from_file_location(class_name, file_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        strategy_class = getattr(module, class_name)
        logger.info(f"Successfully loaded strategy class '{class_name}' from file '{file_path}'")
        return strategy_class
    except Exception as e:
        logger.error(f"Failed to load strategy class '{class_name}' from file '{file_path}': {e}")
        raise

def load_custom_strategy(broker, strategy_name, config):
    try:
        file_path = config['file_path']
        class_name = config['class_name']
        starting_capital = config['starting_capital']
        rebalance_interval_minutes = config['rebalance_interval_minutes']
        strategy_class = load_strategy_class(file_path, class_name)
        logger.info(f"Initializing custom strategy '{class_name}' with config: {config}")
        return strategy_class(broker, strategy_name, starting_capital, rebalance_interval_minutes, **config.get('strategy_params', {}))
    except Exception as e:
        logger.error(f"Error initializing custom strategy '{config['class_name']}': {e}")
        raise

def parse_config(config_path):
    with open(config_path, 'r') as file:
        config = yaml.safe_load(file)
    return config

def initialize_brokers(config):
    # Create a single database engine for all brokers
    if 'database' in config and 'url' in config['database']:
        engine = create_async_engine(config['database']['url'])
    elif os.environ.get("DATABASE_URL", None):
        engine = create_async_engine(os.environ.get("DATABASE_URL"))
    else:
        engine = create_async_engine('sqlite+aiosqlite:///default_trading_system.db')

    brokers = {}
    for broker_name, broker_config in config['brokers'].items():
        try:
            # Initialize the broker with the shared engine
            logger.debug(f"Initializing broker '{broker_name}' with config: {broker_config}")
            brokers[broker_name] = BROKER_MAP[broker_name](broker_config, engine)
        except Exception as e:
            logger.error(f"Error initializing broker '{broker_name}': {e}")
            continue

    return brokers

async def initialize_strategy(strategy_name, strategy_type, broker, config):
    constructor = STRATEGY_MAP.get(strategy_type)
    if constructor is None:
        raise ValueError(f"Unknown strategy type: {strategy_type}")
    strategy = constructor(broker, strategy_name, config)
    if asyncio.iscoroutinefunction(strategy.initialize):
        await strategy.initialize()
        return strategy
    elif callable(strategy.initialize):
        strategy.initialize()
        return strategy
    else:
        return strategy

async def initialize_strategies(brokers, config):
    strategies_config = config['strategies']
    strategies = {}
    for strategy_name in strategies_config:
        try:
            strategy_config = strategies_config[strategy_name]
            strategy_type = strategy_config['type']
            broker_name = strategy_config['broker']
            broker = brokers[broker_name]
            if strategy_type in STRATEGY_MAP:
                strategy = await initialize_strategy(strategy_name, strategy_type, broker, strategy_config)
                strategies[strategy_name]= strategy
            else:
                logger.error(f"Unknown strategy type: {strategy_type}")
        except Exception as e:
            logger.error(f"Error initializing strategy '{strategy_name}': {e}")
    return strategies

def create_api_database_engine(config, local_testing=False):
    if local_testing:
        return create_engine('sqlite:///trading.db')
    if 'database' in config and 'url' in config['database']:
        return create_engine(config['database']['url'])
    return create_engine(os.environ.get("DATABASE_URL", 'sqlite:///default_trading_system.db'))


def create_database_engine(config, local_testing=False):
    if local_testing:
        return create_async_engine('sqlite+aiosqlite:///trading.db')
    if type(config) == str:
        return create_async_engine(config)
    if 'database' in config and 'url' in config['database']:
        return create_async_engine(config['database']['url'])
    return create_async_engine(os.environ.get("DATABASE_URL", 'sqlite:///default_trading_system.db'))

async def initialize_database(engine):
    try:
        await init_db(engine)
        logger.info('Database initialized successfully')
    except Exception as e:
        logger.error('Failed to initialize database', extra={'error': str(e)}, exc_info=True)
        raise

async def initialize_system_components(config):
    try:
        brokers = initialize_brokers(config)
        logger.info('Brokers initialized successfully')
        strategies = await initialize_strategies(brokers, config)
        logger.info('Strategies initialized successfully')
        return brokers, strategies
    except Exception as e:
        logger.error('Failed to initialize system components', extra={'error': str(e)}, exc_info=True)
        raise

async def initialize_brokers_and_strategies(config):
    engine = create_database_engine(config)
    if config.get('rename_strategies'):
        for strategy in config['rename_strategies']:
            try:
                DBManager(engine).rename_strategy(strategy['broker'], strategy['old_strategy_name'], strategy['new_strategy_name'])
            except Exception as e:
                logger.error('Failed to rename strategy', extra={'error': str(e), 'renameStrategyConfig': strategy}, exc_info=True)
                raise
    # Initialize the brokers and strategies
    try:
        brokers, strategies = await initialize_system_components(config)
    except Exception as e:
        logger.error('Failed to initialize brokers', extra={'error': str(e)}, exc_info=True)
        return

    # Initialize the strategies
    try:
        strategies = await initialize_strategies(brokers, config)
        logger.info('Strategies initialized successfully')
    except Exception as e:
        logger.error('Failed to initialize strategies', extra={'error': str(e)}, exc_info=True)
        return
    return brokers, strategies
