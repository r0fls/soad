import yaml
import importlib.util
from brokers.tradier_broker import TradierBroker
from brokers.tastytrade_broker import TastytradeBroker
from brokers.etrade_broker import EtradeBroker
from strategies.constant_percentage_strategy import ConstantPercentageStrategy

# Mapping of broker types to their constructors
BROKER_MAP = {
    'tradier': lambda config: TradierBroker(api_key=config['api_key'], secret_key=None),
    'tastytrade': lambda config: TastytradeBroker(api_key=config['api_key'], secret_key=None),
    'etrade': lambda config: EtradeBroker(api_key=config['api_key'], secret_key=config['secret_key']),
}

# Mapping of strategy types to their constructors
STRATEGY_MAP = {
    'constant_percentage': lambda broker, config: ConstantPercentageStrategy(
        broker=broker,
        stock_allocations=config['stock_allocations'],
        cash_percentage=config['cash_percentage'],
        rebalance_interval_minutes=config['rebalance_interval_minutes'],
        starting_capital=config['starting_capital']
    ),
    'custom': lambda broker, config: load_custom_strategy(broker, config)
}

def load_strategy_class(file_path, class_name):
    spec = importlib.util.spec_from_file_location(class_name, file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    strategy_class = getattr(module, class_name)
    return strategy_class

def load_custom_strategy(broker, config):
    strategy_class = load_strategy_class(config['file'], config['className'])
    return strategy_class(
        broker=broker,
        stock_allocations=config['stock_allocations'],
        cash_percentage=config['cash_percentage'],
        rebalance_interval_minutes=config['rebalance_interval_minutes'],
        starting_capital=config['starting_capital']
    )

def parse_config(config_path):
    with open(config_path, 'r') as file:
        config = yaml.safe_load(file)
    return config

def initialize_brokers(config):
    brokers_config = config['brokers']
    brokers = {}
    for broker_name, broker_config in brokers_config.items():
        broker_type = broker_config['type']
        if broker_type in BROKER_MAP:
            brokers[broker_name] = BROKER_MAP[broker_type](broker_config)
        else:
            raise ValueError(f"Unsupported broker type: {broker_type}")
    return brokers

def initialize_strategies(brokers, config):
    strategies_config = config['strategies']
    strategies = []
    for strategy_config in strategies_config:
        strategy_type = strategy_config['type']
        broker_name = strategy_config['broker']
        broker = brokers[broker_name]
        if strategy_type in STRATEGY_MAP:
            strategies.append(STRATEGY_MAP[strategy_type](broker, strategy_config))
        else:
            raise ValueError(f"Unsupported strategy type: {strategy_type}")
    return strategies
