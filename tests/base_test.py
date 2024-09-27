from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from database.models import Trade, AccountInfo, Balance, init_db
import unittest

class BaseTest(unittest.TestCase):

    @classmethod
    async def asyncSetUpClass(cls):
        pass

    @classmethod
    async def asyncTearDownClass(cls):
        pass

    async def asyncSetUp(self):
        self.engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        await init_db(cls.engine)
        self.Session = sessionmaker(bind=cls.engine, class_=AsyncSession)
        self.session = self.Session()

    async def asyncTearDown(self):
        self.session.close()
        self.engine.dispose()
