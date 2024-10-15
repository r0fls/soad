import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker
from .models import Base, Trade, AccountInfo, Position, Balance
from utils.utils import is_option, OPTION_MULTIPLIER, is_futures_symbol, futures_contract_size
from utils.logger import logger

class DBManager:
    def __init__(self, engine):
        self.engine = engine
        self.Session = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=True)
        logger.info('DBManager initialized', extra={'database_url': self.engine.url})

    async def add_account_info(self, account_info):
        async with self.Session() as session:
            try:
                logger.info('Adding account info', extra={'account_info': account_info})
                existing_info = await session.execute(select(AccountInfo).filter_by(broker=account_info.broker))
                existing_info = existing_info.scalar()
                if existing_info:
                    existing_info.value = account_info.value
                    logger.info('Updated existing account info', extra={'account_info': account_info})
                else:
                    session.add(account_info)
                    logger.info('Added new account info', extra={'account_info': account_info})
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error('Failed to add account info', extra={'error': str(e)})

    async def get_trade(self, trade_id):
        async with self.Session() as session:
            try:
                logger.info('Retrieving trade', extra={'trade_id': trade_id})
                result = await session.execute(select(Trade).filter_by(id=trade_id))
                trade = result.scalar()
                if trade is None:
                    logger.warning(f"No trade found with id {trade_id}")
                else:
                    logger.info('Trade retrieved', extra={'trade': trade})
                return trade
            except Exception as e:
                logger.error(f'Failed to retrieve trade {trade_id}', extra={'error': str(e)})
                return None

    async def get_all_trades(self):
        async with self.Session() as session:
            try:
                logger.info('Retrieving all trades')
                result = await session.execute(select(Trade))
                trades = result.scalars().all()
                logger.info('All trades retrieved', extra={'trade_count': len(trades)})
                return trades
            except Exception as e:
                logger.error('Failed to retrieve all trades', extra={'error': str(e)})
                return []

    async def get_position(self, broker, symbol, strategy):
        async with self.Session() as session:
            try:
                logger.info('Retrieving position', extra={'broker': broker, 'symbol': symbol, 'strategy': strategy})
                result = await session.execute(
                    select(Position).filter_by(broker=broker, symbol=symbol, strategy=strategy)
                )
                positions = result.scalars().all()
                if len(positions) > 1:
                    logger.warning('Multiple positions found', extra={'broker': broker, 'symbol': symbol, 'strategy': strategy})
                position = positions[0] if positions else None
                if position is None:
                    logger.warning('Position not found', extra={'broker': broker, 'symbol': symbol, 'strategy': strategy})
                logger.info('Position retrieved', extra={'position': position})
                return position
            except Exception as e:
                logger.error('Failed to retrieve position', extra={'error': str(e)})
                return None

    async def calculate_profit_loss(self, trade):
        async with self.Session() as session:
            try:
                profit_loss = None
                logger.info('Calculating profit/loss', extra={'trade': trade})

                # Fetch current price
                current_price = float(trade.executed_price)
                logger.info(f"Executed price fetched: {current_price}", extra={'trade': trade})
                if current_price is None:
                    logger.error('Executed price is None, cannot calculate profit/loss', extra={'trade': trade})
                    return None

                # Handling buy trades
                if trade.order_type.lower() == 'buy':
                    logger.info('Buy order detected, no P/L calculation needed.', extra={'trade': trade})
                    return profit_loss

                # Handling sell trades
                elif trade.order_type.lower() == 'sell':
                    logger.info('Sell order detected, calculating P/L.', extra={'trade': trade})
                    position = await self.get_position(trade.broker, trade.symbol, trade.strategy)
                    logger.info(f"Position fetched: {position}", extra={'trade': trade})

                    if position and position.quantity == trade.quantity:
                        profit_loss = (float(trade.executed_price) * trade.quantity - float(position.cost_basis))
                        logger.info(f"Full sell detected, profit/loss calculated as: {profit_loss}", extra={'trade': trade})
                    else:
                        profit_loss = await self.calculate_partial_profit_loss(trade, position)
                        logger.info(f"Partial sell, profit/loss calculated as: {profit_loss}", extra={'trade': trade})

                    # Adjust for futures and options
                    if is_futures_symbol(trade.symbol):
                        profit_loss *= futures_contract_size(trade.symbol)
                        logger.info(f"Futures detected, adjusted P/L: {profit_loss}", extra={'trade': trade})
                    if is_option(trade.symbol):
                        profit_loss *= OPTION_MULTIPLIER
                        logger.info(f"Option detected, adjusted P/L: {profit_loss}", extra={'trade': trade})

                logger.info('Profit/loss calculated', extra={'trade': trade, 'profit_loss': profit_loss})
                return profit_loss
            except Exception as e:
                logger.error('Failed to calculate profit/loss', extra={'error': str(e), 'trade': trade})
                return None


    async def calculate_partial_profit_loss(self, trade, position):
        try:
            profit_loss = None
            logger.info('Calculating partial profit/loss', extra={'trade': trade, 'position': position})
            if trade.order_type.lower() == 'sell':
                profit_loss = (float(trade.executed_price) - (float(position.cost_basis) / position.quantity)) * trade.quantity
            logger.info('Partial profit/loss calculated', extra={'trade': trade, 'position': position, 'profit_loss': profit_loss})
            return profit_loss
        except Exception as e:
            logger.error('Failed to calculate partial profit/loss', extra={'error': str(e)})
            return None

    async def update_trade_status(self, trade_id, executed_price, success, profit_loss):
        async with self.Session() as session:
            try:
                logger.info('Updating trade status', extra={'trade_id': trade_id, 'executed_price': executed_price, 'success': success, 'profit_loss': profit_loss})
                result = await session.execute(select(Trade).filter_by(id=trade_id))
                trade = result.scalar()
                if trade:
                    trade.executed_price = executed_price
                    trade.success = success
                    trade.profit_loss = profit_loss
                    await session.commit()
                    logger.info('Trade status updated', extra={'trade': trade})
            except Exception as e:
                await session.rollback()
                logger.error('Failed to update trade status', extra={'error': str(e)})

    async def rename_strategy(self, broker, old_strategy_name, new_strategy_name):
        async with self.Session() as session:
            try:
                logger.info('Updating strategy name', extra={'old_strategy_name': old_strategy_name, 'broker': broker})

                # Update balances
                result = await session.execute(
                    select(Balance).filter_by(broker=broker, strategy=old_strategy_name)
                )
                balances = result.scalars().all()
                for balance in balances:
                    balance.strategy = new_strategy_name
                await session.commit()
                logger.info(f'Updated {len(balances)} balances', extra={'old_strategy_name': old_strategy_name, 'broker': broker})

                # Update trades
                result = await session.execute(
                    select(Trade).filter_by(broker=broker, strategy=old_strategy_name)
                )
                trades = result.scalars().all()
                for trade in trades:
                    trade.strategy = new_strategy_name
                await session.commit()
                logger.info(f'Updated {len(trades)} trades', extra={'old_strategy_name': old_strategy_name, 'broker': broker})

                # Update positions
                result = await session.execute(
                    select(Position).filter_by(broker=broker, strategy=old_strategy_name)
                )
                positions = result.scalars().all()
                for position in positions:
                    position.strategy = new_strategy_name
                await session.commit()
                logger.info(f'Updated {len(positions)} positions', extra={'old_strategy_name': old_strategy_name, 'broker': broker})

            except Exception as e:
                await session.rollback()
                logger.error('Failed to update strategy name', extra={'error': str(e)})
