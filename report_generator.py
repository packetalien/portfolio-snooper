import os.path
import base64
from email.mime.text import MIMEText

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these SCOPES, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.send']
# The file credentials.json needs to be obtained from Google Cloud Console
# for the OAuth 2.0 Client ID. Place it in the same directory as this script.
CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'token.json'

def format_data_for_email(analysis_result):
    """
    Formats the fund analysis result into a human-readable string for email.
    """
    if not analysis_result or analysis_result.get('status', '').startswith("Parsing failed") or analysis_result.get('status', '').startswith("Download failed"):
        return f"Fund analysis could not be completed. Status: {analysis_result.get('status', 'Unknown error')}"

    report_lines = []
    report_lines.append(f"Fund Analysis Report")
    report_lines.append("======================")

    if analysis_result.get('fund_name'):
        report_lines.append(f"Fund Name: {analysis_result['fund_name']}")
    report_lines.append(f"Fund CIK: {analysis_result.get('fund_cik', 'N/A')}")
    if analysis_result.get('total_net_assets') is not None: # Check specifically for None
        try:
            report_lines.append(f"Total Net Assets: ${float(analysis_result['total_net_assets']):,.2f}")
        except (ValueError, TypeError):
            report_lines.append(f"Total Net Assets: {analysis_result['total_net_assets']} (Could not format as currency)")
    else:
        report_lines.append(f"Total Net Assets: N/A")

    report_lines.append(f"Total Holdings Parsed: {analysis_result.get('holdings_count', 0)}")
    report_lines.append(f"Holdings Processed for Company Ownership: {analysis_result.get('holdings_processed_for_company_ownership', 0)}")
    report_lines.append("\n--- Holdings Details ---")

    detailed_holdings = analysis_result.get('detailed_holdings', [])
    if not detailed_holdings:
        report_lines.append("No detailed holdings information available.")

    for i, holding in enumerate(detailed_holdings[:20]): # Limit to first 20 for brevity in email
        report_lines.append(f"\n{i+1}. Name: {holding.get('name', 'N/A')}")
        report_lines.append(f"   CUSIP: {holding.get('cusip', 'N/A')}, Ticker: {holding.get('ticker', 'N/A')}")
        report_lines.append(f"   Shares/Principal Held by Fund: {holding.get('shares_held_by_fund_str', 'N/A')}")

        market_val = holding.get('market_value_in_fund', 0)
        try:
            report_lines.append(f"   Market Value in Fund: ${float(market_val):,.2f}")
        except (ValueError, TypeError):
            report_lines.append(f"   Market Value in Fund: {market_val}")

        pct_fund = holding.get('percentage_of_fund', 0)
        try:
            report_lines.append(f"   Percentage of Fund Assets: {float(pct_fund):.4f}%")
        except (ValueError, TypeError):
            report_lines.append(f"   Percentage of Fund Assets: {pct_fund}%")

        ownership_pct = holding.get('percentage_of_company_owned_by_fund', 'N/A')
        if isinstance(ownership_pct, float):
            report_lines.append(f"   Percentage of Company Owned by Fund: {ownership_pct:.6f}%")
        else:
            report_lines.append(f"   Percentage of Company Owned by Fund: {ownership_pct}")

        outstanding_shares = holding.get('total_outstanding_shares', 'N/A')
        if isinstance(outstanding_shares, int):
             report_lines.append(f"   Total Outstanding Shares of Company: {outstanding_shares:,}")
        else:
            report_lines.append(f"   Total Outstanding Shares of Company: {outstanding_shares}")

    report_lines.append("\n\nNote: This report may be truncated for brevity if many holdings exist.")
    report_lines.append("Full data might be available in logs or a more detailed output.")
    return "\n".join(report_lines)

def gmail_authenticate():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Failed to refresh token: {e}. Please re-authorize.")
                creds = None
        if not creds:
            if not os.path.exists(CREDENTIALS_FILE):
                print(f"ERROR: {CREDENTIALS_FILE} not found.")
                return None
            try:
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                print("Attempting OAuth: If in a non-interactive env, this may fail or require manual steps.")
                creds = flow.run_local_server(port=0)
            except Exception as e:
                print(f"Failed to run OAuth flow: {e}")
                return None
        if creds:
            with open(TOKEN_FILE, 'w') as token:
                token.write(creds.to_json())
    return creds

def send_email_report(recipient_email, subject, report_content_str):
    creds = gmail_authenticate()
    if not creds:
        print("Could not authenticate with Gmail. Email not sent.")
        return False
    try:
        service = build('gmail', 'v1', credentials=creds)
        message = MIMEText(report_content_str)
        message['to'] = recipient_email
        message['subject'] = subject
        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        create_message = {'raw': encoded_message}
        send_message = service.users().messages().send(userId="me", body=create_message).execute()
        print(f"Sent message to {recipient_email}, Message Id: {send_message['id']}")
        return True
    except HttpError as error:
        print(f'An HTTP error occurred while sending email: {error}')
        if "invalid_grant" in str(error).lower() or "token has been expired or revoked" in str(error).lower():
            print(f"Consider deleting {TOKEN_FILE} and re-authenticating.")
        return False
    except Exception as e:
        print(f"An unexpected error occurred while sending email: {e}")
        return False

if __name__ == '__main__':
    print("--- Testing report_generator.py ---")
    dummy_analysis_result = {
        "fund_cik": "000TESTCIK", "fund_name": "Test Fund Alpha",
        "total_net_assets": 123456789.00, "holdings_count": 2,
        "holdings_processed_for_company_ownership": 1,
        "detailed_holdings": [
            {'name': 'APPLE INC', 'cusip': '037833100', 'ticker': 'AAPL',
             'market_value_in_fund': 10000000.0, 'percentage_of_fund': 0.0810,
             'shares_held_by_fund_str': '50000', 'total_outstanding_shares': 15000000000,
             'percentage_of_company_owned_by_fund': 0.00033333},
            {'name': 'MICROSOFT CORP', 'cusip': '594918104', 'ticker': 'MSFT',
             'market_value_in_fund': 8000000.0, 'percentage_of_fund': 0.0648,
             'shares_held_by_fund_str': '20000', 'total_outstanding_shares': "N/A",
             'percentage_of_company_owned_by_fund': "N/A"}
        ], "status": "Analysis complete."}
    formatted_report = format_data_for_email(dummy_analysis_result)
    print("\n--- Formatted Report ---")
    print(formatted_report)
    print("\n--- Testing Gmail Send (will likely fail in subtask env without credentials.json/auth) ---")
    test_recipient = "testuser@example.com"
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"SKIPPING email test: {CREDENTIALS_FILE} not found.")
    else:
        print(f"ATTEMPTING email send. Requires browser auth if first run/token invalid.")
        success = send_email_report(test_recipient, "Fund Ownership Analysis Report (Test)", formatted_report)
        if success: print(f"Email func executed for {test_recipient}.")
        else: print(f"Email func failed/skipped for {test_recipient}.")
