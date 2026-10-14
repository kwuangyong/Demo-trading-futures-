import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock, patch

from backend.vnstock_fetch import authenticate, history_query


class FetchChecks(unittest.TestCase):
    def test_minute_request_has_explicit_recent_dates_for_both_sources(self):
        for source in ('vci', 'kbs'):
            params = history_query(source, date(2026,10,14))
            self.assertEqual(params['start'], '2026-09-30')
            self.assertEqual(params['end'], '2026-10-14')
            self.assertEqual(params['interval'], '1m')
            self.assertEqual(params['length'], 500)
            self.assertEqual(params['source'], source)

    def test_v5_login_does_not_import_legacy_auth(self):
        library = SimpleNamespace(login=Mock())
        authenticate(library, 'test-key')
        library.login.assert_called_once_with('test-key')

    def test_legacy_failed_key_registration_is_not_ignored(self):
        fake_vnai = SimpleNamespace(setup_api_key=Mock(return_value=False))
        with patch.dict('sys.modules', {'vnai':fake_vnai}):
            with self.assertRaisesRegex(ValueError, 'registration failed'):
                authenticate(SimpleNamespace(), 'test-key')

    def test_guest_does_not_invoke_authentication(self):
        library = SimpleNamespace(login=Mock())
        authenticate(library, '')
        library.login.assert_not_called()


if __name__ == '__main__':
    unittest.main()
