# GiveSendGo Scraper

This Python script scrapes campaign data and donation details from GiveSendGo campaign pages. It can save the data into CSV files and optionally visualize or list the top donors.

## Features

-   Scrapes campaign summary information (total donors, amount raised).
-   Scrapes individual donation details (donor name, amount, relative time, comment).
-   Handles "Load More" functionality to retrieve all available donations.
-   Saves data into two CSV files:
    -   `campaigns.csv`: Stores campaign-level summary data (updates existing entries or adds new ones).
    -   `donations.csv`: Stores individual donation data (adds new donations, avoids duplicates if rescraping).
-   Command-line interface for specifying input:
    -   Scrape a single URL.
    -   Scrape multiple URLs from a text file.
-   Option to rescrape previously processed URLs.
-   Option to skip previously scraped URLs (default behavior).
-   Analysis options (run independently of scraping):
    -   Visualize the top 10 non-anonymous donors based on total donation amounts, grouping similar names.
    -   List the top N non-anonymous donors to the console, grouping similar names and showing aliases.

## Prerequisites

1.  **Python 3.x**: Ensure you have Python 3 installed.
2.  **Google Chrome**: The script uses Selenium with ChromeDriver.
3.  **ChromeDriver**:
    *   Download the ChromeDriver version that matches your installed Google Chrome browser version from [https://chromedriver.chromium.org/downloads](https://chromedriver.chromium.org/downloads) or [https://googlechromelabs.github.io/chrome-for-testing/](https://googlechromelabs.github.io/chrome-for-testing/).
    *   Place the `chromedriver` executable in a known location on your system.
4.  **`.env` File for ChromeDriver Path**:
    *   In the root directory of the project, create a file named `.env`.
    *   Add the following line to it, replacing `/path/to/your/chromedriver` with the actual full path to your `chromedriver` executable:
        ```
        CHROMEDRIVER_PATH="/path/to/your/chromedriver"
        ```
        Example: `CHROMEDRIVER_PATH="/Users/yourname/Downloads/chromedriver-mac-arm64/chromedriver"`
5.  **Virtual Environment (Recommended)**:
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```
6.  **Python Packages**: Install the required packages using the `requirements.txt` file:
    ```bash
    pip install -r requirements.txt
    ```
    (This will install `selenium`, `beautifulsoup4`, `pandas`, `matplotlib`, `thefuzz`, `python-Levenshtein`, and `python-dotenv`.)

## Usage

The script is run from the command line. Ensure your virtual environment is activated if you're using one.

**Basic Scraping Commands:**

*   **Scrape a single URL:**
    ```bash
    python scraper.py -url "https://www.givesendgo.com/yourcampaignurl"
    ```

*   **Scrape URLs from a file:**
    Create a text file (e.g., `urls.txt`) with one GiveSendGo URL per line.
    ```bash
    python scraper.py -file urls.txt
    ```

**Scraping Options:**

*   **Rescrape URLs:**
    By default, the script skips URLs already present in `campaigns.csv` for full scraping (it will still update the campaign summary if the URL is provided again, but won't re-fetch all donations unless `-rescrape` is used). Use `-rescrape` to force re-processing of donations, adding only new ones not previously logged for that campaign.
    ```bash
    python scraper.py -url "https://www.givesendgo.com/yourcampaignurl" -rescrape
    python scraper.py -file urls.txt -rescrape
    ```

**Analysis Options (run independently of scraping):**

*   **Visualize Top Donors:**
    Displays a bar chart of the top 10 non-anonymous donors (names grouped by similarity).
    ```bash
    python scraper.py -visualize
    ```

*   **List Top N Donors:**
    Prints the top N non-anonymous donors (names grouped by similarity) to the console.
    ```bash
    python scraper.py -list 10  # Lists the top 10 donors
    python scraper.py --list_donors 5 # Lists the top 5 donors
    ```

**Help:**
To see all available options:
```bash
python scraper.py -h
```

## Output Files

-   `campaigns.csv`: Contains summary data for each scraped campaign. If a campaign is scraped again, its entry is updated with the latest information.
    -   Columns: `campaign_url`, `total_donors_count`, `amount_raised`, `scraped_at`
-   `donations.csv`: Contains details for each individual donation. When rescraping, only new, previously unlogged donations for a campaign are added.
    -   Columns: `campaign_url`, `donor_name`, `amount`, `donation_relative_time`, `comment`, `scraped_at`

## Notes

-   Be respectful of the website's terms of service.
-   Web page structures can change, which might break the selectors used in the script. If the script fails to find elements, the CSS/XPath selectors in `scraper.py` may need to be updated.
-   Ensure your `.env` file is included in your `.gitignore` file to prevent committing your local ChromeDriver path to version control.