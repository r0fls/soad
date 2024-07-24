import json
from sqlalchemy.orm import sessionmaker
from .models import Base, Trade, AccountInfo, Position, Balance
from utils.utils import is_option, OPTION_MULTIPLIER, is_futures_option, futures_contract_size
from utils.logger import logger

class DBManager:
    def __init__(self, engine):
        self.engine = engine
        self.Session = sessionmaker(bind=engine)
        logger.info('DBManager initialized', extra={'database_url': self.engine.url})

    def add_account_info(self, account_info):
        session = self.Session()
        try:
            logger.info('Adding account info', extra={'account_info': account_info})
            existing_info = session.query(AccountInfo).filter_by(broker=account_info.broker).first()
            if existing_info:
                existing_info.value = account_info.value
                logger.info('Updated existing account info', extra={'account_info': account_info})
            else:
                session.add(account_info)
                logger.info('Added new account info', extra={'account_info': account_info})
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error('Failed to add account info', extra={'error': str(e)})
        finally:
            session.close()

    def get_trade(self, trade_id):
        session = self.Session()
        try:
            logger.info('Retrieving trade', extra={'trade_id': trade_id})
            trade = session.query(Trade).filter_by(id=trade_id).first()
            logger.info('Trade retrieved', extra={'trade': trade})
            return trade
        except Exception as e:
            logger.error('Failed to retrieve trade', extra={'error': str(e)})
            return None
        finally:
            session.close()

    def get_all_trades(self):
        session = self.Session()
        try:
            logger.info('Retrieving all trades')
            trades = session.query(Trade).all()
            logger.info('All trades retrieved', extra={'trade_count': len(trades)})
            return trades
        except Exception as e:
            logger.error('Failed to retrieve all trades', extra={'error': str(e)})
            return []
        finally:
            session.close()

    def get_position(self, broker, symbol, strategy):
        session = self.Session()
        try:
            logger.info('Retrieving position', extra={'broker': broker, 'symbol': symbol, 'strategy': strategy})
            position = session.query(Position).filter_by(broker=broker, symbol=symbol, strategy=strategy).all()
            if len(position) > 1:
                logger.warning('Multiple positions found', extra={'broker': broker, 'symbol': symbol, 'strategy': strategy})
            position = position[0] if position else None
            if position is None:
                logger.warning('Position not found', extra={'broker': broker, 'symbol': symbol, 'strategy': strategy})
            logger.info('Position retrieved', extra={'position': position})
            return position
        except Exception as e:
            logger.error('Failed to retrieve position', extra={'error': str(e)})
            return None
        finally:
            session.close()

    def calculate_profit_loss(self, trade):
        try:
            profit_loss = None
            logger.info('Calculating profit/loss', extra={'trade': trade})
            current_price = trade.executed_price
            if current_price is None:
                logger.error('Executed price is None, cannot calculate profit/loss', extra={'trade': trade})
                return None

            if trade.order_type.lower() == 'buy':
                return profit_loss
            elif trade.order_type.lower() == 'sell':
                position = self.get_position(trade.broker, trade.symbol, trade.strategy)
                if position.quantity == trade.quantity:
                    profit_loss = trade.executed_price - position.cost_basis
                else:
                    profit_loss = self.calculate_partial_profit_loss(trade, position)
                if is_futures_option(trade.symbol):
                    profit_loss *= get_future_option_multiplier(trade.symbol)
                if is_option(trade.symbol):
                    profit_loss *= OPTION_MULTIPLIER
            logger.info('Profit/loss calculated', extra={'trade': trade, 'profit_loss': profit_loss})
            return profit_loss
        except Exception as e:
            logger.error('Failed to calculate profit/loss', extra={'error': str(e)})
            return None

    def calculate_partial_profit_loss(self, trade, position):
        try:
            profit_loss = None
            logger.info('Calculating partial profit/loss', extra={'trade': trade, 'position': position})
            if trade.order_type.lower() == 'sell':
                profit_loss = (trade.executed_price - (position.cost_basis / position.quantity)) * trade.quantity
            logger.info('Partial profit/loss calculated', extra={'trade': trade, 'position': position, 'profit_loss': profit_loss})
            return profit_loss
        except Exception as e:
            logger.error('Failed to calculate partial profit/loss', extra={'error': str(e)})
            return None

    def update_trade_status(self, trade_id, executed_price, success, profit_loss):
        session = self.Session()
        try:
            logger.info('Updating trade status', extra={'trade_id': trade_id, 'executed_price': executed_price, 'success': success, 'profit_loss': profit_loss})
            trade = session.query(Trade).filter_by(id=trade_id).first()
            if trade:
                trade.executed_price = executed_price
                trade.success = success
                trade.profit_loss = profit_loss
                session.commit()
                logger.info('Trade status updated', extra={'trade': trade})
        except Exception as e:
            session.rollback()
            logger.error('Failed to update trade status', extra={'error': str(e)})
        finally:
            session.close()

    def rename_strategy(self, broker, old_strategy_name, new_strategy_name):
        with self.Session() as session:
            try:
                logger.info('Updating strategy name', extra={'old_strategy_name': old_strategy_name, 'broker': broker})

                # Update balances
                balances = session.query(Balance).filter_by(broker=broker, strategy=old_strategy_name).all()
                for balance in balances:
                    balance.strategy = new_strategy_name
                session.commit()
                logger.info(f'Updated {len(balances)} balances', extra={'old_strategy_name': old_strategy_name, 'broker': broker})

                # Update trades
                trades = session.query(Trade).filter_by(broker=broker, strategy=old_strategy_name).all()
                for trade in trades:
                    trade.strategy = new_strategy_name
                session.commit()
                logger.info(f'Updated {len(trades)} trades', extra={'old_strategy_name': old_strategy_name, 'broker': broker})

                # Update positions
                positions = session.query(Position).filter_by(broker=broker, strategy=old_strategy_name).all()
                for position in positions:
                    position.strategy = new_strategy_name
                session.commit()
                logger.info(f'Updated {len(positions)} positions', extra={'old_strategy_name': old_strategy_name, 'broker': broker})

            except Exception as e:
                session.rollback()
                logger.error('Failed to update strategy name', extra={'error': str(e)})
