import os
import time
from alpha_vantage.fundamentaldata import FundamentalData
from dotenv import load_dotenv
import sec_parser
import report_generator

load_dotenv() # This will load .env if present, setting ALPHA_VANTAGE_API_KEY
# API_KEY will be dynamically set/updated by main.py or use env default
API_KEY = os.getenv('ALPHA_VANTAGE_API_KEY', 'demo')
CALL_DELAY_SECONDS = 15 if API_KEY == 'demo' else 1
MAX_HOLDINGS_TO_PROCESS_DEMO = 3

def get_company_shares_outstanding(ticker_symbol):
    # Use the module-level API_KEY which might be updated by main.py
    current_api_key = API_KEY
    if not ticker_symbol:
        # print("Warning: No ticker symbol provided to get_company_shares_outstanding.")
        return None
    if current_api_key == 'demo' and ticker_symbol.upper() != 'IBM':
        print(f"DEMO KEY: Shares outstanding lookup for {ticker_symbol} will be skipped (only IBM works reliably for overview with demo key).")
        return None

    fd = FundamentalData(key=current_api_key, output_format='json')
    try:
        print(f"Fetching company overview for: {ticker_symbol} (Using key ending: {'...' + current_api_key[-4:] if len(current_api_key) > 4 else current_api_key})...")
        overview_data, _ = fd.get_company_overview(symbol=ticker_symbol)
        if overview_data:
            shares_outstanding_str = overview_data.get('SharesOutstanding')
            if shares_outstanding_str and shares_outstanding_str not in ["None", "0", None]:
                try:
                    shares = int(shares_outstanding_str)
                    if shares > 0: return shares
                    else:
                        print(f"Warning: SharesOutstanding is zero for {ticker_symbol}: {shares_outstanding_str}")
                        return None
                except ValueError:
                    print(f"Error: Could not convert SharesOutstanding '{shares_outstanding_str}' to int for {ticker_symbol}")
                    return None
            else:
                print(f"Error: 'SharesOutstanding' not found, is None, or zero for {ticker_symbol} in API response.")
                return None
        else:
            print(f"Error: No data received from get_company_overview for {ticker_symbol}")
            return None
    except Exception as e:
        print(f"An error occurred while fetching company overview for {ticker_symbol}: {e}")
        if "Our standard API call frequency is 5 calls per minute and 500 calls per day" in str(e) and current_api_key == 'demo':
            print(f"Alpha Vantage API call limit likely reached with 'demo' key for {ticker_symbol}.")
        elif "Invalid API call" in str(e) or "error message" in str(e).lower():
             print(f"API error for {ticker_symbol} (e.g. unsupported by demo key, invalid symbol).")
        return None

def resolve_fund_ticker_to_cik(fund_ticker_or_name):
    # print(f"Placeholder: Resolving {fund_ticker_or_name} to CIK.")
    if fund_ticker_or_name.upper() == "VFINX": return "0000036405"
    if fund_ticker_or_name.upper() == "VANGUARD STAR FUNDS": return "0000751158"
    if fund_ticker_or_name.upper() == "VTSAX": return "0000859027"
    if fund_ticker_or_name.upper() == "SPY": return "0000894051"
    print(f"Warning: CIK for {fund_ticker_or_name} not found in placeholder lookup.")
    return None

def analyze_fund_ownership(fund_ticker_or_name):
    # Update module-level API_KEY based on current environment,
    # ensuring it reflects any override from main.py
    global API_KEY
    API_KEY = os.getenv('ALPHA_VANTAGE_API_KEY', 'demo')
    global CALL_DELAY_SECONDS
    CALL_DELAY_SECONDS = 15 if API_KEY == 'demo' else 1

    print(f"Starting analysis for fund: {fund_ticker_or_name}")
    fund_cik = resolve_fund_ticker_to_cik(fund_ticker_or_name)
    if not fund_cik:
        print(f"Could not determine CIK for {fund_ticker_or_name}. Aborting.")
        return {"fund_ticker": fund_ticker_or_name, "status": "CIK resolution failed."}
    print(f"Resolved {fund_ticker_or_name} to CIK: {fund_cik}")

    filing_directory_path = sec_parser.download_latest_fund_holding_filing(fund_cik)
    if not filing_directory_path:
        print(f"Failed to download holdings for CIK {fund_cik}.")
        return {"fund_cik": fund_cik, "fund_ticker": fund_ticker_or_name, "status": "Download failed."}

    print(f"Download initiated. Filings expected in: {filing_directory_path}")
    parsed_fund_name, parsed_total_assets, parsed_holdings = sec_parser.parse_nport_xml_filing(filing_directory_path)

    if not parsed_holdings:
        status_msg = "Parsing failed or no holdings found."
        if parsed_fund_name or parsed_total_assets:
            status_msg = f"Parsed metadata (Fund: {parsed_fund_name}, Assets: {parsed_total_assets}) but no holdings details."
        print(f"{status_msg} for CIK {fund_cik} at {filing_directory_path}.")
        return {"fund_cik": fund_cik, "fund_name": parsed_fund_name, "total_net_assets": parsed_total_assets,
                "fund_ticker": fund_ticker_or_name, "status": status_msg}

    print(f"\nSuccessfully parsed {len(parsed_holdings)} holdings for {parsed_fund_name if parsed_fund_name else 'fund CIK ' + fund_cik}.")
    if parsed_fund_name: print(f"Fund Name: {parsed_fund_name}")
    if parsed_total_assets: print(f"Total Net Assets: ${parsed_total_assets:,.2f}")

    processed_holdings_data = []
    holdings_processed_for_av_count = 0

    for i, holding in enumerate(parsed_holdings):
        holding_detail = {
            'name': holding.get('name', 'N/A'),
            'cusip': holding.get('cusip', 'N/A'),
            'ticker': holding.get('ticker', 'N/A'),
            'market_value_in_fund': holding.get('market_value_usd', 0),
            'percentage_of_fund': holding.get('percentage_of_fund', 0),
            'shares_held_by_fund_str': holding.get('shares_or_principal_amount', '0'),
            'total_outstanding_shares': "Not Processed",
            'percentage_of_company_owned_by_fund': "Not Processed"
        }

        if API_KEY == 'demo' and holdings_processed_for_av_count >= MAX_HOLDINGS_TO_PROCESS_DEMO:
            print(f"DEMO KEY: Reached max ({MAX_HOLDINGS_TO_PROCESS_DEMO}) AlphaVantage calls. Skipping further company ownership checks for {holding_detail['name']}.")
            holding_detail['total_outstanding_shares'] = "Skipped (Demo Limit)"
            holding_detail['percentage_of_company_owned_by_fund'] = "Skipped (Demo Limit)"
            processed_holdings_data.append(holding_detail)
            continue

        try:
            shares_held_by_fund_num = float(holding_detail['shares_held_by_fund_str'])
        except (ValueError, TypeError):
            shares_held_by_fund_num = 0

        ticker_to_lookup = holding_detail['ticker']
        if not ticker_to_lookup and holding_detail['name'] and "INTERNATIONAL BUSINESS MACHINES" in holding_detail['name'].upper() and API_KEY == 'demo':
            ticker_to_lookup = "IBM"
            holding_detail['ticker'] = "IBM (Inferred)"

        if ticker_to_lookup and shares_held_by_fund_num > 0:
            # print(f"\nProcessing company ownership for: {holding_detail['name']} (Ticker: {ticker_to_lookup})")
            time.sleep(CALL_DELAY_SECONDS)
            total_outstanding_shares = get_company_shares_outstanding(ticker_to_lookup)
            holdings_processed_for_av_count += 1

            if total_outstanding_shares and total_outstanding_shares > 0:
                holding_detail['total_outstanding_shares'] = total_outstanding_shares
                percentage_of_company_owned = (shares_held_by_fund_num / total_outstanding_shares) * 100
                holding_detail['percentage_of_company_owned_by_fund'] = percentage_of_company_owned
            else:
                holding_detail['total_outstanding_shares'] = "N/A (AV Fail/No Data)"
                holding_detail['percentage_of_company_owned_by_fund'] = "N/A (AV Fail/No Data)"
        else:
             holding_detail['total_outstanding_shares'] = "N/A (No Ticker/Shares)"
             holding_detail['percentage_of_company_owned_by_fund'] = "N/A (No Ticker/Shares)"

        processed_holdings_data.append(holding_detail)

    final_result = {
        "fund_cik": fund_cik,
        "fund_name": parsed_fund_name,
        "fund_ticker": fund_ticker_or_name,
        "total_net_assets": parsed_total_assets,
        "holdings_count": len(parsed_holdings),
        "holdings_processed_for_company_ownership": holdings_processed_for_av_count,
        "detailed_holdings": processed_holdings_data,
        "status": "Analysis complete."
    }
    return final_result

# The original __main__ block from fund_analyzer.py is removed or commented out
# to ensure main.py is the sole entry point for typical application runs.
# Test/dev runs can still be done by uncommenting or running specific functions directly.
# if __name__ == '__main__':
#     fund_symbol = "VFINX"
#     print(f"--- Direct Test Run of fund_analyzer.py for: {fund_symbol} ---")
#     user_recipient_email = "dev_test@example.com"
#     analysis_data = analyze_fund_ownership(fund_symbol)
#     if analysis_data and analysis_data.get('status') == "Analysis complete.":
#         print(f"\n--- Generating Email Report for {fund_symbol} ---")
#         report_text = report_generator.format_data_for_email(analysis_data)
#         # ... (rest of original test email logic) ...
#     elif analysis_data:
#         print(f"\nAnalysis for {fund_symbol} not fully completed: {analysis_data.get('status')}")
#     else:
#         print(f"\nAnalysis failed for {fund_symbol}.")
#     if API_KEY == 'demo':
#         print("\nNOTE: AlphaVantage calls were limited due to using the 'demo' API key.")
