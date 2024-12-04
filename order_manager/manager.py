from database.db_manager import DBManager
from utils.logger import logger
from datetime import datetime, timedelta

MARK_ORDER_STALE_AFTER = 60 * 60 * 24 * 2 # 2 days

class OrderManager:
    def __init__(self, engine, brokers):
        logger.info('Initializing OrderManager')
        self.engine = engine
        self.db_manager = DBManager(engine)
        self.brokers = brokers

    async def update_positions(self, order, session):
        '''Update positions based on the filled order.'''
        logger.info(f'Updating positions for order {order.id}', extra={
            'order_id': order.id,
            'symbol': order.symbol,
            'quantity': order.quantity,
            'side': order.side,
            'executed_price': order.price
        })

        try:
            # Fetch the current position for the symbol
            result = await session.execute(
                select(Position).filter_by(symbol=order.symbol, broker=order.broker)
            )
            position = result.scalars().first()

            # Initialize profit/loss
            profit_loss = 0

            if order.side == 'buy':
                if position and position.quantity < 0:  # Short cover
                    # Calculate P/L for short cover
                    cost_per_share = position.cost_basis / abs(position.quantity)
                    profit_loss = (cost_per_share - order.price) * abs(order.quantity)

                    # Update or delete the short position
                    if abs(position.quantity) == order.quantity:
                        await session.delete(position)
                    else:
                        position.cost_basis -= cost_per_share * abs(order.quantity)
                        position.quantity += order.quantity
                        position.latest_price = order.price
                        session.add(position)
                else:  # Regular buy
                    if position:
                        # Update existing position
                        position.cost_basis += order.price * order.quantity
                        position.quantity += order.quantity
                        position.latest_price = order.price
                        session.add(position)
                    else:
                        # Create a new position
                        position = Position(
                            broker=order.broker,
                            symbol=order.symbol,
                            quantity=order.quantity,
                            latest_price=order.price,
                            cost_basis=order.price * order.quantity,
                            timestamp=datetime.utcnow()
                        )
                        session.add(position)
            elif order.side == 'sell':
                if position:
                    # Calculate P/L for sell
                    cost_per_share = position.cost_basis / position.quantity
                    profit_loss = (order.price - cost_per_share) * order.quantity

                    if position.quantity == order.quantity:  # Full sell
                        await session.delete(position)
                    else:  # Partial sell
                        position.cost_basis -= cost_per_share * order.quantity
                        position.quantity -= order.quantity
                        position.latest_price = order.price
                        session.add(position)
                else:
                    # Short sale
                    position = Position(
                        broker=order.broker,
                        symbol=order.symbol,
                        quantity=-order.quantity,
                        latest_price=order.price,
                        cost_basis=order.price * order.quantity,
                        timestamp=datetime.utcnow()
                    )
                    session.add(position)

            order.profit_loss = profit_loss
            session.add(order)
            await session.commit()

            logger.info('Positions updated successfully', extra={'order_id': order.id, 'profit_loss': profit_loss})
        except Exception as e:
            logger.error(f'Failed to update positions for order {order.id}', extra={'error': str(e)})
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
