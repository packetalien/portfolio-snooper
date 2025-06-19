import argparse
import os
import sys # For sys.exit
from dotenv import load_dotenv

import fund_analyzer
import report_generator

# Load .env file if it exists, for ALPHA_VANTAGE_API_KEY
load_dotenv()

def main():
    parser = argparse.ArgumentParser(description="Analyze mutual fund ownership and email a report.")
    parser.add_argument("--fund", required=True, help="Ticker symbol or name of the mutual fund/ETF to analyze.")
    parser.add_argument("--email", required=True, help="Recipient's email address for the report.")
    # Gmail user for sending is handled by OAuth, so not needed as CLI arg if using OAuth.
    # If a different sending mechanism was added, it might be needed.

    parser.add_argument("--alpha_vantage_key",
                        default=os.getenv('ALPHA_VANTAGE_API_KEY', 'demo'),
                        help="Alpha Vantage API key. Overrides ALPHA_VANTAGE_API_KEY environment variable if set. Defaults to 'demo'.")

    args = parser.parse_args()

    print(f"Received request to analyze fund: {args.fund} and email report to: {args.email}")

    # Update Alpha Vantage API key in fund_analyzer if provided via CLI
    # The fund_analyzer module already gets it from os.getenv or defaults to 'demo'.
    # We need to ensure the CLI arg takes precedence if provided.
    # A simple way is to update the global API_KEY in fund_analyzer if it's designed to be mutable,
    # or pass it down. Let's assume fund_analyzer.API_KEY can be updated or it re-checks os.environ.
    # For better design, fund_analyzer functions could accept api_key as a parameter.
    # For now, we'll set the environment variable, which fund_analyzer.py already reads.
    if args.alpha_vantage_key:
        os.environ['ALPHA_VANTAGE_API_KEY'] = args.alpha_vantage_key
        # Update the module's variable if it's already loaded and uses a global
        if hasattr(fund_analyzer, 'API_KEY'):
             fund_analyzer.API_KEY = args.alpha_vantage_key
        print(f"Using Alpha Vantage API Key: {'*'*(len(args.alpha_vantage_key)-4) + args.alpha_vantage_key[-4:] if args.alpha_vantage_key != 'demo' else 'demo'}")


    print(f"\nStarting fund analysis for: {args.fund}...")
    analysis_data = fund_analyzer.analyze_fund_ownership(args.fund)

    if not analysis_data or analysis_data.get('status') != "Analysis complete.":
        print(f"\nFund analysis for {args.fund} could not be completed or failed.")
        if analysis_data:
            print(f"Status: {analysis_data.get('status', 'Unknown error during analysis.')}")
        # Optionally, still try to send a failure report
        error_report_subject = f"Fund Analysis FAILED for {args.fund}"
        error_report_body = f"Analysis for fund '{args.fund}' failed.\n"
        if analysis_data and analysis_data.get('status'):
            error_report_body += f"Reason: {analysis_data.get('status')}\n"
        else:
            error_report_body += "An unexpected error occurred during analysis.\n"

        print(f"\nAttempting to send failure notification to {args.email}...")
        if not os.path.exists(report_generator.CREDENTIALS_FILE):
            print(f"SKIPPING email send: {report_generator.CREDENTIALS_FILE} not found.")
        else:
            report_generator.send_email_report(args.email, error_report_subject, error_report_body)
        sys.exit(1) # Exit with an error code

    print(f"\nAnalysis for {args.fund} complete. Generating email report...")
    report_text = report_generator.format_data_for_email(analysis_data)

    email_subject = f"Fund Ownership Analysis: {analysis_data.get('fund_name', args.fund)}"

    print(f"\nAttempting to send analysis report to {args.email}...")
    if not os.path.exists(report_generator.CREDENTIALS_FILE):
        print(f"SKIPPING email send: {report_generator.CREDENTIALS_FILE} not found.")
        print(f"Report for {args.fund} was generated but not sent. Content preview:")
        print(report_text[:1000] + "..." if len(report_text) > 1000 else report_text)
    else:
        send_success = report_generator.send_email_report(args.email, email_subject, report_text)
        if send_success:
            print(f"Email report for {args.fund} successfully sent to {args.email}.")
        else:
            print(f"Failed to send email report for {args.fund} to {args.email}.")
            print("Report content was:")
            print(report_text[:1000] + "..." if len(report_text) > 1000 else report_text)

    print("\nApplication finished.")

if __name__ == '__main__':
    main()
