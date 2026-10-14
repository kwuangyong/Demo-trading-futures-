import json
import os
import subprocess
import unittest
from unittest.mock import patch

from backend.diagnostics import safe_detail
from backend.provider import Provider


class ProviderChecks(unittest.TestCase):
    def test_source_failure_does_not_create_a_snapshot_and_reports_safe_error(self):
        process = subprocess.CompletedProcess([], 1, '', 'RuntimeError: rejected api_key=super-secret\n')
        with patch.dict(os.environ, {'VNSTOCK_PACKAGE':'vnstock','VNSTOCK_API_KEY':'super-secret'}), \
             patch('backend.provider.importlib.util.find_spec', return_value=object()), \
             patch('backend.provider.subprocess.run', return_value=process):
            p = Provider()
            with self.assertRaisesRegex(ValueError, 'REDACTED'):
                p.get()
            self.assertIsNone(p.snapshot)
            self.assertNotIn('super-secret', p.error)

    def test_failed_refresh_retains_only_the_previously_fetched_genuine_data(self):
        rows = [dict(time=f'2026-10-09T09:{i:02d}:00+07:00',open=1800,high=1802,low=1799,close=1801,volume=40) for i in range(40)]
        success = subprocess.CompletedProcess([], 0, 'ARENA_DATA: '+json.dumps({'source':'vnstock / vci','candles':rows}), '')
        failure = subprocess.CompletedProcess([], 1, '', 'ConnectionError: source unavailable')
        with patch.dict(os.environ, {'VNSTOCK_PACKAGE':'vnstock'}), \
             patch('backend.provider.importlib.util.find_spec', return_value=object()), \
             patch('backend.provider.subprocess.run', side_effect=[success, failure]):
            p = Provider()
            first = p.get()
            p.next_fetch = 0
            cached = p.get()
            self.assertEqual(cached['candles'], first['candles'])
            self.assertTrue(cached['genuine'])
            self.assertTrue(cached['cached'])
            self.assertIn('ConnectionError', cached['error'])

    def test_error_redacts_environment_key_url_query_and_bearer(self):
        with patch.dict(os.environ, {'VNSTOCK_API_KEY':'secret/key'}):
            for text in ('ValueError: secret/key', 'URL: ?api_key=secret%2Fkey&x=1', 'Error: Bearer my-token', 'Error: access_token="value"'):
                result = safe_detail(text)
                self.assertNotIn('secret/key', result)
                self.assertNotIn('secret%2Fkey', result)
                self.assertNotIn('my-token', result)
                self.assertNotIn('"value"', result)


if __name__ == '__main__':
    unittest.main()
