from abc import ABC, abstractmethod
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import and_
from sqlalchemy import select
from database.db_manager import DBManager
from database.models import Trade, AccountInfo, Position, Balance
from datetime import datetime
from utils.logger import logger
from utils.utils import is_option, OPTION_MULTIPLIER, is_futures_symbol, futures_contract_size


class BaseBroker(ABC):
    def __init__(
            self,
            broker_name,
            engine,
            prevent_day_trading=False):
        self.broker_name = broker_name.lower()
        self.db_manager = DBManager(engine)
        # Use AsyncSession
        self.Session = sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=True)
        self.account_id = None
        self.prevent_day_trading = prevent_day_trading
        logger.debug(
            'Initialized BaseBroker', extra={
                'broker_name': self.broker_name})

    @abstractmethod
    def connect(self):
        pass

    def get_cost_basis(self, symbol):
        """
        Retrieve the cost basis for a specific position (symbol) from the broker.
        """
        pass

    @abstractmethod
    def _get_account_info(self):
        pass

    @abstractmethod
    def _place_order(self, symbol, quantity, side, price=None, order_type='limit'):
        pass

    def _place_future_option_order(
            self,
            symbol,
            quantity,
            side,
            price=None):
        pass

    def _place_option_order(self, symbol, quantity, side, price=None):
        pass

    @abstractmethod
    def _get_order_status(self, order_id):
        pass

    @abstractmethod
    def _cancel_order(self, order_id):
        pass

    def _get_options_chain(self, symbol, expiration_date):
        pass

    @abstractmethod
    def get_current_price(self, symbol):
        pass

    @abstractmethod
    def get_positions(self):
        pass

    async def get_account_info(self):
        '''Get the account information'''
        logger.debug('Getting account information')
        try:
            account_info = self._get_account_info()
            await self.db_manager.add_account_info(AccountInfo(
                broker=self.broker_name, value=account_info['value']
            ))
            logger.debug(
                'Account information retrieved', extra={
                    'account_info': account_info})
            return account_info
        except Exception as e:
            logger.error(
                'Failed to get account information',
                extra={
                    'error': str(e)})
            return None

    async def has_bought_today(self, symbol):
        try:
            today = datetime.now().date()
            logger.debug('Checking if bought today', extra={'symbol': symbol})

            async with self.Session() as session:
                result = await session.execute(
                    select(Trade)
                    .filter_by(symbol=symbol, broker=self.broker_name, side='buy')
                    .filter(Trade.timestamp >= today)
                )
                trade = result.scalars().first()
                return trade is not None
        except Exception as e:
            logger.error(
                'Failed to check if bought today', extra={
                    'error': str(e)})
            return False

    async def update_positions(self, trade_id, session):
        '''Update the positions based on the trade'''
        try:
            # Fetch the trade
            result = await session.execute(select(Trade).filter_by(id=trade_id))
            trade = result.scalars().first()
            trade_quantity = trade.quantity
            trade_symbol = trade.symbol
            trade_strategy = trade.strategy
            trade_side = trade.side
            logger.info(
                'Updating positions',
                extra={
                    'trade': trade,
                    'quantity': trade_quantity,
                    'symbol': trade_symbol,
                    'strategy': trade_strategy,
                    'side': trade_side})

            if trade.quantity == 0:
                logger.error(
                    'Trade quantity is 0, doing nothing', extra={
                        'trade': trade})
                return

            # Query the current position for the trade's symbol, broker, and
            # strategy
            result = await session.execute(
                select(Position).filter_by(symbol=trade.symbol,
                                           broker=self.broker_name, strategy=trade.strategy)
            )
            position = result.scalars().first()
            logger.debug(f"Queried position: {position}")

            # Initialize profit/loss
            profit_loss = 0

            # Handling Buy Orders
            if 'buy' in trade.side:
                if position and position.quantity < 0:  # This is a short cover
                    logger.info(
                        'Processing short cover',
                        extra={
                            'trade_quantity': trade_quantity,
                            'position_quantity': position.quantity,
                            'trade_symbol': trade_symbol,
                            'strategy': trade_strategy})

                    # Calculate P/L for short cover (covering short position)
                    cost_per_share = position.cost_basis / \
                        abs(position.quantity)
                    profit_loss = (
                        cost_per_share - float(trade.executed_price)) * abs(trade.quantity)
                    logger.info(
                        f'Short cover profit/loss calculated: {profit_loss}',
                        extra={
                            'trade_quantity': trade_quantity,
                            'position_quantity': position.quantity,
                            'trade_symbol': trade_symbol,
                            'strategy': trade_strategy,
                            'profit_loss': profit_loss,
                            'cost_per_share': cost_per_share})

                    # Update or remove the short position
                    if abs(position.quantity) == trade.quantity:
                        logger.info(
                            'Fully covering short position, removing position',
                            extra={
                                'trade_quantity': trade_quantity,
                                'position_quantity': position.quantity,
                                'trade_symbol': trade_symbol,
                                'strategy': trade_strategy,
                                'profit_loss': profit_loss,
                                'cost_per_share': cost_per_share})
                        await session.delete(position)
                    else:
                        logger.info(
                            'Partially covering short position',
                            extra={
                                'trade_quantity': trade_quantity,
                                'position_quantity': position.quantity,
                                'trade_symbol': trade_symbol,
                                'strategy': trade_strategy,
                                'profit_loss': profit_loss,
                                'cost_per_share': cost_per_share})
                        position.cost_basis -= cost_per_share * \
                            abs(trade.quantity)
                        position.quantity += trade.quantity  # Add back the covered quantity
                        position.latest_price = float(trade.executed_price)
                        position.timestamp = datetime.now()
                        logger.info(
                            'Updating position with new quantity and cost basis',
                            extra={
                                'position': position,
                                'trade_quantity': trade_quantity,
                                'position_quantity': position.quantity,
                                'cost_basis': position.cost_basis,
                                'trade_symbol': trade_symbol,
                                'strategy': trade_strategy,
                                'profit_loss': profit_loss,
                                'cost_per_share': cost_per_share})
                        session.add(position)
                    trade.profit_loss = profit_loss
                    session.add(trade)

                else:  # Regular Buy
                    logger.info(
                        'Processing regular buy order',
                        extra={
                            'trade_quantity': trade_quantity,
                            'trade_symbol': trade_symbol})
                    if position:
                        # Update existing position
                        cost_increment = float(
                            trade.executed_price) * trade.quantity
                        if is_option(trade.symbol):
                            position.cost_basis += cost_increment * OPTION_MULTIPLIER
                        elif is_futures_symbol(trade.symbol):
                            multiplier = futures_contract_size(trade.symbol)
                            position.cost_basis += cost_increment * multiplier
                        else:
                            position.cost_basis += cost_increment
                        position.quantity += trade.quantity
                        position.latest_price = float(trade.executed_price)
                        position.timestamp = datetime.now()
                        session.add(position)
                    else:
                        # Create a new position
                        position = Position(
                            broker=self.broker_name,
                            strategy=trade.strategy,
                            symbol=trade.symbol,
                            quantity=trade.quantity,
                            latest_price=float(
                                trade.executed_price),
                            cost_basis=float(
                                trade.executed_price) *
                            trade.quantity,
                        )
                        session.add(position)

            # Handling Sell Orders
            elif 'sell' in trade.side:
                logger.info('Processing sell order', extra={'trade': trade})

                # Short sales
                if position:
                    cost_per_share = position.cost_basis / position.quantity
                    profit_loss = (float(trade.executed_price) -
                                   cost_per_share) * trade.quantity
                    logger.info(
                        f'Sell order profit/loss calculated: {profit_loss}',
                        extra={
                            'trade': trade,
                            'position': position})

                    if position.quantity == trade.quantity:  # Full sell
                        logger.info(
                            'Deleting sold position', extra={
                                'position': position})
                        await session.delete(position)
                    else:  # Partial sell
                        position.cost_basis -= trade.quantity * cost_per_share
                        position.quantity -= trade.quantity
                        position.latest_price = float(trade.executed_price)
                        session.add(position)
                    trade.profit_loss = profit_loss
                    session.add(trade)
                elif position is None:
                    logger.info(
                        'Short sale detected',
                        extra={
                            'trade': trade,
                            'quantity': trade.quantity,
                            'symbol': trade.symbol})
                    quantity = -abs(trade.quantity)
                    position = Position(
                        broker=self.broker_name,
                        strategy=trade.strategy,
                        symbol=trade.symbol,
                        quantity=quantity,
                        latest_price=float(
                            trade.executed_price),
                        cost_basis=float(
                            trade.executed_price) *
                        trade.quantity,
                    )
                    session.add(position)

            # Commit the transaction
            await session.commit()

            logger.info('Position updated', extra={'position': position})

        except Exception as e:
            logger.error('Failed to update positions', extra={'error': str(e)})
            await session.rollback()

    async def place_future_option_order(
            self,
            symbol,
            quantity,
            side,
            strategy,
            price=None,
            order_type='limit'):
        multiplier = futures_contract_size(symbol)
        return await self._place_order_generic(
            symbol, quantity, side, strategy, price, multiplier, self._place_future_option_order, order_type
        )

    async def place_option_order(
            self,
            symbol,
            quantity,
            side,
            strategy,
            price=None,
            order_type='limit'):
        multiplier = OPTION_MULTIPLIER
        return await self._place_order_generic(
            symbol, quantity, side, strategy, price, multiplier, self._place_option_order, order_type
        )

    async def place_order(
            self,
            symbol,
            quantity,
            side,
            strategy,
            price=None,
            order_type='limit'):
        multiplier = 1  # Regular stock orders don't have a multiplier
        return await self._place_order_generic(
            symbol, quantity, side, strategy, price, multiplier, self._place_order, order_type
        )

    async def _place_order_generic(
            self,
            symbol,
            quantity,
            side,
            strategy,
            price,
            multiplier,
            broker_order_func,
            order_type='limit'):
        '''Generic method to place an order and update database'''
        logger.info(
            'Placing order',
            extra={
                'symbol': symbol,
                'quantity': quantity,
                'side': side,
                'strategy': strategy})
        if self.prevent_day_trading and side == 'sell' and await self.has_bought_today(symbol):
            logger.error(
                'Day trading is not allowed. Cannot sell positions opened today.',
                extra={
                    'symbol': symbol})
            return None

        try:
            if asyncio.iscoroutinefunction(broker_order_func):
                response = await broker_order_func(symbol, quantity, side, price, order_type)
            else:
                response = broker_order_func(
                    symbol, quantity, side, price, order_type)

            logger.info(
                'Order placed successfully',
                extra={
                    'response': response,
                    'symbol': symbol,
                    'quantity': quantity,
                    'side': side,
                    'strategy': strategy})

            # Extract price if not given
            if not price:
                price = response.get('filled_price', None)

            trade = Trade(
                symbol=symbol,
                quantity=quantity,
                price=price,
                executed_price=price,
                side=side,
                status='open',
                timestamp=datetime.now(),
                broker=self.broker_name,
                strategy=strategy,
                profit_loss=0,
                success='yes'
            )

            # Update the trade and positions in the database
            async with self.Session() as session:
                session.add(trade)
                await session.flush()
                await self.update_positions(trade.id, session)
                await session.commit()

                # Update balance
                latest_balance = await session.execute(
                    select(Balance).filter_by(
                        broker=self.broker_name, strategy=strategy, type='cash'
                    ).order_by(Balance.timestamp.desc())
                )
                latest_balance = latest_balance.scalars().first()
                if latest_balance:
                    order_cost = price * quantity * multiplier
                    new_balance_amount = latest_balance.balance - \
                        order_cost if side == 'buy' else latest_balance.balance + order_cost

                    new_balance = Balance(
                        broker=self.broker_name,
                        strategy=strategy,
                        type='cash',
                        balance=new_balance_amount,
                        timestamp=datetime.now()
                    )
                    session.add(new_balance)
                    await session.commit()

            return response
        except Exception as e:
            logger.error('Failed to place order', extra={'error': str(e)})
            return None

    async def get_order_status(self, order_id):
        '''Get the status of an order'''
        logger.info('Retrieving order status', extra={'order_id': order_id})
        try:
            order_status = self._get_order_status(order_id)
            async with self.Session() as session:
                trade = await session.execute(session.query(Trade).filter_by(id=order_id))
                trade = trade.scalars().first()
                if trade:
                    await self.update_trade(session, trade.id, order_status)
            logger.info(
                'Order status retrieved', extra={
                    'order_status': order_status})
            return order_status
        except Exception as e:
            logger.error('Failed to get order status', extra={'error': str(e)})
            return None

    async def cancel_order(self, order_id):
        '''Cancel an order'''
        logger.info('Cancelling order', extra={'order_id': order_id})
        try:
            cancel_status = self._cancel_order(order_id)
            async with self.Session() as session:
                trade = await session.execute(session.query(Trade).filter_by(id=order_id))
                trade = trade.scalars().first()
                if trade:
                    await self.update_trade(session, trade.id, cancel_status)
            logger.info(
                'Order cancelled successfully', extra={
                    'cancel_status': cancel_status})
            return cancel_status
        except Exception as e:
            logger.error('Failed to cancel order', extra={'error': str(e)})
            return None

    def position_exists(self, symbol):
        '''Check if a position exists for a symbol in the brokerage account'''
        positions = self.get_positions()
        return symbol in positions

    def get_options_chain(self, symbol, expiration_date):
        '''Get the options chain for a symbol'''
        logger.info(
            'Retrieving options chain',
            extra={
                'symbol': symbol,
                'expiration_date': expiration_date})
        try:
            options_chain = self._get_options_chain(symbol, expiration_date)
            logger.info(
                'Options chain retrieved', extra={
                    'options_chain': options_chain})
            return options_chain
        except Exception as e:
            logger.error(
                'Failed to retrieve options chain', extra={
                    'error': str(e)})
            return None

    async def update_trade(self, session, trade_id, order_info):
        '''Update the trade with the order information'''
        try:
            trade = await session.execute(session.query(Trade).filter_by(id=trade_id))
            trade = trade.scalars().first()
            if not trade:
                logger.error(
                    'Trade not found for update', extra={
                        'trade_id': trade_id})
                return

            executed_price = order_info.get('filled_price', trade.price)
            trade.executed_price = executed_price
            success = "success" if trade.profit_loss > 0 else "failure"

            trade.executed_price = executed_price
            trade.success = success
            await session.commit()
            logger.info('Trade updated', extra={'trade': trade})
        except Exception as e:
            logger.error('Failed to update trade', extra={'error': str(e)})
