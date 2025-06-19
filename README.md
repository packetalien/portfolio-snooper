# Fund Ownership Analyzer

## Description

The Fund Ownership Analyzer is a Python application designed to provide insights into the holdings of mutual funds and ETFs. It fetches data from SEC EDGAR filings to determine a fund's holdings and then uses the Alpha Vantage API to gather information about the underlying companies, including calculating the approximate percentage of a company's stock owned by the analyzed fund. The results are delivered as a formatted report via email using the Gmail API.

## Features

*   Retrieves and parses NPORT-P (and N-Q as fallback) filings from SEC EDGAR.
*   Extracts detailed fund holdings: stock name, CUSIP, ticker, market value, shares, and percentage of fund assets.
*   Fetches total outstanding shares for each holding using Alpha Vantage API.
*   Calculates the percentage of each underlying company owned by the fund.
*   Generates a text-based report summarizing the analysis.
*   Sends the report to a specified email address using the Gmail API (requires user authentication via OAuth 2.0).
*   Command-Line Interface (CLI) for easy operation.
*   Handles API rate limits and missing data gracefully.

## Prerequisites

*   Python 3.7+
*   `pip` (Python package installer)
*   Access to a Gmail account (for sending email reports).
*   An Alpha Vantage API Key.
*   Google Cloud Project for Gmail API access.

## Setup Instructions

1.  **Clone the Repository (if applicable) or Download Files:**
    Ensure you have all the project files (`main.py`, `fund_analyzer.py`, `sec_parser.py`, `report_generator.py`, `requirements.txt`) in a single directory.

2.  **Create a Virtual Environment (Recommended):**
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install Dependencies:**
    Navigate to the project directory in your terminal and run:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up Alpha Vantage API Key:**
    *   Visit [Alpha Vantage](https://www.alphavantage.co/support/#api-key) to obtain a free API key.
    *   You can set this key as an environment variable named `ALPHA_VANTAGE_API_KEY`.
        *   On Linux/macOS: `export ALPHA_VANTAGE_API_KEY="YOUR_KEY_HERE"` (add to your `.bashrc` or `.zshrc` for persistence).
        *   On Windows: `set ALPHA_VANTAGE_API_KEY="YOUR_KEY_HERE"` (in Command Prompt) or `$env:ALPHA_VANTAGE_API_KEY="YOUR_KEY_HERE"` (in PowerShell).
    *   Alternatively, you can create a `.env` file in the project root directory with the line:
        `ALPHA_VANTAGE_API_KEY="YOUR_KEY_HERE"`
    *   You can also provide the key directly via the `--alpha_vantage_key` CLI argument when running the application.
    *   **Note:** The free Alpha Vantage 'demo' key is heavily restricted and may only work for fetching data for the 'IBM' ticker or quickly hit rate limits. A personal free key is recommended for better results.

5.  **Set up Gmail API Credentials:**
    This is required to allow the application to send emails on your behalf.
    *   Go to the [Google Cloud Console](https://console.cloud.google.com/).
    *   Create a new project (or select an existing one).
    *   Enable the **Gmail API** for your project.
        *   Search for "Gmail API" in the marketplace or API library and enable it.
    *   Create OAuth 2.0 Client ID credentials:
        *   Go to "Credentials" in the APIs & Services section.
        *   Click "Create Credentials" -> "OAuth client ID".
        *   If prompted, configure the OAuth consent screen (User Type: External, provide app name, user support email, developer contact). For scopes, you can leave it blank for now or add `../auth/gmail.send` if prompted during consent screen setup.
        *   Select "Desktop app" as the Application type.
        *   Give it a name (e.g., "Fund Analyzer CLI").
        *   Click "Create".
    *   Download the credentials JSON file. It will likely be named `client_secret_XXXXXXXX.json`. **Rename this file to `credentials.json` and place it in the root directory of this project.**

    **Important:** The first time you run the application and it attempts to send an email, a browser window will open asking you to log in to your Google account and grant the application permission to send emails. After successful authorization, a `token.json` file will be created in the project directory to store your authorization tokens for future use.

## Usage

The application is run from the command line using `main.py`.

**Command-Line Arguments:**

*   `--fund FUND_IDENTIFIER`: (Required) The ticker symbol or name of the mutual fund/ETF to analyze (e.g., "VFINX", "SPY"). Note: CIK resolution from name/ticker is currently basic.
*   `--email RECIPIENT_EMAIL`: (Required) The email address where the analysis report will be sent.
*   `--alpha_vantage_key YOUR_API_KEY`: (Optional) Your Alpha Vantage API key. If not provided, it will try to use the `ALPHA_VANTAGE_API_KEY` environment variable, then default to 'demo'.

**Example Command:**

```bash
python main.py --fund "VFINX" --email "your_email@example.com"
```

Or, if you have your Alpha Vantage key in the environment:

```bash
python main.py --fund "SPY" --email "your_email@example.com"
```

To use a specific Alpha Vantage key via CLI:
```bash
python main.py --fund "VTSAX" --email "another_email@example.com" --alpha_vantage_key "YOUR_ACTUAL_AV_KEY"
```

**First Run (Gmail Authentication):**
When you run a command that triggers email sending for the first time (or if `token.json` is invalid/deleted), your web browser should open. You'll need to:
1.  Choose the Google account associated with the `credentials.json` you set up.
2.  If you see a "Google hasn’t verified this app" screen, click "Advanced" and then "Go to [Your App Name] (unsafe)". This is expected for local test applications that haven't gone through Google's formal verification process.
3.  Grant the application permission to "Send email on your behalf".
4.  The browser will confirm, and you can close the tab. The application will then proceed to send the email. A `token.json` file will be saved in your project directory.

## Project File Structure

*   `main.py`: CLI entry point for the application.
*   `fund_analyzer.py`: Core logic for orchestrating fund analysis, including calls to SEC parser and Alpha Vantage.
*   `sec_parser.py`: Handles downloading and parsing SEC EDGAR filings (NPORT-P, N-Q).
*   `report_generator.py`: Formats the analysis data into an email report and handles Gmail API interaction.
*   `requirements.txt`: Lists Python package dependencies.
*   `tests/`: Directory containing unit tests.
    *   `test_sec_parser.py`
    *   `test_fund_analyzer.py`
    *   `test_report_generator.py`
*   `roadmap.md`: Outlines potential future enhancements for the application.
*   `.env` (optional, if created by user): For storing `ALPHA_VANTAGE_API_KEY`.
*   `credentials.json` (user-provided): OAuth 2.0 client credentials for Gmail API.
*   `token.json` (generated): Stores user's Gmail API access/refresh tokens after successful OAuth.

## Running Unit Tests

To run the unit tests, navigate to the project's root directory and execute:

```bash
python -m unittest discover tests
```

To run a specific test file:
```bash
python -m unittest tests.test_sec_parser
```

## Current Limitations

*   **CIK Resolution:** The current mechanism for resolving a fund ticker/name to an SEC CIK is a basic placeholder. For reliable analysis of various funds, this needs to be made more robust.
*   **Alpha Vantage Demo Key:** The 'demo' key for Alpha Vantage is severely rate-limited and often only supports fetching detailed company overview data for the 'IBM' ticker. A personal free key from Alpha Vantage is highly recommended.
*   **Ticker Availability:** NPORT-P filings do not always contain explicit ticker symbols for all holdings (CUSIP is more common). The application currently prioritizes holdings with tickers for Alpha Vantage lookups. A CUSIP-to-ticker mapping could enhance this.
*   **SEC Edgar Data Availability:** The `sec-edgar-downloader` library relies on specific SEC data URLs. If these change or are unavailable for certain CIKs, downloading may fail.

## Future Development

See the `roadmap.md` file for a list of planned and potential future enhancements.
