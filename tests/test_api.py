import os
import json
import tempfile
import time
import unittest
from unittest.mock import patch

temp = tempfile.TemporaryDirectory()
os.environ['ARENA_DATA_DIR'] = temp.name
from fastapi.testclient import TestClient
from backend import server
from backend.provider import fresh, normalize


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(server.app)

    def start(self):
        response = self.client.post('/api/games', json=dict(name='Test <script>', mode='practice'))
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_hidden_future_candles_and_finish_lock(self):
        g = self.start()
        self.assertEqual(len(g['candles']), 30)
        self.assertFalse(g['market']['genuine'])
        self.assertNotIn('owner', g)
        self.assertNotIn('actions', g)
        self.assertNotIn('candles', g['market'])
        self.assertEqual(g['seconds_left'], 180)
        result = self.client.post(f"/api/games/{g['id']}/orders", json=dict(side='long', qty=1, action_id='first-trade')).json()
        self.assertEqual(result['account']['qty'], 1)
        finished = self.client.post(f"/api/games/{g['id']}/finish").json()
        self.assertTrue(finished['done'])
        self.assertEqual(finished['account']['qty'], 0)
        self.assertEqual(self.client.post(f"/api/games/{g['id']}/orders", json=dict(side='long', qty=1, action_id='late-trade')).status_code, 409)
        scores = self.client.get('/api/leaderboard', params={'scenario':g['scenario']}).json()
        self.assertTrue(any(s['name'] == 'Test <script>' for s in scores))

    def test_session_isolation_and_idempotent_order(self):
        g = self.start()
        intruder = TestClient(server.app)
        self.assertEqual(intruder.get(f"/api/games/{g['id']}").status_code, 404)
        body = dict(side='long', qty=1, action_id='one-request-only')
        self.client.post(f"/api/games/{g['id']}/orders", json=body)
        second = self.client.post(f"/api/games/{g['id']}/orders", json=body).json()
        self.assertEqual(len(second['account']['trades']), 1)
        self.assertEqual(second['account']['qty'], 1)

    def test_clock_advances_and_auto_settles_without_ui(self):
        g = self.start()
        self.client.post(f"/api/games/{g['id']}/orders", json=dict(side='short', qty=1, action_id='open-short'))
        with server.lock:
            original = json.loads(server.db.execute('SELECT body FROM games WHERE id=?', (g['id'],)).fetchone()[0])
            original['started'] -= 181
            original['deadline'] -= 181
            server.save(original)
        final = self.client.get(f"/api/games/{g['id']}").json()
        self.assertTrue(final['done'])
        self.assertEqual(len(final['candles']), 90)
        self.assertEqual(final['account']['qty'], 0)
        self.assertEqual(final['end_reason'], 'time_up')

    def test_true_source_failure_does_not_fall_back_to_synthetic(self):
        with patch.object(server.provider, 'get', side_effect=ValueError('Nguồn lỗi')), patch.object(server, 'practice') as sample:
            for mode in ('live','replay'):
                response = self.client.post('/api/games', json=dict(name='Real', mode=mode))
                self.assertEqual(response.status_code, 503)
            sample.assert_not_called()

    def test_live_stale_rejection_and_subsequent_freeze(self):
        snap = {**server.practice(), 'genuine':True, 'source':'TEST FIXTURE', 'data_as_of':int(time.time())}
        with patch.object(server.provider, 'get', return_value=snap):
            response = self.client.post('/api/games', json=dict(name='Live', mode='live'))
            self.assertEqual(response.status_code, 200)
            g = response.json()
        stale = {**snap, 'data_as_of':int(time.time())-180}
        with patch.object(server.provider, 'get', return_value=stale):
            order = self.client.post(f"/api/games/{g['id']}/orders", json=dict(side='long', qty=1, action_id='stale-order'))
            self.assertEqual(order.status_code, 409)
            response = self.client.post('/api/games', json=dict(name='Live', mode='live'))
            self.assertEqual(response.status_code, 409)
        self.assertFalse(fresh({**snap, 'error':'network failure'}))

    def test_input_limits_and_static_serving(self):
        self.assertEqual(self.client.get('/').status_code, 200)
        self.assertEqual(self.client.get('/api/health').json()['symbol'], 'VN30F1M')
        self.assertEqual(self.client.post('/api/games', json=dict(name='x'*25,mode='practice')).status_code, 422)
        self.assertEqual(self.client.post('/api/games', json=dict(name='x',mode='fake')).status_code, 422)


class DataTests(unittest.TestCase):
    def test_timezone_prices_and_ohlc_validation(self):
        rows = [dict(time=f'2026-10-09T09:{i:02d}:00',open=1800,high=1802,low=1799,close=1801,volume=40) for i in range(40)]
        result = normalize(rows)
        self.assertEqual(result[0]['time'], 1791511200)
        self.assertEqual(result[0]['close'], 1801)  # points, not VND or thousands
        rows[0]['close'] = float('nan')
        with self.assertRaises(ValueError):
            normalize(rows)


if __name__ == '__main__':
    unittest.main()
