from datetime import timedelta
from strategies.base_strategy import BaseStrategy

class ConstantPercentageStrategy(BaseStrategy):
    def __init__(self, broker, stock_allocations, cash_percentage, rebalance_interval_minutes, starting_capital):
        super().__init__(broker)
        self.stock_allocations = stock_allocations
        self.rebalance_interval_minutes = rebalance_interval_minutes
        self.cash_percentage = cash_percentage
        self.rebalance_interval = timedelta(minutes=rebalance_interval_minutes)
        self.starting_capital = starting_capital

    def rebalance(self):
        account_info = self.broker.get_account_info()
        cash_balance = account_info.get('cash_available')
        # TODO: get the current balance for this strategy from the DB 
        #  - (initial balance - change over time)
        # NOTE: this is not available in the broker
        total_balance = 0
        
        target_cash_balance = total_balance * self.cash_percentage
        target_investment_balance = total_balance - target_cash_balance
        
        current_positions = self.get_current_positions()
        
        for stock, allocation in self.stock_allocations.items():
            target_balance = target_investment_balance * allocation
            current_position = current_positions.get(stock, 0)
            current_price = self.broker.get_current_price(stock)
            target_quantity = target_balance // current_price
            if current_position < target_quantity:
                self.broker.place_order(stock, target_quantity - current_position, 'buy', 'constant_percentage')
            elif current_position > target_quantity:
                self.broker.place_order(stock, current_position - target_quantity, 'sell', 'constant_percentage')

    def get_current_positions(self):
        positions = self.broker.get_positions()
        return {position: positions[position]['quantity'] for position in positions}
