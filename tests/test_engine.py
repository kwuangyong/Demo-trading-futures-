import unittest
from copy import deepcopy
from backend.engine import account, flatten, metrics, risk_check, trade


class AccountingTests(unittest.TestCase):
    def test_long_profit_in_vnd_includes_both_fees_and_slippage(self):
        a = account()
        trade(a, 1, 2, 18000)
        self.assertEqual(a['entry'], 18001)
        self.assertEqual(metrics(a, 18050)['unrealized'], 980000)
        flatten(a, 18050)
        self.assertEqual(a['cash'], 100_952_000)
        self.assertEqual(a['qty'], 0)
        self.assertEqual(a['fees'], 8000)

    def test_short_profit_and_reversal_account_for_closed_portion(self):
        a = account()
        trade(a, -1, 2, 18000)
        trade(a, 1, 3, 17950)
        self.assertEqual(a['qty'], 1)
        self.assertEqual(a['entry'], 17951)
        self.assertEqual(a['cash'], 100_950_000)
        self.assertEqual(a['trades'][-1]['realized'], 960000)

    def test_partial_close_preserves_cost_basis(self):
        a = account()
        trade(a, 1, 2, 18000)
        trade(a, -1, 1, 18030)
        self.assertEqual(a['qty'], 1)
        self.assertEqual(a['entry'], 18001)
        self.assertEqual(a['cash'], 100_274_000)

    def test_rejected_margin_order_is_atomic(self):
        a = account()
        original = deepcopy(a)
        with self.assertRaises(ValueError):
            trade(a, 1, 4, 18000)
        self.assertEqual(a, original)

    def test_weighted_average_and_flat_trade_returns_only_costs(self):
        a = account()
        trade(a, 1, 1, 18000)
        trade(a, 1, 1, 18020)
        self.assertEqual(a['entry'], 18011)
        flatten(a, 18010)
        self.assertEqual(a['cash'], 99_952_000)

    def test_margin_call_and_close_when_account_has_negative_available(self):
        a = account()
        trade(a, 1, 3, 18000)
        self.assertTrue(risk_check(a, 16600))
        self.assertEqual(a['qty'], 0)
        self.assertEqual(a['liquidations'], 1)
        self.assertFalse(risk_check(a, 16000))

    def test_bad_quantities_do_not_mutate(self):
        for qty in (0, -1, True, 1.5, 51):
            a = account()
            with self.assertRaises(ValueError):
                trade(a, 1, qty, 18000)
            self.assertEqual(a, account())


if __name__ == '__main__':
    unittest.main()
