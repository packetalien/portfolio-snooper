import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import xml.etree.ElementTree as ET

# Add project root to sys.path to allow importing project modules
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import sec_parser # Assuming sec_parser.py is in the parent directory

# Sample NPORT-P XML data (simplified for testing)
SAMPLE_NPORT_P_XML_CONTENT = """
<edgarSubmission>
    <formData>
        <genInfo>
            <regName>Test Fund Family</regName>
            <seriesName>Test Fund Series A</seriesName>
            <totAssets>12345000.00</totAssets>
        </genInfo>
        <fundInfo>
            <!-- More fund info here -->
        </fundInfo>
        <invstOrSecs>
            <invstOrSec>
                <name>APPLE INC</name>
                <lei>HWUPKR0MPOU8FGXBT394</lei>
                <cusip>037833100</cusip>
                <valUSD>1000000.00</valUSD>
                <balance>5000</balance>
                <pctVal>8.10</pctVal>
                <payoffProfile>Long</payoffProfile>
                <assetCat>EC</assetCat>
                <issuerCat>CORP</issuerCat>
                <invCountry>US</invCountry>
                <isRestrictedSec>N</isRestrictedSec>
                <securityTicker>AAPL</securityTicker>
            </invstOrSec>
            <invstOrSec>
                <name>MICROSOFT CORP</name>
                <lei>GLEE8Y66F67V82VM2W42</lei>
                <cusip>594918104</cusip>
                <valUSD>800000.00</valUSD>
                <balance>2000</balance>
                <pctVal>6.48</pctVal>
                <payoffProfile>Long</payoffProfile>
                <assetCat>EC</assetCat>
                <issuerCat>CORP</issuerCat>
                <invCountry>US</invCountry>
                <isRestrictedSec>N</isRestrictedSec>
                <!-- No ticker for this one -->
            </invstOrSec>
        </invstOrSecs>
    </formData>
</edgarSubmission>
"""

SAMPLE_FULL_SUBMISSION_TXT_CONTENT = f"""
<SEC-DOCUMENT>
<FILENAME>full-submission.txt
<TEXT>
<XML>
{SAMPLE_NPORT_P_XML_CONTENT}
</XML>
</TEXT>
</SEC-DOCUMENT>
"""


class TestSecParser(unittest.TestCase):

    def setUp(self):
        # Ensure DOWNLOAD_PATH exists for the downloader instance, even if not used in all tests
        self.test_download_path = os.path.join(os.getcwd(), "test_sec_filings_parser")
        if not os.path.exists(self.test_download_path):
            os.makedirs(self.test_download_path)

        # Patch the Downloader class within sec_parser module
        self.downloader_patch = patch('sec_parser.Downloader')
        self.MockDownloaderClass = self.downloader_patch.start()
        self.mock_downloader_instance = self.MockDownloaderClass.return_value

        # Also patch the global dl instance in sec_parser if it's used directly by functions
        # If sec_parser.dl is instantiated at module level, we need to patch that specific instance too.
        # For simplicity, assuming functions might take a downloader instance or use a module global.
        # If functions always use `sec_parser.dl`, then patch `sec_parser.dl`.
        # Let's assume sec_parser.dl is the one used.
        self.dl_instance_patch = patch('sec_parser.dl', self.mock_downloader_instance)
        self.dl_instance_patch.start()


    def tearDown(self):
        self.downloader_patch.stop()
        self.dl_instance_patch.stop()
        if os.path.exists(self.test_download_path):
            # Clean up created directories, be careful with rmtree
            for root, dirs, files in os.walk(self.test_download_path, topdown=False):
                for name in files:
                    os.remove(os.path.join(root, name))
                for name in dirs:
                    os.rmdir(os.path.join(root, name))
            os.rmdir(self.test_download_path)


    @patch('sec_parser.os.path.exists')
    @patch('sec_parser.os.makedirs')
    @patch('sec_parser.glob.glob')
    @patch('builtins.open', new_callable=mock_open) # Mocks open()
    @patch('xml.etree.ElementTree.parse') # Mocks ET.parse
    def test_parse_nport_xml_filing_direct_xml(self, mock_et_parse, mock_file_open, mock_glob, mock_makedirs, mock_path_exists):
        # Simulate finding a direct XML file
        mock_path_exists.return_value = True # For os.path.exists(DOWNLOAD_PATH)
        filing_dir = "/fake/path/to/filings/CIK/NPORT-P"
        accession_dir = os.path.join(filing_dir, "0000123-45-678910")
        xml_file_path = os.path.join(accession_dir, "formNPORT-P.xml")

        with patch('sec_parser.os.listdir', return_value=["0000123-45-678910"]): # Mock listdir to return accession dir
            mock_glob.return_value = [xml_file_path] # Simulate glob finding this file

            # Mock the content of the XML file
            mock_file_open.return_value.read.return_value = SAMPLE_NPORT_P_XML_CONTENT

            # Mock ET.parse to return a mock tree and root
            mock_tree = MagicMock()
            mock_root = ET.fromstring(SAMPLE_NPORT_P_XML_CONTENT) # Use real XML for root structure
            mock_tree.getroot.return_value = mock_root
            mock_et_parse.return_value = mock_tree

            fund_name, total_assets, holdings = sec_parser.parse_nport_xml_filing(filing_dir)

            self.assertEqual(fund_name, "Test Fund Series A")
            self.assertEqual(total_assets, 12345000.00)
            self.assertEqual(len(holdings), 2)
            self.assertEqual(holdings[0]['name'], "APPLE INC")
            self.assertEqual(holdings[0]['cusip'], "037833100")
            self.assertEqual(holdings[0]['ticker'], "AAPL")
            self.assertEqual(holdings[0]['market_value_usd'], 1000000.00)
            self.assertEqual(holdings[0]['shares_or_principal_amount'], "5000")
            self.assertEqual(holdings[0]['percentage_of_fund'], 8.10)
            self.assertEqual(holdings[1]['name'], "MICROSOFT CORP")
            self.assertIsNone(holdings[1].get('ticker')) # Ticker is missing for MSFT in sample

    @patch('sec_parser.os.path.exists')
    @patch('sec_parser.os.makedirs')
    @patch('sec_parser.glob.glob')
    @patch('builtins.open', new_callable=mock_open)
    # No need to mock ET.parse here if we are testing the XML extraction logic primarily
    def test_parse_nport_xml_filing_from_full_submission_txt(self, mock_file_open, mock_glob, mock_makedirs, mock_path_exists):
        mock_path_exists.return_value = True
        filing_dir = "/fake/path/to/filings/CIK/NPORT-P"
        accession_dir = os.path.join(filing_dir, "0000123-45-678910")
        txt_file_path = os.path.join(accession_dir, "full-submission.txt")

        with patch('sec_parser.os.listdir', return_value=["0000123-45-678910"]):
            # This mock_glob should return an empty list for *.xml to force fallback to full-submission.txt
            # The logic in sec_parser.py tries specific XML names first, then full-submission.txt, then *.xml
            # So, we need to ensure those specific XML names don't exist (or mock os.path.exists for them)
            # and that glob for *.xml returns empty.

            # Simulate that preferred XML files (primary_doc.xml, etc.) do not exist
            def path_exists_side_effect(path):
                if path == sec_parser.DOWNLOAD_PATH: return True # Initial check for download path
                if path == filing_dir: return True # Check for filing_dir itself
                if path == accessions_dir: return True
                if "full-submission.txt" in path: return True # The .txt file exists
                if ".xml" in path: return False # No other XML files exist
                return True # Default for other paths like accession_dir

            mock_path_exists.side_effect = path_exists_side_effect
            mock_glob.return_value = [] # No other *.xml files found by glob

            # Mock the content of the .txt file when open(txt_file_path) is called
            mock_file_open.return_value.read.return_value = SAMPLE_FULL_SUBMISSION_TXT_CONTENT

            # The actual ET.fromstring will be called on the extracted XML string
            fund_name, total_assets, holdings = sec_parser.parse_nport_xml_filing(filing_dir)

            self.assertEqual(fund_name, "Test Fund Series A")
            self.assertEqual(total_assets, 12345000.00)
            self.assertEqual(len(holdings), 2)
            self.assertEqual(holdings[0]['name'], "APPLE INC")

    def test_download_latest_fund_holding_filing_success(self):
        self.mock_downloader_instance.get.return_value = 1 # Simulate 1 filing downloaded
        cik = "000TESTCIK"
        expected_path = os.path.join(sec_parser.DOWNLOAD_PATH, 'sec-edgar-filings', cik, 'NPORT-P')

        # Call the function that uses the mocked downloader
        result_path = sec_parser.download_latest_fund_holding_filing(cik)

        self.mock_downloader_instance.get.assert_called_with("NPORT-P", cik, limit=1)
        self.assertEqual(result_path, expected_path)

    def test_download_latest_fund_holding_filing_fallback(self):
        # Simulate NPORT-P fails, NPORT-EX succeeds
        self.mock_downloader_instance.get.side_effect = [0, 1]
        cik = "000FALLBACKCIK"
        expected_path_nport_ex = os.path.join(sec_parser.DOWNLOAD_PATH, 'sec-edgar-filings', cik, 'NPORT-EX')

        result_path = sec_parser.download_latest_fund_holding_filing(cik)

        self.assertEqual(self.mock_downloader_instance.get.call_count, 2)
        self.mock_downloader_instance.get.assert_any_call("NPORT-P", cik, limit=1)
        self.mock_downloader_instance.get.assert_called_with("NPORT-EX", cik, limit=1) # Last call
        self.assertEqual(result_path, expected_path_nport_ex)

if __name__ == '__main__':
    unittest.main()
