import argparse
import asyncio
import time
import os
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from database.models import init_db
from database.db_manager import DBManager
from ui.app import create_app
from utils.config import parse_config, initialize_brokers, initialize_strategies
from utils.logger import logger  # Import the logger
from data.sync_worker import sync_worker  # Import the sync worker

def create_database_engine(config, local_testing=False):
    if local_testing:
        return create_engine('sqlite:///trading.db')
    if 'database' in config and 'url' in config['database']:
        return create_engine(config['database']['url'])
    return create_engine(os.environ.get("DATABASE_URL", 'sqlite:///default_trading_system.db'))

def initialize_database(engine):
    try:
        init_db(engine)
        logger.info('Database initialized successfully')
    except Exception as e:
        logger.error('Failed to initialize database', extra={'error': str(e)})
        raise

async def initialize_system_components(config):
    try:
        brokers = initialize_brokers(config)
        logger.info('Brokers initialized successfully')
        strategies = await initialize_strategies(brokers, config)
        logger.info('Strategies initialized successfully')
        return brokers, strategies
    except Exception as e:
        logger.error('Failed to initialize system components', extra={'error': str(e)})
        raise

async def initialize_brokers_and_strategies(config):
    engine = create_database_engine(config)
    if config.get('rename_strategies'):
        for strategy in config['rename_strategies']:
            try:
                DBManager(engine).rename_strategy(strategy['old_strategy_name'], strategy['new_strategy_name'], strategy['broker'])
            except Exception as e:
                logger.error('Failed to rename strategy', extra={'error': str(e), 'renameStrategyConfig': strategy})
                raise
    # Initialize the brokers and strategies
    try:
        brokers, strategies = await initialize_system_components(config)
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
    return brokers, strategies

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
    engine = create_database_engine(config)
    logger.info('Database engine created', extra={'db_url': engine.url})

    # Initialize the database
    initialize_database(engine)

    # Initialize the brokers and strategies
    brokers, strategies = await initialize_brokers_and_strategies(config)

    # Execute the strategies loop
    rebalance_intervals = { s: timedelta(minutes=strategies[s].rebalance_interval_minutes) for s in strategies }
    last_rebalances = {s: datetime.min for s in strategies}
    logger.info('Entering the strategies execution loop')

    while True:
        now = datetime.now()
        for strategy_name, strategy in strategies.items():
            if now - last_rebalances[strategy_name] >= rebalance_intervals[strategy_name]:
                try:
                    await strategy.rebalance()
                    last_rebalances[strategy_name] = now
                    logger.info(f'Strategy {strategy_name} rebalanced successfully', extra={'time': now})
                except Exception as e:
                    # Try to reinitalize the brokers and strategies
                    logger.error(f'Error during rebalancing strategy {strategy_name}', extra={'error': str(e)})
                    brokers, strategies = await initialize_brokers_and_strategies(config)
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
    engine = create_database_engine(config, local_testing)
    logger.info('Database engine created for API server', extra={'db_url': engine.url})

    # Initialize the database
    initialize_database(engine)

    # Create and run the app
    try:
        app = create_app(engine)
        logger.info('API server created successfully')
        app.run(host="0.0.0.0", port=8000, debug=True)
    except Exception as e:
        logger.error('Failed to start API server', extra={'error': str(e)})

async def start_sync_worker(config_path):
    logger.info('Starting sync worker', extra={'config_path': config_path})

    # Parse the configuration file
    try:
        config = parse_config(config_path)
        logger.info('Configuration parsed successfully')
    except Exception as e:
        logger.error('Failed to parse configuration', extra={'error': str(e)})
        return

    # Setup the database engine
    engine = create_database_engine(config)
    logger.info('Database engine created for sync worker', extra={'db_url': engine.url})

    # Initialize the database
    initialize_database(engine)

    # Initialize the brokers
    try:
        brokers = initialize_brokers(config)
        logger.info('Brokers initialized successfully')
    except Exception as e:
        logger.error('Failed to initialize brokers', extra={'error': str(e)})
        return

    # Start the sync worker
    try:
        await sync_worker(engine, brokers)
        logger.info('Sync worker started successfully')
    except Exception as e:
        logger.error('Failed to start sync worker', extra={'error': str(e)})

async def main():
    parser = argparse.ArgumentParser(description="Run trading strategies, start API server, or start sync worker based on YAML configuration.")
    parser.add_argument('--mode', choices=['trade', 'api', 'sync'], required=True, help='Mode to run the system in: "trade", "api", or "sync"')
    parser.add_argument('--config', type=str, help='Path to the YAML configuration file.')
    parser.add_argument('--local_testing', action='store_true', help='Run API server with local testing configuration.')
    args = parser.parse_args()

    if args.mode == 'trade':
        if not args.config:
            parser.error('--config is required when mode is "trade"')
        await start_trading_system(args.config)
    elif args.mode == 'api':
        start_api_server(config_path=args.config, local_testing=args.local_testing)
    elif args.mode == 'sync':
        if not args.config:
            parser.error('--config is required when mode is "sync"')
        await start_sync_worker(args.config)

if __name__ == "__main__":
    asyncio.run(main())
