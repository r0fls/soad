import argparse
import asyncio
import time
import os
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import create_async_engine
from ui.app import create_app
from utils.config import parse_config, initialize_brokers, initialize_strategies, create_database_engine, create_api_database_engine, initialize_database, initialize_brokers_and_strategies
from utils.logger import logger  # Import the logger
from utils.utils import is_market_open, is_futures_market_open
import data.sync_worker as sync_worker
from order_manager.manager import run_order_manager

SYNC_WORKER_INTERVAL_SECONDS = 60 * 5
ORDER_MANAGER_INTERVAL_SECONDS = 60

# TODO: fix the need to restart to refresh the tastytrade token
# TODO: refactor/redesign to allow strategies that are not discretely rebalanced
#       (i.e. streaming via websockets)
async def start_trading_system(config_path):
    logger.info('Starting the trading system', extra={'config_path': config_path})

    # Parse the configuration file
    try:
        config = parse_config(config_path)
        logger.info('Configuration parsed successfully')
    except Exception as e:
        logger.error('Failed to parse configuration', extra={'error': str(e)}, exc_info=True)
        return

    # Setup the database engine
    engine = create_database_engine(config)
    logger.info('Database engine created', extra={'db_url': engine.url})

    # Initialize the database
    await initialize_database(engine)

    # Initialize the brokers and strategies
    brokers, strategies = await initialize_brokers_and_strategies(config)

    # Execute the strategies loop
    rebalance_intervals = {s: timedelta(minutes=strategies[s].rebalance_interval_minutes) for s in strategies}
    last_rebalances = {s: datetime.min for s in strategies}
    logger.info('Entering the strategies execution loop')

    start_time = datetime.now()
    end_time = start_time + timedelta(hours=24)

    while datetime.now() < end_time:
        now = datetime.now()
        # Collect all the strategies that need rebalancing
        # rebalance synchronously
        for strategy_name, strategy in strategies.items():
            if now - last_rebalances[strategy_name] >= rebalance_intervals[strategy_name]:
                try:
                    await strategy.rebalance()
                except Exception as e:
                    logger.error(f"Error during rebalancing strategy {strategy_name}",
                                 extra={'error': str(e)}, exc_info=True)
                    brokers, strategies = await initialize_brokers_and_strategies(config)

        #strategies_to_rebalance = []
        #for strategy_name, strategy in strategies.items():
        #    if now - last_rebalances[strategy_name] >= rebalance_intervals[strategy_name]:
        #        strategies_to_rebalance.append((strategy_name, strategy))
        #if strategies_to_rebalance:
        #    try:
        #        # Perform all rebalances concurrently
        #        await asyncio.gather(
        #            *[strategy.rebalance() for _, strategy in strategies_to_rebalance]
        #        )
        #        for strategy_name, _ in strategies_to_rebalance:
        #            last_rebalances[strategy_name] = now
        #            logger.info(f'Strategy {strategy_name} rebalanced successfully', extra={'time': now})
        #    except Exception as e:
        #        logger.error(f"Error during rebalancing strategies",
        #                     extra={'error': str(e), 'strategy': strategy_name}, exc_info=True)
        #        brokers, strategies = await initialize_brokers_and_strategies(config)

        await asyncio.sleep(60)  # Check every minute
    logger.info('Trading system finished 24 hours of trading')

async def start_api_server(config_path=None, local_testing=False):
    logger.info('Starting API server', extra={'config_path': config_path, 'local_testing': local_testing})

    if config_path is None:
        config = {}
    else:
        try:
            config = parse_config(config_path)
            logger.info('Configuration parsed successfully for API server')
        except Exception as e:
            logger.error('Failed to parse configuration for API server', extra={'error': str(e)}, exc_info=True)
            return

    # Setup the database engine
    engine = create_api_database_engine(config, local_testing)
    logger.info('Database engine created for API server', extra={'db_url': engine.url})

    # Initialize the database
    async_db_url = os.environ.get("ASYNC_DATABASE_URL", 'sqlite+aiosqlite:///default_trading_system.db')
    async_db_engine = create_database_engine(async_db_url, local_testing)
    await initialize_database(async_db_engine)

    # Create and run the app
    try:
        app = create_app(engine)
        logger.info('API server created successfully')
        app.run(host="0.0.0.0", port=8000, debug=True)
    except Exception as e:
        logger.error('Failed to start API server', extra={'error': str(e)}, exc_info=True)

async def start_order_manager(config_path):
    logger.info('Starting order manager', extra={'config_path': config_path})
    config = parse_config(config_path)
    engine = create_database_engine(config)
    await initialize_database(engine)
    try:
        brokers = initialize_brokers(config)
        logger.info('Brokers initialized successfully')
    except Exception as e:
        logger.error('Failed to initialize brokers', extra={'error': str(e)})
        return
    while True:
        try:
            await run_order_manager(engine, brokers)
            logger.info('Order manager started successfully')
            await asyncio.sleep(ORDER_MANAGER_INTERVAL_SECONDS)
        except Exception as e:
            logger.error('Failed to start order manager, trying to initialize brokers again', extra={'error': str(e)}, exc_info=True)
            brokers = initialize_brokers(config)

async def start_sync_worker(config_path):
    logger.info('Starting sync worker', extra={'config_path': config_path})

    # Parse the configuration file
    try:
        config = parse_config(config_path)
        # TODO: should this default to False instead?
        if config.get("update_uncateorized_positions"):
            sync_worker.UPDATE_UNCATEGORIZED_POSITIONS = True
        if config.get("timeout_duration"):
            sync_worker.TIMEOUT_DURATION = config.get("timeout_duration")
        logger.info('Configuration parsed successfully')
    except Exception as e:
        logger.error('Failed to parse configuration', extra={'error': str(e)}, exc_info=True)
        return

    # Setup the database engine
    engine = create_database_engine(config)
    logger.info('Database engine created for sync worker', extra={'db_url': engine.url})

    # Initialize the database
    await initialize_database(engine)

    # Initialize the brokers
    try:
        brokers = initialize_brokers(config)
        logger.info('Brokers initialized successfully')
    except Exception as e:
        logger.error('Failed to initialize brokers', extra={'error': str(e)})
        return

    # Start the sync worker
    while True:
        try:
            await sync_worker.start(engine, brokers)
            logger.info('Sync worker started successfully')
            if is_market_open():
                await asyncio.sleep(SYNC_WORKER_INTERVAL_SECONDS)
            elif config.get('futures_enabled', False) and is_futures_market_open():
                await asyncio.sleep(SYNC_WORKER_INTERVAL_SECONDS)
            else:
                logger.info('Market is closed, sleeping for 30 minutes')
                await asyncio.sleep(60 * 30)
        except Exception as e:
            logger.error('Failed to start sync worker, trying to initialize brokers again', extra={'error': str(e)}, exc_info=True)
            brokers = initialize_brokers(config)

async def main():
    parser = argparse.ArgumentParser(description="Run trading strategies, start API server, or start sync worker based on YAML configuration.")
    parser.add_argument('--mode', choices=['trade', 'api', 'sync', 'manager'], required=True, help='Mode to run the system in: "trade", "api", or "sync"')
    parser.add_argument('--config', type=str, help='Path to the YAML configuration file.')
    parser.add_argument('--local_testing', action='store_true', help='Run API server with local testing configuration.')
    args = parser.parse_args()

    if args.mode == 'trade':
        if not args.config:
            parser.error('--config is required when mode is "trade"')
        while True:
            try:
                await start_trading_system(args.config)
            except Exception as e:
                logger.error('Error in trading system', extra={'error': str(e)})
                logger.info('Restarting the trading system')
                continue
    elif args.mode == 'api':
        await start_api_server(config_path=args.config, local_testing=args.local_testing)
    elif args.mode == 'sync':
        if not args.config:
            parser.error('--config is required when mode is "sync"')
        try:
            await start_sync_worker(args.config)
        except Exception as e:
            logger.error('Error in sync worker', extra={'error': str(e)}, exc_info=True)
            await start_sync_worker(args.config)
    elif args.mode == 'manager':
        if not args.config:
            parser.error('--config is required when mode is "order_manager"')
        try:
            await start_order_manager(args.config)
        except Exception as e:
            logger.error('Error in order manager', extra={'error': str(e)}, exc_info=True)
            await start_order_manager(args.config)

if __name__ == "__main__":
    asyncio.run(main())
