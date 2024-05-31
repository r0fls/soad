from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.models import Trade, AccountInfo, Balance, init_db
import unittest

class BaseTest(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine('sqlite:///:memory:')
        init_db(cls.engine)
        cls.Session = sessionmaker(bind=cls.engine)
        cls.session = cls.Session()

    @classmethod
    def tearDownClass(cls):
        cls.session.close()
        cls.engine.dispose()

    def setUp(self):
        self.session = self.Session()
    
    def tearDown(self):
        self.session.rollback()
        self.session.close()
