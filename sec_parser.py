import os
import xml.etree.ElementTree as ET
from sec_edgar_downloader import Downloader
from datetime import date
import glob # For finding files

# Initialize downloader
COMPANY_NAME_FOR_EDGAR = "My Financial Analysis Tool"
EMAIL_FOR_EDGAR = "dev.email@example.com"
DOWNLOAD_PATH = os.path.join(os.getcwd(), "sec_filings")

if not os.path.exists(DOWNLOAD_PATH):
    os.makedirs(DOWNLOAD_PATH)

dl = Downloader(COMPANY_NAME_FOR_EDGAR, EMAIL_FOR_EDGAR, DOWNLOAD_PATH)

def download_latest_fund_holding_filing(fund_cik):
    """
    Downloads the latest NPORT-P, NPORT-EX, or N-Q filing for a given fund CIK.
    Returns the path to the specific downloaded filing directory or None.
    """
    print(f"Attempting to download filings for CIK: {fund_cik}")
    # Define filing types in order of preference
    filing_types_to_try = ["NPORT-P", "NPORT-EX", "N-Q"]

    for filing_type in filing_types_to_try:
        try:
            print(f"Attempting to download {filing_type} filings for {fund_cik}...")
            # Limit to 1 filing to get the most recent one.
            # Consider adding date constraints if needed, e.g., after_date=(date.today() - timedelta(days=365)).isoformat()
            num_filings = dl.get(filing_type, fund_cik, limit=1)

            if num_filings > 0:
                print(f"Successfully downloaded {num_filings} {filing_type} filing(s) for {fund_cik}.")
                # Path to the directory for this CIK and filing type
                specific_filing_dir = os.path.join(DOWNLOAD_PATH, 'sec-edgar-filings', fund_cik, filing_type)
                return specific_filing_dir # Return the directory containing the filing(s)
            else:
                print(f"No {filing_type} filings found for {fund_cik}.")
        except Exception as e:
            print(f"An error occurred while trying to download {filing_type} for {fund_cik}: {e}")
            if "No filings found for CIK" in str(e) and "0000000000" in fund_cik:
                print("This CIK is known to have no filings, as expected for testing.")
            # Continue to the next filing type if current one fails or not found

    print(f"No suitable filings found for {fund_cik} after trying all types.")
    return None

def parse_nport_xml_filing(filing_directory_path):
    """
    Parses an NPORT-P XML filing to extract fund holdings.
    This is a simplified parser and might need adjustments based on XML variations.
    """
    holdings = []
    total_net_assets = None
    fund_name = None

    try:
        # Find the main XML file in the directory. NPORT-P often has a primary XML.
        # Common names could be formNPORT-P.xml, NPORT-P.xml, or similar.
        # Sometimes they are named with accession number like 0001234567-89-012345.xml
        # We'll look for any .xml file in the immediate directory.
        # The actual filing downloaded by sec-edgar-downloader is usually inside another
        # directory named after the accession number. We need to find the specific XML file.

        # The sec-edgar-downloader library creates a structure like:
        # DOWNLOAD_PATH/sec-edgar-filings/CIK/FILING_TYPE/ACCESSION_NUMBER_cleaned/primary_doc.xml or full_submission.txt
        # We need to find the primary XML document. Often it's called 'formNPORT-P.xml' or similar within the accession number folder.

        # Let's list all subdirectories (accession numbers) in filing_directory_path
        accession_dirs = [d for d in os.listdir(filing_directory_path) if os.path.isdir(os.path.join(filing_directory_path, d))]
        if not accession_dirs:
            print(f"No accession number directories found in {filing_directory_path}")
            return None, None, None

        # Assume the latest accession number directory by sorting (optional, or just take first if limit=1)
        accession_dirs.sort(reverse=True)
        latest_accession_dir = os.path.join(filing_directory_path, accession_dirs[0])

        # Revised file searching logic:
        # Prefer specific XML file names, then full-submission.txt
        # Then any other .xml file as a last resort.
        xml_file_path = None
        potential_files_to_check = [
            os.path.join(latest_accession_dir, "primary_doc.xml"), # Common name for actual XML content
            os.path.join(latest_accession_dir, "formNPORT-P.xml"),
            os.path.join(latest_accession_dir, "NPORT-P.xml")
        ]

        for pf_path in potential_files_to_check:
            if os.path.exists(pf_path):
                xml_file_path = pf_path
                print(f"Found preferred XML file: {xml_file_path}")
                break

        is_text_submission = False
        if not xml_file_path:
            # Fallback to full-submission.txt if no direct XML file is found
            txt_submission_path = os.path.join(latest_accession_dir, "full-submission.txt")
            if os.path.exists(txt_submission_path):
                xml_file_path = txt_submission_path
                is_text_submission = True
                print(f"Found text submission file (will attempt to parse as XML): {xml_file_path}")
            else:
                # Last resort: any other .xml file in the directory
                xml_files = glob.glob(os.path.join(latest_accession_dir, '*.xml'))
                if xml_files:
                    xml_file_path = xml_files[0] # Take the first one found
                    print(f"Found other XML file: {xml_file_path}")

        if not xml_file_path:
            print(f"No suitable XML or text submission file found in {latest_accession_dir}")
            return None, None, None

        root = None
        if is_text_submission:
            print(f"Parsing text submission file: {xml_file_path}")
            with open(xml_file_path, 'r', encoding='utf-8') as f:
                file_content = f.read()
            # NPORT-P XML content is usually enclosed in <XML> tags within the submission txt file
            # Or sometimes starts directly with <?xml ...?> or the root tag like <edgarSubmission>
            # Revised logic for extracting XML from full-submission.txt
            # 1. Try to find <XML>...</XML> block. This is common.
            # 2. If not found, try to find <?xml ...?> declaration.
            # 3. Strip any leading content before these markers.

            xml_data_to_parse = None

            # Try to find the <XML> block first
            xml_start_tag = '<XML>'
            xml_end_tag = '</XML>'
            xml_block_start_index = file_content.find(xml_start_tag)

            if xml_block_start_index != -1:
                print(f"Found '{xml_start_tag}' tag.")
                xml_block_end_index = file_content.find(xml_end_tag, xml_block_start_index + len(xml_start_tag))
                if xml_block_end_index != -1:
                    # Extract content between <XML> and </XML>
                    xml_data_segment = file_content[xml_block_start_index + len(xml_start_tag):xml_block_end_index]
                    # The actual XML might start after an <?xml ...?> declaration within this block
                    xml_decl_within_segment_idx = xml_data_segment.find("<?xml")
                    if xml_decl_within_segment_idx != -1:
                        xml_data_to_parse = xml_data_segment[xml_decl_within_segment_idx:].strip()
                        print("Using content from <?xml...?> declaration within <XML> block.")
                    else:
                        # Or it might be the direct content
                        xml_data_to_parse = xml_data_segment.strip()
                        print("Using content directly from <XML> block (after stripping whitespace).")
                else:
                    print(f"Found '{xml_start_tag}' but no matching '{xml_end_tag}' in {xml_file_path}")
                    # This case is problematic, maybe try from <?xml if present in the whole file

            # If <XML> block processing didn't yield data, try finding <?xml ...?> in the whole file
            if not xml_data_to_parse:
                print("Could not process <XML> block or it was not found. Looking for <?xml ...?> declaration.")
                xml_declaration_start_index = file_content.find("<?xml")
                if xml_declaration_start_index != -1:
                    xml_data_to_parse = file_content[xml_declaration_start_index:].strip()
                    print("Using content from <?xml ...?> declaration in the full file.")
                else:
                    print(f"Neither '<XML>' block nor '<?xml ...?>' declaration found in {xml_file_path}. Cannot parse.")
                    return None, None, None

            if xml_data_to_parse:
                try:
                    root = ET.fromstring(xml_data_to_parse)
                except ET.ParseError as e:
                    print(f"Final XML parsing attempt failed for {xml_file_path}: {e}")
                    # Log a snippet of what was attempted for debugging
                    # print(f"Data snippet attempted for parsing (first 200 chars): {xml_data_to_parse[:200]}")
                    return None, None, None
            else:
                # This case should ideally be caught by previous checks
                print("No XML data could be extracted for parsing.")
                return None, None, None
        else:
            print(f"Parsing XML file: {xml_file_path}")
            tree = ET.parse(xml_file_path)
            root = tree.getroot()

        if root is None:
            print("XML root element not found or parsed.")
            return None, None, None

        # XML namespaces can make parsing tricky. Attempt to handle them.
        # Common namespaces for NPORT-P. This is a common point of failure if namespaces change.
        # We'll try a generic approach to find tags, stripping namespace if present.

        # Function to strip namespace for easier tag matching
        def get_tag_name(element):
            try:
                return element.tag.split('}', 1)[1] if '}' in element.tag else element.tag
            except: # pylint: disable=bare-except
                return element.tag

        # Find fund name (heuristic, depends on specific NPORT-P structure)
        # Example path: genInfo/regName or seriesName or seriesId
        # This needs to be adapted based on actual NPORT-P XML structure.
        # Looking for seriesName as often it's more descriptive

        # Try finding series information first.
        series_name_elem = root.find("./{*}seriesName") # More direct path if root is <edgarSubmission> or similar wrapper
        if series_name_elem is None: # Fallback to deeper search
            series_name_elem = root.find(".//{*}seriesName")

        if series_name_elem is not None and series_name_elem.text:
            fund_name = series_name_elem.text.strip()
        else:
            # Fallback to regName if seriesName is not found
            reg_name_elem = root.find("./{*}genInfo/{*}regName") # More direct path
            if reg_name_elem is None:
                 reg_name_elem = root.find(".//{*}regName") # Fallback to deeper search
            if reg_name_elem is not None and reg_name_elem.text:
                fund_name = reg_name_elem.text.strip()


        # Find total net assets
        # In NPORT-P, it's often under fundInfo/totAssets or similar
        tot_assets_elem = root.find("./{*}fundInfo/{*}totAssets") # More direct path
        if tot_assets_elem is None: # Fallback to deeper search
            tot_assets_elem = root.find(".//{*}totAssets")

        if tot_assets_elem is not None and tot_assets_elem.text:
            try:
                total_net_assets = float(tot_assets_elem.text)
            except ValueError:
                print(f"Could not parse total_net_assets: {tot_assets_elem.text}")

        # Iterate through holdings (usually under an <invstOrSecs> or <holding> section)
        # NPORT-P structure often has <invstOrSecs> elements.

        # Find all invstOrSec elements. Try direct path first, then deeper search.
        holdings_elements = root.findall("./{*}invstOrSecs/{*}invstOrSec")
        if not holdings_elements: # If direct path fails, try a more general search
            holdings_elements = root.findall(".//{*}invstOrSec")

        for holding_elem in holdings_elements:
            holding_data = {}

            # Using more direct child searches first, then .//{} as fallback
            name_elem = holding_elem.find("./{*}name") or holding_elem.find(".//{*}name")
            if name_elem is not None:
                holding_data['name'] = name_elem.text

            cusip_elem = holding_elem.find("./{*}cusip") or holding_elem.find(".//{*}cusip")
            if cusip_elem is not None:
                holding_data['cusip'] = cusip_elem.text

            ticker_elem = holding_elem.find("./{*}securityTicker") or holding_elem.find(".//{*}securityTicker")
            if ticker_elem is not None:
                holding_data['ticker'] = ticker_elem.text

            val_usd_elem = holding_elem.find("./{*}valUSD") or holding_elem.find(".//{*}valUSD")
            if val_usd_elem is not None:
                try:
                    holding_data['market_value_usd'] = float(val_usd_elem.text)
                except ValueError:
                    pass

            balance_elem = holding_elem.find("./{*}balance") or holding_elem.find(".//{*}balance")
            if balance_elem is not None:
                 holding_data['shares_or_principal_amount'] = balance_elem.text

            pct_val_elem = holding_elem.find("./{*}pctVal") or holding_elem.find(".//{*}pctVal")
            if pct_val_elem is not None:
                try:
                    holding_data['percentage_of_fund'] = float(pct_val_elem.text)
                except ValueError:
                    pass

            if holding_data.get('name') and (holding_data.get('market_value_usd') is not None or holding_data.get('shares_or_principal_amount')):
                holdings.append(holding_data)

        if not fund_name and root.find(".//{*}regName") is not None : # Check if regName was found as a fallback
             fund_name = root.find(".//{*}regName").text # Attempt to get it if seriesName was missed

        if not fund_name:
            print("Warning: Could not determine fund name from XML.")
        if total_net_assets is None:
             print("Warning: Could not determine total net assets from XML.")
        if not holdings:
            print("Warning: No holdings extracted. The XML structure might be different or unsupported by this basic parser.")
            if xml_file_path: print(f"Consider inspecting the file: {xml_file_path}")

        return fund_name, total_net_assets, holdings

    except ET.ParseError as e:
        errmsg = f"XML ParseError"
        if 'xml_file_path' in locals() and xml_file_path:
            errmsg += f" for {xml_file_path}"
        errmsg += f": {e}"
        print(errmsg)
        return None, None, None
    except Exception as e:
        print(f"An error occurred during parsing of {filing_directory_path}: {e}")
        # import traceback
        # traceback.print_exc() # For more detailed debugging if needed
        return None, None, None

if __name__ == '__main__':
    # This CIK (VANGUARD STAR FUNDS) is known to have NPORT-P filings.
    # The downloader should place them in: ./sec_filings/sec-edgar-filings/0000751158/NPORT-P/
    test_cik = "0000751158"
    print(f"--- Attempting to download and parse for CIK: {test_cik} ---")

    # First, ensure the filing is downloaded
    download_dir = download_latest_fund_holding_filing(test_cik)

    if download_dir and os.path.exists(download_dir):
        print(f"Download directory for {test_cik} confirmed at: {download_dir}")
        # Now, attempt to parse
        parsed_fund_name, parsed_total_assets, parsed_holdings = parse_nport_xml_filing(download_dir)

        if parsed_holdings:
            print(f"\nSuccessfully parsed holdings for CIK {test_cik}.")
            if parsed_fund_name:
                print(f"Fund Name: {parsed_fund_name}")
            if parsed_total_assets:
                print(f"Total Net Assets: {parsed_total_assets:,.2f}")
            print(f"Found {len(parsed_holdings)} holdings. Showing first 5:")
            for i, holding in enumerate(parsed_holdings[:5]):
                print(f"  {i+1}. Name: {holding.get('name', 'N/A')}, CUSIP: {holding.get('cusip', 'N/A')}, Value: ${holding.get('market_value_usd', 0):,.2f}, %Fund: {holding.get('percentage_of_fund', 0):.4f}")
        elif parsed_fund_name is not None or parsed_total_assets is not None:
            print(f"Parsed some metadata (Fund: {parsed_fund_name}, Assets: {parsed_total_assets}) but no holdings found or error during holdings parsing.")
        else:
            print(f"Could not parse holdings for CIK {test_cik} from directory {download_dir}.")
            print("This could be due to XML structure variations, missing XML file, or other parsing issues.")
    else:
        print(f"Failed to download or locate filing directory for CIK {test_cik}. Cannot parse.")

    # Test with a CIK that was problematic before (e.g. VFINX direct CIK)
    # VFINX CIK 0000036405 - downloader seems to work for NPORT-P now.
    test_cik_vfinx = "0000036405"
    print(f"\n--- Attempting to download and parse for CIK: {test_cik_vfinx} (Vanguard 500 Index) ---")
    download_dir_vfinx = download_latest_fund_holding_filing(test_cik_vfinx)
    if download_dir_vfinx and os.path.exists(download_dir_vfinx):
        print(f"Download directory for {test_cik_vfinx} confirmed at: {download_dir_vfinx}")
        parsed_fund_name_v, parsed_total_assets_v, parsed_holdings_v = parse_nport_xml_filing(download_dir_vfinx)
        if parsed_holdings_v:
            print(f"\nSuccessfully parsed holdings for CIK {test_cik_vfinx}.")
            if parsed_fund_name_v: print(f"Fund Name: {parsed_fund_name_v}")
            if parsed_total_assets_v: print(f"Total Net Assets: {parsed_total_assets_v:,.2f}")
            print(f"Found {len(parsed_holdings_v)} holdings. Showing first 2:")
            for i, holding in enumerate(parsed_holdings_v[:2]):
                print(f"  {i+1}. {holding}")
        else:
            print(f"Could not parse holdings for CIK {test_cik_vfinx} from {download_dir_vfinx}")
    else:
        print(f"Failed to download or locate filing directory for CIK {test_cik_vfinx}. Cannot parse.")
