import time
import datetime
import csv
import os
import argparse
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from bs4 import BeautifulSoup
import pandas as pd
import matplotlib.pyplot as plt
import traceback

DONATIONS_CSV = 'donations.csv'
CAMPAIGNS_CSV = 'campaigns.csv'

def init_csv_files():
    """Initializes CSV files with headers if they don't exist."""
    if not os.path.exists(DONATIONS_CSV):
        with open(DONATIONS_CSV, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['campaign_url', 'donor_name', 'amount', 'donation_relative_time', 'comment', 'scraped_at'])
    
    if not os.path.exists(CAMPAIGNS_CSV):
        with open(CAMPAIGNS_CSV, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            # Define headers for campaigns.csv
            fieldnames = ['campaign_url', 'total_donors_count', 'amount_raised', 'scraped_at']
            dict_writer = csv.DictWriter(f, fieldnames=fieldnames)
            dict_writer.writeheader()

def append_to_csv(filepath, row_data):
    """Appends a row to the specified CSV file."""
    with open(filepath, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(row_data)

def get_scraped_campaigns():
    """Reads the campaigns CSV and returns a set of scraped campaign URLs."""
    scraped = set()
    if not os.path.exists(CAMPAIGNS_CSV):
        return scraped
    try:
        with open(CAMPAIGNS_CSV, 'r', newline='', encoding='utf-8') as f:
            # Skip header row before reading
            next(f, None) 
            reader = csv.reader(f) # Use csv.reader to avoid issues if columns are missing in some rows
            for row in reader:
                if row: # Ensure row is not empty
                    scraped.add(row[0]) # campaign_url is the first column
    except FileNotFoundError:
        pass 
    except Exception as e:
        print(f"Error reading {CAMPAIGNS_CSV}: {e}")
    return scraped

def get_existing_donation_keys_for_url(url_to_check):
    """
    Reads donations.csv and returns a set of unique keys for donations
    already saved for the given campaign URL.
    A key is (donor_name, amount, relative_time, comment_preview).
    """
    existing_keys = set()
    if not os.path.exists(DONATIONS_CSV):
        return existing_keys
    try:
        with open(DONATIONS_CSV, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['campaign_url'] == url_to_check:
                    comment_preview = row.get('comment', '')[:50] if row.get('comment') else '' # Preview of comment
                    key = (
                        row.get('donor_name', 'Anonymous'),
                        row.get('amount', 'N/A'),
                        row.get('donation_relative_time', 'N/A'),
                        comment_preview
                    )
                    existing_keys.add(key)
    except Exception as e:
        print(f"Error reading existing donation keys from {DONATIONS_CSV} for {url_to_check}: {e}")
    return existing_keys

def save_or_update_campaign_summary(campaign_data_dict):
    """Saves or updates a campaign's summary in campaigns.csv."""
    fieldnames = ['campaign_url', 'total_donors_count', 'amount_raised', 'scraped_at']
    campaign_url_to_update = campaign_data_dict['campaign_url']
    
    rows = []
    updated = False

    if os.path.exists(CAMPAIGNS_CSV):
        try:
            with open(CAMPAIGNS_CSV, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['campaign_url'] == campaign_url_to_update:
                        rows.append(campaign_data_dict) # Replace with new data
                        updated = True
                    else:
                        rows.append(row)
        except Exception as e:
            print(f"Error reading {CAMPAIGNS_CSV} for update: {e}. Will attempt to overwrite.")
            # If reading fails catastrophically, we might lose old data if we proceed to write.
            # For now, we'll proceed, but this could be made more robust (e.g., backup before write).

    if not updated:
        rows.append(campaign_data_dict) # Add as new if not found or file didn't exist/was empty

    try:
        with open(CAMPAIGNS_CSV, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
    except Exception as e:
        print(f"Error writing updated data to {CAMPAIGNS_CSV}: {e}")

def scrape_campaign(url, rescrape_mode=False):  # Added rescrape_mode parameter
    """Scrapes donation data from a given GiveSendGo campaign URL."""
    options = webdriver.ChromeOptions()
    # options.add_argument('--headless') # Uncomment for headless mode
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920x1080')
    
    chromedriver_path = '/Users/alberthwang/Library/Projects/gsg-scraper/driver/chromedriver'
    service = ChromeService(executable_path=chromedriver_path)
    driver = None # Initialize driver to None

    scraped_at_timestamp = datetime.datetime.now().isoformat()
    print(f"[{scraped_at_timestamp}] Starting scrape for: {url}")

    total_donors_on_button = "N/A"
    amount_raised_text = "N/A"

    existing_donation_keys_this_url = set()
    if rescrape_mode:
        print(f"Rescrape mode active for {url}. Checking for existing donations to avoid duplicates.")
        existing_donation_keys_this_url = get_existing_donation_keys_for_url(url)
        if existing_donation_keys_this_url:
            print(f"Found {len(existing_donation_keys_this_url)} existing donation entries for this URL.")

    try:
        driver = webdriver.Chrome(service=service, options=options)
        driver.get(url)
        wait = WebDriverWait(driver, 20) # General wait time

        # --- 1. Extract Total Donors (from button) & Amount Raised ---
        try:
            # Updated XPath to target the span within the visible desktop "Give" button
            give_button_counter_locator = (By.XPATH, "//button[contains(@class, 'give-button') and contains(@class, 'lg:flex')]//span[contains(@class, 'button__counter--give')]")
            give_counter_element = wait.until(EC.visibility_of_element_located(give_button_counter_locator))
            total_donors_on_button = give_counter_element.text.strip()
            print(f"[{datetime.datetime.now().isoformat()}] Total donors on button: {total_donors_on_button}")
        except TimeoutException:
            print("Could not find the total donors on button counter. The element might be missing, hidden, or the page structure may have changed.")
        except Exception as e:
            print(f"An error occurred while extracting total donors on button: {e}")

        try:
            details_container_selectors = ["div.donation__details", "div.camp-details__wrapper", "div.max-w-md.space-y-10"]
            details_container = None
            for selector in details_container_selectors:
                try:
                    details_container = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, selector)))
                    if details_container:
                        break
                except TimeoutException:
                    continue
            
            if details_container:
                soup_details = BeautifulSoup(details_container.get_attribute('outerHTML'), 'html.parser')
                raised_label_p = soup_details.find("p", string=lambda text: text and "Raised:" in text.strip())
                if raised_label_p:
                    amount_raised_p = raised_label_p.find_next_sibling("p")
                    if amount_raised_p:
                        amount_raised_text = amount_raised_p.text.strip()
                        print(f"[{datetime.datetime.now().isoformat()}] Amount raised: {amount_raised_text}")
                if amount_raised_text == "N/A": # If first method failed
                    potential_raised_elements = soup_details.find_all("p", class_="text-base")
                    for i, p_element in enumerate(potential_raised_elements):
                        if "Raised:" in p_element.text:
                            if i + 1 < len(potential_raised_elements):
                                amount_raised_text = potential_raised_elements[i+1].text.strip()
                                print(f"[{datetime.datetime.now().isoformat()}] Amount raised (fallback): {amount_raised_text}")
                                break
                if amount_raised_text == "N/A":
                     print("Could not find 'Raised:' label or its value.")
            else:
                print("Could not find campaign details section for amount raised.")

        except Exception as e:
            print(f"An error occurred while extracting amount raised: {e}")


        # --- 2. Extract Recent Donations with "Load More" ---
        processed_donation_ids = set() 
        consecutive_zero_donation_loads = 0

        donation_item_selector = "div.recent-donations__loop"
        donor_name_selector = "span.font-bold"
        amount_selector = "div.donation__amount span"
        relative_time_selector = "span.text-xs"
        comment_selector = "p.mt-2"

        while True:
            time.sleep(0.5) # Increased wait for content to load/settle

            soup = BeautifulSoup(driver.page_source, 'html.parser')
            recent_donations_container = soup.select_one("div.recent-donations__wrapper")
            
            if not recent_donations_container:
                print("Could not find recent donations container. Ending donation scrape for this campaign.")
                break

            donation_elements = recent_donations_container.select(donation_item_selector)
            new_donations_found_in_batch = 0

            for item in donation_elements:
                donation_html_id = str(item) # Use HTML content as a simple ID
                if donation_html_id in processed_donation_ids:
                    continue

                donor_name_tag = item.select_one(donor_name_selector)
                amount_tag = item.select_one(amount_selector)
                relative_time_tag = item.select_one(relative_time_selector)
                comment_tag = item.select_one(comment_selector)

                donor_name = donor_name_tag.text.strip() if donor_name_tag else "Anonymous"
                amount = amount_tag.text.strip() if amount_tag else "N/A"
                relative_time_str = relative_time_tag.text.strip() if relative_time_tag else "N/A"
                comment = comment_tag.text.strip() if comment_tag else ""
                
                # --- Check for duplicates if in rescrape_mode ---
                if rescrape_mode:
                    current_donation_comment_preview = comment[:50]
                    current_donation_key = (donor_name, amount, relative_time_str, current_donation_comment_preview)
                    if current_donation_key in existing_donation_keys_this_url:
                        processed_donation_ids.add(donation_html_id) # Still add to in-session set
                        new_donations_found_in_batch += 1 # Count it as "found" in this batch for load more logic
                        continue # Skip appending to CSV

                donation_csv_row = [url, donor_name, amount, relative_time_str, comment, scraped_at_timestamp]
                append_to_csv(DONATIONS_CSV, donation_csv_row)
                
                processed_donation_ids.add(donation_html_id)
                new_donations_found_in_batch += 1
            
            print(f"Found {new_donations_found_in_batch} new unique donations in this batch. Total unique donations processed this session: {len(processed_donation_ids)}")

            if new_donations_found_in_batch == 0:
                consecutive_zero_donation_loads += 1
            else:
                consecutive_zero_donation_loads = 0 # Reset if new donations found

            if consecutive_zero_donation_loads >= 3:
                print("Stopped clicking 'Load More' after 3 consecutive attempts with 0 new donations.")
                break
            
            try:
                load_more_button_xpath = "//div[contains(@class, 'recent-donations__wrapper')]//button[contains(., 'Load More')]"
                load_more_button = WebDriverWait(driver, 7).until( # Increased wait for button
                    EC.element_to_be_clickable((By.XPATH, load_more_button_xpath))
                )
                print("Clicking 'Load More'...")
                driver.execute_script("arguments[0].scrollIntoView(true);", load_more_button) # Scroll to button
                time.sleep(0.5) # Brief pause after scroll
                driver.execute_script("arguments[0].click();", load_more_button)
            except TimeoutException:
                print("'Load More' button not found or not clickable. Assuming all donations loaded.")
                break
            except Exception as e:
                print(f"Error clicking 'Load More' button: {e}")
                break
        
        # --- 3. Save Campaign Summary to CSV ---
        # Create a dictionary for the campaign data
        campaign_summary_data = {
            'campaign_url': url,
            'total_donors_count': total_donors_on_button,
            'amount_raised': amount_raised_text,
            'scraped_at': scraped_at_timestamp
        }
        save_or_update_campaign_summary(campaign_summary_data)
        print(f"Campaign summary saved/updated for {url}")

    except Exception as e:
        print(f"An overall error occurred during scraping {url}: {e}")
        traceback.print_exc() # Ensure traceback is imported and used
    finally:
        if driver is not None:
            driver.quit()
        print(f"[{datetime.datetime.now().isoformat()}] Finished scrape for: {url}")

def visualize_top_donors():
    """Reads donations.csv and visualizes top 10 non-anonymous donors."""
    if not os.path.exists(DONATIONS_CSV):
        print(f"Error: {DONATIONS_CSV} not found. Scrape some data first.")
        return

    try:
        df = pd.read_csv(DONATIONS_CSV)
    except pd.errors.EmptyDataError:
        print(f"Error: {DONATIONS_CSV} is empty. Scrape some data first.")
        return
    except Exception as e:
        print(f"Error reading {DONATIONS_CSV}: {e}")
        return

    if df.empty:
        print(f"{DONATIONS_CSV} contains no data. Scrape some data first.")
        return

    df['amount_cleaned'] = df['amount'].astype(str).str.replace(r'[$,USD\s]', '', regex=True)
    df['amount_cleaned'] = pd.to_numeric(df['amount_cleaned'], errors='coerce')
    df.dropna(subset=['amount_cleaned'], inplace=True)

    # Filter out various forms of anonymous donors (case-insensitive)
    anonymous_patterns = ["anonymous", "anonymous giver"] 
    df_filtered = df[~df['donor_name'].astype(str).str.lower().isin(anonymous_patterns)]
    # Additional exact case-sensitive filtering just in case
    df_filtered = df_filtered[~df_filtered['donor_name'].isin(["Anonymous Giver", "Anonymous"])]


    if df_filtered.empty:
        print("No non-anonymous donations with valid amounts found to visualize.")
        return

    top_donors = df_filtered.groupby('donor_name')['amount_cleaned'].sum().nlargest(10)

    if top_donors.empty:
        print("No data to plot for top donors after filtering.")
        return

    plt.figure(figsize=(12, 8))
    top_donors.sort_values(ascending=False).plot(kind='bar')
    plt.title('Top 10 Donors (Total Amount Donated)')
    plt.xlabel('Donor Name')
    plt.ylabel('Total Amount Donated (USD)')
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    print("Displaying top donors plot...")
    plt.show()

def main():
    parser = argparse.ArgumentParser(description="Scrape GiveSendGo campaign data and optionally visualize donors.")
    
    # Group for scraping input, not required if -visualize is used
    scrape_input_group = parser.add_argument_group('Scraping Input (required if not visualizing)')
    input_method_group = scrape_input_group.add_mutually_exclusive_group()
    input_method_group.add_argument("-url", metavar='URL', help="A single GiveSendGo campaign URL to scrape.")
    input_method_group.add_argument("-file", metavar='FILEPATH', help="Path to a .txt file containing line-separated GiveSendGo URLs.")
    
    parser.add_argument("-rescrape", action="store_true", help="Rescrape URLs even if they appear in campaigns.csv. Default is to skip.")
    parser.add_argument("-visualize", action="store_true", help="Visualize top 10 donors from donations.csv and exit. This option ignores URL/file inputs for scraping.")

    args = parser.parse_args()

    init_csv_files() # Ensure CSV files and headers exist

    if args.visualize:
        visualize_top_donors()
        return # Exit after visualization

    # If not visualizing, URL or file for scraping is required
    if not args.url and not args.file:
        print("Error: You must provide either -url or -file for scraping if -visualize is not used.")
        parser.print_help()
        return

    urls_to_scrape = []
    if args.url:
        urls_to_scrape.append(args.url)
    elif args.file:
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                urls_to_scrape = [line.strip() for line in f if line.strip()]
            if not urls_to_scrape:
                print(f"No URLs found in {args.file}")
                return
        except FileNotFoundError:
            print(f"Error: File not found at {args.file}")
            return
        except Exception as e:
            print(f"Error reading file {args.file}: {e}")
            return
    
    scraped_campaigns_set = set()
    if not args.rescrape:
        scraped_campaigns_set = get_scraped_campaigns()
        if scraped_campaigns_set: # Only print if set is not empty
             print(f"Found {len(scraped_campaigns_set)} previously scraped campaigns to potentially skip.")

    valid_urls_for_current_session = []
    for url_item in urls_to_scrape:
        if not url_item.startswith("https://www.givesendgo.com/"):
            print(f"Skipping invalid URL (must start with https://www.givesendgo.com/): {url_item}")
            continue
        
        if not args.rescrape and url_item in scraped_campaigns_set:
            print(f"Skipping already scraped URL (use -rescrape to override): {url_item}")
            continue
        valid_urls_for_current_session.append(url_item)

    if not valid_urls_for_current_session:
        print("No new URLs to scrape in this session.")
        return
    
    print(f"Preparing to scrape {len(valid_urls_for_current_session)} URL(s).")
    for url_item in valid_urls_for_current_session:
        scrape_campaign(url_item, args.rescrape) # Pass rescrape status

if __name__ == "__main__":
    main()