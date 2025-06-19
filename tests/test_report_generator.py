import unittest
from unittest.mock import patch, MagicMock
import os

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import report_generator

class TestReportGenerator(unittest.TestCase):

    def test_format_data_for_email_success(self):
        analysis_result = {
            "fund_cik": "000TESTCIK",
            "fund_name": "Test Fund Alpha",
            "fund_ticker": "TFA",
            "total_net_assets": 123456789.00,
            "holdings_count": 1,
            "holdings_processed_for_company_ownership": 1,
            "detailed_holdings": [
                {
                    'name': 'Test Company XYZ', 'cusip': 'TESTCUSIP1', 'ticker': 'XYZ',
                    'market_value_in_fund': 1234567.0, 'percentage_of_fund': 0.01,
                    'shares_held_by_fund_str': '10000',
                    'total_outstanding_shares': 100000000,
                    'percentage_of_company_owned_by_fund': 0.01
                }
            ],
            "status": "Analysis complete."
        }
        report = report_generator.format_data_for_email(analysis_result)
        self.assertIn("Fund Name: Test Fund Alpha", report)
        self.assertIn("Fund CIK: 000TESTCIK", report)
        self.assertIn("Total Net Assets: $123,456,789.00", report)
        self.assertIn("Name: Test Company XYZ", report)
        self.assertIn("Percentage of Company Owned by Fund: 0.010000%", report)

    def test_format_data_for_email_failure_status(self):
        analysis_result = {"status": "Download failed.", "fund_cik": "000FAIL"}
        report = report_generator.format_data_for_email(analysis_result)
        self.assertIn("Fund analysis could not be completed.", report)
        self.assertIn("Status: Download failed.", report)

    @patch('report_generator.gmail_authenticate')
    @patch('report_generator.build')
    def test_send_email_report_success(self, mock_build, mock_gmail_authenticate):
        # Mock successful authentication and email sending
        mock_creds = MagicMock()
        mock_gmail_authenticate.return_value = mock_creds

        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_send_message_response = {'id': 'test_message_id'}
        mock_service.users.return_value.messages.return_value.send.return_value.execute.return_value = mock_send_message_response

        success = report_generator.send_email_report("test@example.com", "Test Subject", "Test Body")

        self.assertTrue(success)
        mock_gmail_authenticate.assert_called_once()
        mock_build.assert_called_once_with('gmail', 'v1', credentials=mock_creds)
        mock_service.users.return_value.messages.return_value.send.assert_called_once()

    @patch('report_generator.gmail_authenticate', return_value=None) # Simulate auth failure
    def test_send_email_report_auth_failure(self, mock_gmail_authenticate):
        success = report_generator.send_email_report("test@example.com", "Test Subject", "Test Body")
        self.assertFalse(success)
        mock_gmail_authenticate.assert_called_once()

    # Test for gmail_authenticate would be more complex due to file I/O and OAuth flow
    # For now, we focus on testing send_email_report assuming gmail_authenticate works or is mocked.
    # A simple test for credentials_file not found:
    @patch('report_generator.os.path.exists')
    def test_gmail_authenticate_no_credentials_file(self, mock_os_exists):
        # Simulate token.json not existing, then credentials.json not existing
        mock_os_exists.side_effect = [False, False]
        creds = report_generator.gmail_authenticate()
        self.assertIsNone(creds)
        # It should have tried to check for token.json then credentials.json
        self.assertEqual(mock_os_exists.call_count, 2)
        calls = [unittest.mock.call(report_generator.TOKEN_FILE), unittest.mock.call(report_generator.CREDENTIALS_FILE)]
        mock_os_exists.assert_has_calls(calls)


if __name__ == '__main__':
    unittest.main()
