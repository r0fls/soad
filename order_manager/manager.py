from database.db_manager import DBManager
from utils.logger import logger

class OrderManager:
    async def __init__(self, engine, brokers):
        logger.info('Initializing OrderManager')
        self.db_manager = DBManager(engine)
        self.brokers = brokers

    async def reconcile_orders(self, orders):
        logger.info('Reconciling orders', extra={'orders': orders})
        for order in orders:
            await self.reconcile_order(order)

    async def reconcile_order(self, order):
        logger.info(f'Reconciling order {order.id}', extra={'order_id': order.id, 'broker': order.broker, 'symbol': order.symbol, 'quantity': order.quantity, 'price': order.price, 'side': order.side, 'status': order.status, 'type': order.type, 'time_in_force': order.time_in_force, 'created_at': order.created_at, 'updated_at': order.updated_at, 'filled_at': order.filled_at, 'filled_quantity': order.filled_quantity, 'remaining_quantity': order.remaining_quantity, 'canceled_at': order.canceled_at, 'failed_at': order.failed_at, 'message': order.message})
        broker = self.brokers[order.broker]
        # TODO: handle partial fill
        filled = await broker.is_order_filled(order)
        if filled:
            await self.db_manager.set_trade_filled(order.id)

    async def run(self):
        logger.info('Running OrderManager')
        orders = await self.db_manager.get_open_trades()
        await self.reconcile_orders(orders)

async def run(engine, brokers):
    order_manager = OrderManager(engine, brokers)
    await order_manager.run()
