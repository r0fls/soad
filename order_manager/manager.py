from database.db_manager import DBManager
from utils.logger import logger
from datetime import datetime, timedelta
from sqlalchemy import select
from database.models import Position, Trade

MARK_ORDER_STALE_AFTER = 60 * 60 * 24 * 2 # 2 days

class OrderManager:
    def __init__(self, engine, brokers):
        logger.info('Initializing OrderManager')
        self.engine = engine
        self.db_manager = DBManager(engine)
        self.brokers = brokers

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


    async def reconcile_orders(self, orders):
        logger.info('Reconciling orders', extra={'orders': orders})
        for order in orders:
            await self.reconcile_order(order)
        # Commit the transaction

    async def reconcile_order(self, order):
        logger.info(f'Reconciling order {order.id}', extra={
            'order_id': order.id,
            'broker_id': order.broker_id,
            'broker': order.broker,
            'symbol': order.symbol,
            'quantity': order.quantity,
            'price': order.price,
            'side': order.side,
            'status': order.status
        })

        # Calculate the stale threshold
        stale_threshold = datetime.utcnow() - timedelta(seconds=MARK_ORDER_STALE_AFTER)

        # Check if the order is stale
        if order.timestamp < stale_threshold and order.status not in ['filled', 'canceled']:
            try:
                logger.info(f'Marking order {order.id} as stale', extra={'order_id': order.id})
                await self.db_manager.update_trade_status(order.id, 'stale')
                return  # Exit early if the order is stale
            except Exception as e:
                logger.error(f'Error marking order {order.id} as stale', extra={'error': str(e)})
                return

        # If the order is not stale, reconcile it
        broker = self.brokers[order.broker]
        if order.broker_id is None:
            # If the order has no broker_id, mark it as stale
            logger.info(f'Marking order {order.id} as stale, missing broker_id', extra={'order_id': order.id})
            await self.db_manager.update_trade_status(order.id, 'stale')
            return
        filled = await broker.is_order_filled(order.broker_id)
        if filled:
            try:
                async with self.db_manager.Session() as session:
                    await self.db_manager.set_trade_filled(order.id)
                    await self.update_positions(order, session)
            except Exception as e:
                logger.error(f'Error reconciling order {order.id}', extra={'error': str(e)})

    async def run(self):
        logger.info('Running OrderManager')
        orders = await self.db_manager.get_open_trades()
        await self.reconcile_orders(orders)

async def run_order_manager(engine, brokers):
    order_manager = OrderManager(engine, brokers)
    await order_manager.run()
