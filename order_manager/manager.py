from database.db_manager import DBManager
from utils.logger import logger
from datetime import datetime, timedelta
from sqlalchemy import select
from database.models import Position, Trade

MARK_ORDER_STALE_AFTER = 60 * 60 * 24 * 2 # 2 days
PEGGED_ORDER_CANCEL_AFTER = 15 # 15 seconds

class OrderManager:
    def __init__(self, engine, brokers):
        logger.info('Initializing OrderManager')
        self.engine = engine
        self.db_manager = DBManager(engine)
        self.brokers = brokers

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
        if order.timestamp < stale_threshold and order.status not in ['filled', 'cancelled', 'stale', 'rejected']:
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
                    await broker.update_positions(order.id, session)
            except Exception as e:
                logger.error(f'Error reconciling order {order.id}', extra={'error': str(e)})
        status = await broker.get_order_status(order.broker_id)
        if status == 'rejected':
            try:
                logger.info(f'Marking order {order.id} as rejected', extra={'order_id': order.id})
                await self.db_manager.update_trade_status(order.id, 'rejected')
            except Exception as e:
                logger.error(f'Error marking order {order.id} as rejected', extra={'error': str(e)})
            return

        elif order.execution_style == 'pegged':
            cancel_threshold = datetime.utcnow() - timedelta(seconds=PEGGED_ORDER_CANCEL_AFTER)
            if order.timestamp < cancel_threshold:
                try:
                    logger.info(f'Cancelling pegged order {order.id}', extra={'order_id': order.id})
                    mid_price = await broker.get_mid_price(order.symbol)
                    await broker.cancel_order(order.broker_id)
                    await self.db_manager.update_trade_status(order.id, 'cancelled')
                    await broker.place_order(
                        symbol=order.symbol,
                        quantity=order.quantity,
                        side=order.side,
                        strategy=order.strategy,
                        price=round(mid_price, 2),
                        order_type='limit',
                        execution_style=order.execution_style
                    )
                except Exception as e:
                    logger.error(f'Error cancelling pegged order {order.id}', extra={'error': str(e)})

    async def run(self):
        logger.info('Running OrderManager')
        orders = await self.db_manager.get_open_trades()
        await self.reconcile_orders(orders)

async def run_order_manager(engine, brokers):
    order_manager = OrderManager(engine, brokers)
    await order_manager.run()
