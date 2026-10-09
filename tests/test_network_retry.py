import unittest
from unittest.mock import Mock, patch
from network_retry import retry_transient


class RetryTests(unittest.TestCase):
    def test_zotero_503_can_recover(self):
        operation = Mock(side_effect=[RuntimeError("Code: 503"), "corpus"])
        with patch("network_retry.time.sleep") as sleep:
            self.assertEqual(retry_transient(operation, Mock()), "corpus")
        sleep.assert_called_once_with(15)

    def test_authentication_failure_is_not_retried(self):
        operation = Mock(side_effect=RuntimeError("Code: 401"))
        with patch("network_retry.time.sleep") as sleep, self.assertRaises(RuntimeError):
            retry_transient(operation, Mock())
        sleep.assert_not_called()

    def test_persistent_service_failure_is_bounded(self):
        operation = Mock(side_effect=RuntimeError("Code: 503"))
        with patch("network_retry.time.sleep"), self.assertRaises(RuntimeError):
            retry_transient(operation, Mock())
        self.assertEqual(operation.call_count, 4)
