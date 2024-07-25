from utils.utils import futures_contract_size, is_futures_market_open, is_futures_symbol
import unittest
from unittest.mock import patch
from freezegun import freeze_time

class TestFuturesContractSize(unittest.TestCase):
    def test_is_futures_symbol(self):
        # Test cases for valid futures option symbols
        self.assertTrue(is_futures_symbol('./ESU4'))
        self.assertTrue(is_futures_symbol('./MNQU4D4DN4 240725P19300'))
        self.assertTrue(is_futures_symbol('./CLU4 240725P19300'))
        # Test cases for invalid futures option symbols
        self.assertFalse(is_futures_symbol('AAPL'))
        # TODO: fix
        #self.assertFalse(is_futures_symbol('./INVALID SYMBOL'))
        self.assertFalse(is_futures_symbol('ESU4'))


    def test_known_symbols(self):
        self.assertEqual(futures_contract_size('./ESU4'), 50)
        self.assertEqual(futures_contract_size('./NQU4'), 20)
        self.assertEqual(futures_contract_size('./MESU4'), 5)
        self.assertEqual(futures_contract_size('./MNQU4'), 2)
        self.assertEqual(futures_contract_size('./RTYU4'), 50)
        self.assertEqual(futures_contract_size('./M2KU4'), 10)
        self.assertEqual(futures_contract_size('./YMU4'), 5)
        self.assertEqual(futures_contract_size('./MYMU4'), 2)
        self.assertEqual(futures_contract_size('./ZBU4'), 1000)
        self.assertEqual(futures_contract_size('./ZNU4'), 1000)
        self.assertEqual(futures_contract_size('./ZTU4'), 2000)
        self.assertEqual(futures_contract_size('./ZFU4'), 1000)
        self.assertEqual(futures_contract_size('./ZCU4'), 50)
        self.assertEqual(futures_contract_size('./ZSU4'), 50)
        self.assertEqual(futures_contract_size('./ZWU4'), 50)
        self.assertEqual(futures_contract_size('./ZLU4'), 50)
        self.assertEqual(futures_contract_size('./ZMU4'), 50)
        self.assertEqual(futures_contract_size('./ZRU4'), 50)
        self.assertEqual(futures_contract_size('./ZKU4'), 50)
        self.assertEqual(futures_contract_size('./ZOU4'), 50)
        self.assertEqual(futures_contract_size('./ZVU4'), 1000)
        self.assertEqual(futures_contract_size('./HEU4'), 40000)
        self.assertEqual(futures_contract_size('./LEU4'), 40000)
        self.assertEqual(futures_contract_size('./CLU4'), 1000)
        self.assertEqual(futures_contract_size('./GCU4'), 100)
        self.assertEqual(futures_contract_size('./SIU4'), 5000)
        self.assertEqual(futures_contract_size('./6EU4'), 125000)

    @patch('utils.utils.logger')
    def test_unknown_symbol(self, mock_logger):
        self.assertEqual(futures_contract_size('./XYZU4'), 1)
        mock_logger.error.assert_called_once_with("Unknown future symbol: ./XYZU4")

class TestIsFuturesMarketOpen(unittest.TestCase):
    @freeze_time("2024-07-22 13:00:00")  # A Monday at 1:00 PM Eastern Time
    def test_futures_market_open(self):
        self.assertTrue(is_futures_market_open())

    @freeze_time("2024-07-22 18:00:00")  # A Monday at 6:00 PM Eastern Time
    def test_futures_market_open_evening(self):
        self.assertTrue(is_futures_market_open())

    @freeze_time("2024-07-20 13:00:00")  # A Saturday at 1:00 PM Eastern Time
    def test_futures_market_closed_saturday(self):
        self.assertFalse(is_futures_market_open())

    @freeze_time("2024-07-21 17:00:00")  # A Sunday at 5:00 PM Eastern Time
    def test_futures_market_closed_sunday_before_open(self):
        self.assertFalse(is_futures_market_open())

    # TODO: fix
    @freeze_time("2024-07-21 18:30:00")  # A Sunday at 6:30 PM Eastern Time
    def skip_test_futures_market_open_sunday_evening(self):
        self.assertTrue(is_futures_market_open())

    @freeze_time("2024-07-23 17:30:00")  # A Tuesday at 5:30 PM Eastern Time
    def skip_test_futures_market_closed_weekday_after_close(self):
        self.assertFalse(is_futures_market_open())

    @freeze_time("2024-07-23 16:30:00")  # A Tuesday at 4:30 PM Eastern Time
    def test_futures_market_open_weekday_afternoon(self):
        self.assertTrue(is_futures_market_open())

if __name__ == '__main__':
    unittest.main()
