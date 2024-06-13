import argparse
import asyncio
import time
import os
from datetime import datetime, timedelta
from database.models import init_db, drop_then_init_db
from ui.app import create_app
from utils.config import parse_config, initialize_brokers, initialize_strategies
from sqlalchemy import create_engine
from utils.logger import logger  # Import the logger

async def start_trading_system(config_path):
    logger.info('Starting the trading system', extra={'config_path': config_path})

    # Parse the configuration file
    try:
        config = parse_config(config_path)
        logger.info('Configuration parsed successfully')
    except Exception as e:
        logger.error('Failed to parse configuration', extra={'error': str(e)})
        return

    # Setup the database engine
    if 'database' in config and 'url' in config['database']:
        engine = create_engine(config['database']['url'])
    elif os.environ.get("DATABASE_URL", None):
        engine = create_engine(os.environ.get("DATABASE_URL"))
    else:
        engine = create_engine('sqlite:///default_trading_system.db')
    logger.info('Database engine created', extra={'db_url': engine.url})

    # Initialize the database
    try:
        init_db(engine)
        logger.info('Database initialized successfully')
    except Exception as e:
        logger.error('Failed to initialize database', extra={'error': str(e)})
        return

    # Initialize the brokers
    try:
        brokers = initialize_brokers(config)
        logger.info('Brokers initialized successfully')
    except Exception as e:
        logger.error('Failed to initialize brokers', extra={'error': str(e)})
        return

    # Initialize the strategies
    try:
        strategies = await initialize_strategies(brokers, config)
        logger.info('Strategies initialized successfully')
    except Exception as e:
        logger.error('Failed to initialize strategies', extra={'error': str(e)})
        return

    # Execute the strategies loop
    rebalance_intervals = [timedelta(minutes=s.rebalance_interval_minutes) for s in strategies]
    last_rebalances = [datetime.min for _ in strategies]
    logger.info('Entering the strategies execution loop')

    while True:
        now = datetime.now()
        for i, strategy in enumerate(strategies):
            if now - last_rebalances[i] >= rebalance_intervals[i]:
                try:
                    await strategy.rebalance()
                    last_rebalances[i] = now
                    logger.info(f'Strategy {i} rebalanced successfully', extra={'time': now})
                except Exception as e:
                    logger.error(f'Error during rebalancing strategy {i}', extra={'error': str(e)})
        await asyncio.sleep(60)  # Check every minute

def start_api_server(config_path=None, local_testing=False):
    logger.info('Starting API server', extra={'config_path': config_path, 'local_testing': local_testing})

    if config_path is None:
        config = {}
    else:
        try:
            config = parse_config(config_path)
            logger.info('Configuration parsed successfully for API server')
        except Exception as e:
            logger.error('Failed to parse configuration for API server', extra={'error': str(e)})
            return

    # Setup the database engine
    if local_testing:
        engine = create_engine('sqlite:///trading.db')
    elif 'database' in config and 'url' in config['database']:
        engine = create_engine(config['database']['url'])
    elif os.environ.get("DATABASE_URL", None):
        engine = create_engine(os.environ.get("DATABASE_URL"))
    else:
        engine = create_engine('sqlite:///default_trading_system.db')
    logger.info('Database engine created for API server', extra={'db_url': engine.url})

    # Initialize the database
    try:
        init_db(engine)
        logger.info('Database initialized successfully for API server')
    except Exception as e:
        logger.error('Failed to initialize database for API server', extra={'error': str(e)})
        return

    # Create and run the app
    try:
        app = create_app(engine)
        logger.info('API server created successfully')
        app.run(host="0.0.0.0", port=8000, debug=True)
    except Exception as e:
        logger.error('Failed to start API server', extra={'error': str(e)})

async def main():
    parser = argparse.ArgumentParser(description="Run trading strategies or start API server based on YAML configuration.")
    parser.add_argument('--mode', choices=['trade', 'api'], required=True, help='Mode to run the system in: "trade" or "api"')
    parser.add_argument('--config', type=str, help='Path to the YAML configuration file.')
    parser.add_argument('--local_testing', action='store_true', help='Run API server with local testing configuration.')
    args = parser.parse_args()

    if args.mode == 'trade':
        if not args.config:
            parser.error('--config is required when mode is "trade"')
        await start_trading_system(args.config)
    elif args.mode == 'api':
        start_api_server(config_path=args.config, local_testing=args.local_testing)

if __name__ == "__main__":
    asyncio.run(main())
