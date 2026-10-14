import json
import math
import random
import unittest
from backend.quant import analyze, at_quote, _decision


def candles(n=160, predictive=False):
    rng = random.Random(42)
    price = 1800.0
    previous_volume = 100
    out = []
    for i in range(n):
        price += (0.9 * (math.log1p(previous_volume)-4.3) if predictive else 0) + rng.gauss(0,.1)
        volume = rng.choice([20,50,100,200,400])
        out.append(dict(time=1700000000+i*60, close=price, volume=volume))
        previous_volume = volume
    return out


class QuantTests(unittest.TestCase):
    def test_flat_data_has_no_invented_edge(self):
        data = candles()
        for c in data: c['close'] = 1800
        q = at_quote(analyze(data),1800)
        self.assertEqual(q['status'],'ready')
        self.assertEqual(q['suggestion'],'wait')
        self.assertEqual(q['rmse_points'],0)
        self.assertIsNone(q['z_score'])
        self.assertEqual(q['probability_up'],.5)
        json.dumps(q,allow_nan=False)
        self.assertFalse(any(k.startswith('_') for k in q))

    def test_missing_data_and_gaps_do_not_create_forecast(self):
        self.assertEqual(analyze(candles(30))['status'],'insufficient')
        data = candles()
        data[-1]['time'] += 600
        self.assertEqual(analyze(data)['status'],'insufficient')
        data[-1]['close'] = float('nan')
        self.assertEqual(analyze(data)['status'],'insufficient')

    def test_lagged_volume_can_improve_later_forecasts(self):
        q = analyze(candles(predictive=True))
        self.assertEqual(q['selected'],'arx')
        self.assertGreater(q['skill_pct'],30)
        self.assertEqual(q['n_selection'],12)
        self.assertEqual(q['n_audit'],40)
        self.assertLess(q['interval80'][0],q['interval80'][1])

    def test_forecast_is_compared_with_actual_quote(self):
        q = analyze(candles(predictive=True))
        near = at_quote(q,q['forecast_price'])
        self.assertEqual(near['delta_points'],0)
        self.assertEqual(near['suggestion'],'wait')
        self.assertAlmostEqual(near['expected_net_points'],-.24)
        above = at_quote(q,q['forecast_price']+1)
        self.assertEqual(above['delta_points'],-1)
        self.assertEqual(q['forecast_price'],above['forecast_price'])

    def test_fees_and_bad_skill_block_suggestions(self):
        audit = [0]*40
        self.assertEqual(_decision(.1,.01,1,audit)['suggestion'],'wait')
        self.assertEqual(_decision(2,1,1,audit)['suggestion'],'wait')
        self.assertEqual(_decision(2,.1,1,audit)['suggestion'],'long')
