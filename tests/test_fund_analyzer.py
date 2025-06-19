import unittest
from unittest.mock import patch, MagicMock
import os

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import fund_analyzer

class TestFundAnalyzer(unittest.TestCase):

    @patch('fund_analyzer.sec_parser.download_latest_fund_holding_filing')
    @patch('fund_analyzer.sec_parser.parse_nport_xml_filing')
    @patch('fund_analyzer.get_company_shares_outstanding') # Mocks the function within fund_analyzer
    def test_analyze_fund_ownership_success(self, mock_get_shares, mock_parse_nport, mock_download_filing):
        # Setup mocks
        mock_download_filing.return_value = "/fake/path/to/filings/0001234567/NPORT-P"
        mock_parse_nport.return_value = (
            "Test Fund X",
            100000000.0,
            [
                {'name': 'Company A', 'cusip': 'CUSIPA', 'ticker': 'CMPA', 'shares_or_principal_amount': '100', 'market_value_usd': 10000.0, 'percentage_of_fund': 0.01},
                {'name': 'Company B (No Ticker)', 'cusip': 'CUSIPB', 'ticker': None, 'shares_or_principal_amount': '200', 'market_value_usd': 20000.0, 'percentage_of_fund': 0.02},
                {'name': 'Company C Bond', 'cusip': 'CUSIPC', 'ticker': 'CMPCT', 'shares_or_principal_amount': '30000', 'market_value_usd': 30000.0, 'percentage_of_fund': 0.03} # Shares might be principal for bond
            ]
        )
        # Mock return for shares outstanding: first call for CMPA, second for CMPCT (if it were equity)
        mock_get_shares.side_effect = [1000000, 5000000]

        # Ensure API_KEY is not 'demo' for this test to allow processing all holdings
        # Also, ensure that fund_analyzer.API_KEY is updated if it's checked at module load time
        # or if analyze_fund_ownership re-reads it.
        with patch.dict(os.environ, {'ALPHA_VANTAGE_API_KEY': 'fakekey_for_test'}):
            # If fund_analyzer.API_KEY is set at module load, we need to patch it or reload the module.
            # A simpler approach for testing is to ensure its functions can be influenced by a passed-in key
            # or it re-evaluates os.getenv. The current fund_analyzer.py re-evaluates os.getenv in analyze_fund_ownership.
            fund_analyzer.API_KEY = 'fakekey_for_test' # Directly set for this test context if needed by other functions
            fund_analyzer.CALL_DELAY_SECONDS = 0 # No delay in tests

            result = fund_analyzer.analyze_fund_ownership("VFINX_TEST") # Fund ticker

            self.assertIsNotNone(result)
            self.assertEqual(result['status'], "Analysis complete.")
            self.assertEqual(result['fund_name'], "Test Fund X")
            self.assertEqual(result['total_net_assets'], 100000000.0)
            self.assertEqual(len(result['detailed_holdings']), 3)

            # Check Company A (CMPA)
            self.assertEqual(result['detailed_holdings'][0]['name'], 'Company A')
            self.assertEqual(result['detailed_holdings'][0]['total_outstanding_shares'], 1000000)
            self.assertAlmostEqual(result['detailed_holdings'][0]['percentage_of_company_owned_by_fund'], (100 / 1000000) * 100)

            # Check Company B (No Ticker) - should not have ownership calculated
            self.assertEqual(result['detailed_holdings'][1]['name'], 'Company B (No Ticker)')
            self.assertEqual(result['detailed_holdings'][1]['percentage_of_company_owned_by_fund'], "N/A (No Ticker/Shares)")

            # Check Company C (CMPCT) - assume shares_held_by_fund_num would be float(30000)
            self.assertEqual(result['detailed_holdings'][2]['name'], 'Company C Bond')
            self.assertEqual(result['detailed_holdings'][2]['total_outstanding_shares'], 5000000)
            self.assertAlmostEqual(result['detailed_holdings'][2]['percentage_of_company_owned_by_fund'], (30000 / 5000000) * 100)

            mock_download_filing.assert_called_once()
            mock_parse_nport.assert_called_once()
            self.assertEqual(mock_get_shares.call_count, 2) # Called for CMPA and CMPCT

    @patch('alpha_vantage.fundamentaldata.FundamentalData.get_company_overview')
    def test_get_company_shares_outstanding_success(self, mock_get_overview):
        mock_get_overview.return_value = ({'SharesOutstanding': '123456789'}, None)
        # Temporarily set API_KEY for this test to non-demo to bypass demo key specific logic
        original_api_key = fund_analyzer.API_KEY
        fund_analyzer.API_KEY = 'fake_test_key'
        try:
            shares = fund_analyzer.get_company_shares_outstanding("TESTTICKER")
            self.assertEqual(shares, 123456789)
        finally:
            fund_analyzer.API_KEY = original_api_key # Reset

    @patch('alpha_vantage.fundamentaldata.FundamentalData.get_company_overview')
    def test_get_company_shares_outstanding_api_failure(self, mock_get_overview):
        mock_get_overview.side_effect = Exception("API Error")
        original_api_key = fund_analyzer.API_KEY
        fund_analyzer.API_KEY = 'fake_test_key'
        try:
            shares = fund_analyzer.get_company_shares_outstanding("TESTTICKER")
            self.assertIsNone(shares)
        finally:
            fund_analyzer.API_KEY = original_api_key

    def test_resolve_fund_ticker_to_cik(self):
        self.assertEqual(fund_analyzer.resolve_fund_ticker_to_cik("VFINX"), "0000036405")
        self.assertIsNone(fund_analyzer.resolve_fund_ticker_to_cik("UNKNOWNTICKER"))

if __name__ == '__main__':
    unittest.main()
