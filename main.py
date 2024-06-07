import argparse
import time
from datetime import datetime, timedelta
from database.models import init_db
from ui.app import create_app
from utils.config import parse_config, initialize_brokers, initialize_strategies
from sqlalchemy import create_engine
from data.sync_service import run_sync_service

def start_trading_system(config_path):
    # Parse the configuration file
    config = parse_config(config_path)
    
    # Initialize the brokers
    brokers = initialize_brokers(config)

    if 'database' in config and 'url' in config['database']:
        engine = create_engine(config['database']['url'])
    else:
        engine = create_engine('sqlite:///default_trading_system.db')
    
    # Initialize the database
    init_db(engine)
    
    # Connect to each broker
    for broker in brokers.values():
        broker.connect()
    
    # Initialize the strategies
    strategies = initialize_strategies(brokers, config)
    
    # Execute the strategies loop
    rebalance_intervals = [timedelta(minutes=s.rebalance_interval_minutes) for s in strategies]
    last_rebalances = [datetime.min for _ in strategies]
    
    while True:
        now = datetime.now()
        for i, strategy in enumerate(strategies):
            if now - last_rebalances[i] >= rebalance_intervals[i]:
                strategy.rebalance()
                last_rebalances[i] = now
        time.sleep(60)  # Check every minute


def start_sync_service(config_path=None, local_testing=False):
    if config_path is None:
        config = {}
    else:
        config = parse_config(config_path)

    if local_testing:
        engine = create_engine('sqlite:///trading.db')
    elif 'database' in config and 'url' in config['database']:
        engine = create_engine(config['database']['url'])
    else:
        engine = create_engine('sqlite:///default_trading_system.db')
    run_sync_service(config, engine)


def start_api_server(config_path=None, local_testing=False):
    if config_path is None:
        config = {}
    else:
        config = parse_config(config_path)

    if local_testing:
        engine = create_engine('sqlite:///trading.db')
    elif 'database' in config and 'url' in config['database']:
        engine = create_engine(config['database']['url'])
    else:
        engine = create_engine('sqlite:///default_trading_system.db')

    # Initialize the database
    init_db(engine)

    app = create_app(engine)
    app.run(host="0.0.0.0", port=8000, debug=True)

def main():
    parser = argparse.ArgumentParser(description="Run trading strategies or start API server based on YAML configuration.")
    parser.add_argument('--mode', choices=['trade', 'api', 'sync'], required=True, help='Mode to run the system in: "trade" or "api"')
    parser.add_argument('--config', type=str, help='Path to the YAML configuration file.')
    parser.add_argument('--local_testing', action='store_true', help='Run API server with local testing configuration.')
    args = parser.parse_args()

    if args.mode == 'trade':
        if not args.config:
            parser.error('--config is required when mode is "trade"')
        start_trading_system(args.config)
    elif args.mode == 'api':
        start_api_server(config_path=args.config, local_testing=args.local_testing)
    elif args.mode == 'sync':
        if not args.config:
            parser.error('--config is required when mode is "sync"')
        start_sync_service(args.config)

if __name__ == "__main__":
    main()
