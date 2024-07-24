from utils.utils import futures_contract_size
import unittest
from unittest.mock import patch

class TestFuturesContractSize(unittest.TestCase):
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

if __name__ == '__main__':
    unittest.main()

