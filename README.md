# GiveSendGo Scraper

This Python script scrapes campaign data and donation details from GiveSendGo campaign pages. It can save the data into CSV files and optionally visualize the top donors.

## Features

-   Scrapes campaign summary information (total donors, amount raised).
-   Scrapes individual donation details (donor name, amount, relative time, comment).
-   Handles "Load More" functionality to retrieve all available donations.
-   Saves data into two CSV files:
    -   `campaigns.csv`: Stores campaign-level summary data.
    -   `donations.csv`: Stores individual donation data.
-   Command-line interface for specifying input:
    -   Scrape a single URL.
    -   Scrape multiple URLs from a text file.
-   Option to rescrape previously processed URLs.
-   Option to skip previously scraped URLs (default behavior).
-   Option to visualize the top 10 non-anonymous donors based on total donation amounts.

## Prerequisites

1.  **Python 3.x**: Ensure you have Python 3 installed.
2.  **pip**: Python package installer.
3.  **Google Chrome**: The script uses Selenium with ChromeDriver.
4.  **ChromeDriver**:
    *   Download the ChromeDriver version that matches your installed Google Chrome browser version from [https://chromedriver.chromium.org/downloads](https://chromedriver.chromium.org/downloads) or [https://googlechromelabs.github.io/chrome-for-testing/](https://googlechromelabs.github.io/chrome-for-testing/).
    *   Place the `chromedriver` executable in a known location (e.g., within the project directory in a `driver` subfolder, or a location in your system's PATH).
    *   **Update the `chromedriver_path` variable in `scraper.py`** to point to the location of your `chromedriver` executable.
        ```python
        # In scraper.py
        chromedriver_path = '/path/to/your/chromedriver' # e.g., '/Users/yourname/Projects/gsg-scraper/driver/chromedriver'
        ```
5.  **Python Packages**: Install the required packages using the `requirements.txt` file:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

The script is run from the command line.

**Basic Commands:**

*   **Scrape a single URL:**
    ```bash
    python scraper.py -url "https://www.givesendgo.com/yourcampaignurl"
    ```

*   **Scrape URLs from a file:**
    Create a text file (e.g., `urls.txt`) with one GiveSendGo URL per line.
    ```bash
    python scraper.py -file urls.txt
    ```

**Options:**

*   **Rescrape URLs:**
    By default, the script skips URLs already present in `campaigns.csv`. Use `-rescrape` to force rescraping.
    ```bash
    python scraper.py -url "https://www.givesendgo.com/yourcampaignurl" -rescrape
    python scraper.py -file urls.txt -rescrape
    ```

*   **Visualize Top Donors:**
    This option reads `donations.csv` and displays a bar chart of the top 10 non-anonymous donors. It does not perform any scraping.
    ```bash
    python scraper.py -visualize
    ```

**Help:**
To see all available options:
```bash
python scraper.py -h
```

## Output Files

-   `campaigns.csv`: Contains summary data for each scraped campaign.
    -   Columns: `campaign_url`, `total_donors_count`, `amount_raised`, `scraped_at`
-   `donations.csv`: Contains details for each individual donation.
    -   Columns: `campaign_url`, `donor_name`, `amount`, `donation_relative_time`, `comment`, `scraped_at`

## Notes

-   Avoid overly aggressive scraping. The script includes `time.sleep()` calls to be polite.
-   Web page structures can change, which might break the selectors used in the script. If the script fails to find elements, the CSS selectors in `scraper.py` may need to be updated.