import argparse
import time
from datetime import datetime, timedelta
from utils.config import parse_config, initialize_brokers, initialize_strategies

def main(config_path):
    # Parse the configuration file
    config = parse_config(config_path)
    
    # Initialize the brokers
    brokers = initialize_brokers(config)
    
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

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run trading strategies based on YAML configuration.")
    parser.add_argument('--config', type=str, required=True, help='Path to the YAML configuration file.')
    args = parser.parse_args()
    
    main(args.config)
