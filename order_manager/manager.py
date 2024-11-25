from database.db_manager import DBManager

class OrderManager:
    async def __init__(self, engine, brokers):
        self.db_manager = DBManager(engine)
        self.brokers = brokers

    async def reconcile_orders(orders):
        for order in orders:
            await self.reconcile_order(order)

    async def reconcile_order(order):
        broker = self.brokers[order.broker]
        # TODO: handle partial fill
        filled = await broker.is_order_filled(order)
        if filled:
            await self.db_manager.set_trade_filled(order.id)

    async def run(self):
        orders = await self.db_manager.get_open_trades()
        await self.reconcile_orders(orders)

async def run(engine, brokers):
    order_manager = OrderManager(engine, brokers)
    await order_manager.run()
