from database.db_manager import DBManager
from utils.logger import logger

MARK_ORDER_STALE_AFTER = 60 * 60 * 24 * 2 # 2 days

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
        filled = await broker.is_order_filled(order.id)
        if filled:
            try:
                await self.db_manager.set_trade_filled(order.id)
            except Exception as e:
                logger.error(f'Error reconciling order {order.id}', extra={'error': str(e)})

    async def run(self):
        logger.info('Running OrderManager')
        orders = await self.db_manager.get_open_trades()
        await self.reconcile_orders(orders)

async def run_order_manager(engine, brokers):
    order_manager = OrderManager(engine, brokers)
    await order_manager.run()
