import asyncio
import yaml
import os
import importlib.util
from brokers.tradier_broker import TradierBroker
from brokers.tastytrade_broker import TastytradeBroker
from brokers.etrade_broker import EtradeBroker
from sqlalchemy.ext.asyncio import create_async_engine
from strategies.constant_percentage_strategy import ConstantPercentageStrategy
from strategies.random_yolo_hedge_strategy import RandomYoloHedge
from strategies.black_swan_strategy import BlackSwanStrategy
from .logger import logger

# Mapping of broker types to their constructors
# TODO: refactor
BROKER_MAP = {
    'tradier': lambda config, engine: TradierBroker(api_key=config['api_key'], secret_key=None, engine=engine, prevent_day_trading=config.get('prevent_day_trading', False)),
    'etrade': lambda config, engine: EtradeBroker(api_key=config['api_key'], secret_key=config['secret_key'], engine=engine, prevent_day_trading=config.get('prevent_day_trading', False)),
    'tastytrade': lambda config, engine: TastytradeBroker(username=config['username'], password=config['password'], engine=engine, prevent_day_trading=config.get('prevent_day_trading', False))
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
        # Initialize the broker with the shared engine
        brokers[broker_name] = BROKER_MAP[broker_name](broker_config, engine)

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
