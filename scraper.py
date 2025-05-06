import time
import datetime
import csv
import os
import argparse
from dotenv import load_dotenv
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
from thefuzz import fuzz

load_dotenv()

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
            # Define headers for campaigns.csv
            fieldnames = ['campaign_url', 'total_donors_count', 'amount_raised', 'campaign_creator', 'funds_receiver', 'scraped_at']
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
            reader = csv.reader(f)
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
    fieldnames = ['campaign_url', 'total_donors_count', 'amount_raised', 'campaign_creator', 'funds_receiver', 'scraped_at']
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
            # Use this for now, but this could be made more robust (e.g., backup before write).

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
    options.add_argument('--headless') # Uncomment for headless mode
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920x1080')
    
    # Load ChromeDriver path from environment variable
    chromedriver_path = os.getenv('CHROMEDRIVER_PATH')
    if not chromedriver_path:
        print("Error: CHROMEDRIVER_PATH environment variable not set.")
        print("Please create a .env file in the project root and add: CHROMEDRIVER_PATH=/path/to/your/chromedriver")
        return # Exit the function if path is not found

    service = ChromeService(executable_path=chromedriver_path)
    driver = None # Initialize driver to None

    scraped_at_timestamp = datetime.datetime.now().isoformat()
    print(f"[{scraped_at_timestamp}] Starting scrape for: {url}")

    total_donors_on_button = "N/A"
    amount_raised_text = "N/A"
    campaign_creator = "N/A"
    funds_receiver = "N/A"

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

        # --- 1. Extract Total Donors (from button), Amount Raised, Creator, Fund Receiver ---
        try:
            # Primary attempt: Use the more anchored XPath based on the provided parent div structure
            give_button_counter_locator_xpath = (By.XPATH, "//div[contains(@class, 'lg:flex') and contains(@class, 'space-y-4')]/button[contains(@class, 'give-button') and contains(@class, 'lg:flex')]//span[contains(@class, 'ml-auto') and contains(@class, 'button__counter--give')]")
            give_counter_element = wait.until(EC.visibility_of_element_located(give_button_counter_locator_xpath))
            total_donors_on_button = give_counter_element.text.strip()
            print(f"[{datetime.datetime.now().isoformat()}] Total donors on button (using primary XPath): {total_donors_on_button}")
        except TimeoutException:
            print("Could not find the total donors on button counter using primary XPath.")
            # Fallback to CSS selector if XPath fails
            try:
                print("Attempting fallback CSS selector for total donors on button counter...")
                give_button_counter_selector = "button.give-button.lg\:flex span.ml-auto.button__counter--give"
                give_counter_element = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, give_button_counter_selector)))
                total_donors_on_button = give_counter_element.text.strip()
                print(f"[{datetime.datetime.now().isoformat()}] Total donors on button (using fallback CSS selector): {total_donors_on_button}")
            except TimeoutException:
                print("Fallback CSS selector for total donors on button counter also failed.")
            except Exception as e_css:
                print(f"An error occurred while extracting total donors on button using fallback CSS selector: {e_css}")
        except Exception as e:
            print(f"An error occurred while extracting total donors on button: {e}")

        # Parse static page details with BeautifulSoup after main content is likely loaded
        # It's good to do this after an initial wait/element interaction like the one above
        time.sleep(2) # Give a brief moment for JS to settle if any post-load changes occur
        page_soup = BeautifulSoup(driver.page_source, 'html.parser')

        # Extract Campaign Creator
        try:
            creator_div_texts = page_soup.find_all("div", class_="mt-4")
            for div_text_element in creator_div_texts:
                if "Campaign created by" in div_text_element.get_text():
                    creator_span = div_text_element.find("span", class_="font-semibold")
                    if creator_span:
                        campaign_creator = creator_span.text.strip()
                        print(f"[{datetime.datetime.now().isoformat()}] Campaign created by: {campaign_creator}")
                        break
            if campaign_creator == "N/A":
                print("Could not find 'Campaign created by' information.")
        except Exception as e:
            print(f"An error occurred while extracting campaign creator: {e}")

        # Extract Funds Receiver
        try:
            receiver_p_texts = page_soup.find_all("p", class_="mt-4 text-base")
            for p_text_element in receiver_p_texts:
                if "Campaign funds will be received by" in p_text_element.get_text():
                    receiver_span = p_text_element.find("span", class_="font-semibold")
                    if receiver_span:
                        funds_receiver = receiver_span.text.strip()
                        print(f"[{datetime.datetime.now().isoformat()}] Funds will be received by: {funds_receiver}")
                        break
            if funds_receiver == "N/A":
                 print("Could not find 'Campaign funds will be received by' information.")
        except Exception as e:
            print(f"An error occurred while extracting funds receiver: {e}")
        
        # Extract Amount Raised (existing logic)
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
            time.sleep(0.5)

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
            'campaign_creator': campaign_creator,
            'funds_receiver': funds_receiver,
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

def get_aggregated_donor_data(top_n=10):
    """
    Reads donations.csv, processes data, groups similar donor names,
    and returns aggregated top donor data and alias map.
    """
    if not os.path.exists(DONATIONS_CSV):
        print(f"Error: {DONATIONS_CSV} not found. Scrape some data first.")
        return None, None

    try:
        df = pd.read_csv(DONATIONS_CSV)
    except pd.errors.EmptyDataError:
        print(f"Error: {DONATIONS_CSV} is empty. Scrape some data first.")
        return None, None
    except Exception as e:
        print(f"Error reading {DONATIONS_CSV}: {e}")
        return None, None

    if df.empty:
        print(f"{DONATIONS_CSV} contains no data. Scrape some data first.")
        return None, None

    df['amount_cleaned'] = df['amount'].astype(str).str.replace(r'[$,USD\s]', '', regex=True)
    df['amount_cleaned'] = pd.to_numeric(df['amount_cleaned'], errors='coerce')
    df.dropna(subset=['amount_cleaned'], inplace=True)

    anonymous_patterns = ["anonymous", "anonymous giver"]
    df_filtered = df[~df['donor_name'].astype(str).str.lower().isin(anonymous_patterns)]
    df_filtered = df_filtered[~df_filtered['donor_name'].isin(["Anonymous Giver", "Anonymous"])]

    if df_filtered.empty:
        print("No non-anonymous donations with valid amounts found.")
        return None, None

    df_filtered['normalized_donor_name'] = df_filtered['donor_name'].astype(str).str.lower().str.strip()
    normalized_to_originals_map = {}
    for _, row in df_filtered.iterrows():
        norm_name = row['normalized_donor_name']
        orig_name = str(row['donor_name']).strip()
        if norm_name not in normalized_to_originals_map:
            normalized_to_originals_map[norm_name] = set()
        normalized_to_originals_map[norm_name].add(orig_name)

    unique_normalized_names = list(df_filtered['normalized_donor_name'].unique())
    normalized_name_groups = []
    processed_indices = set()
    similarity_threshold = 88

    for i in range(len(unique_normalized_names)):
        if i in processed_indices:
            continue
        current_normalized_name = unique_normalized_names[i]
        current_normalized_group = [current_normalized_name]
        processed_indices.add(i)
        for j in range(i + 1, len(unique_normalized_names)):
            if j in processed_indices:
                continue
            other_normalized_name = unique_normalized_names[j]
            if fuzz.token_sort_ratio(current_normalized_name, other_normalized_name) > similarity_threshold:
                current_normalized_group.append(other_normalized_name)
                processed_indices.add(j)
        normalized_name_groups.append(current_normalized_group)

    variant_to_canonical_normalized_map = {}
    canonical_normalized_to_all_original_aliases_map = {}
    for norm_group in normalized_name_groups:
        if not norm_group: continue
        canonical_normalized_name = sorted(norm_group)[0]
        all_original_aliases_for_this_group = set()
        for norm_name_in_group in norm_group:
            variant_to_canonical_normalized_map[norm_name_in_group] = canonical_normalized_name
            if norm_name_in_group in normalized_to_originals_map:
                all_original_aliases_for_this_group.update(normalized_to_originals_map[norm_name_in_group])
            else:
                all_original_aliases_for_this_group.add(norm_name_in_group)
        canonical_normalized_to_all_original_aliases_map[canonical_normalized_name] = all_original_aliases_for_this_group
    
    df_filtered['canonical_group_id'] = df_filtered['normalized_donor_name'].map(variant_to_canonical_normalized_map)
    df_filtered['canonical_group_id'].fillna(df_filtered['normalized_donor_name'], inplace=True)
    
    for group_id in df_filtered['canonical_group_id'].unique():
        if group_id not in canonical_normalized_to_all_original_aliases_map:
            if group_id in normalized_to_originals_map:
                 canonical_normalized_to_all_original_aliases_map[group_id] = normalized_to_originals_map[group_id]
            else:
                 canonical_normalized_to_all_original_aliases_map[group_id] = {group_id}

    top_donors_aggregated = df_filtered.groupby('canonical_group_id')['amount_cleaned'].sum().nlargest(top_n)
    
    if top_donors_aggregated.empty:
        print("No data to aggregate for top donors after fuzzy grouping and filtering.")
        return None, None
        
    return top_donors_aggregated, canonical_normalized_to_all_original_aliases_map


def visualize_top_donors():
    """Visualizes top 10 donors with aliases."""
    top_donors_aggregated, alias_map = get_aggregated_donor_data(top_n=10)

    if top_donors_aggregated is None or top_donors_aggregated.empty:
        print("No data to plot for top donors.")
        return

    plot_labels = []
    for canonical_id_from_index in top_donors_aggregated.index:
        original_aliases = sorted(list(alias_map.get(canonical_id_from_index, {str(canonical_id_from_index)})))
        if not original_aliases:
            plot_labels.append(str(canonical_id_from_index))
            continue
        primary_alias = original_aliases[0]
        other_aliases = original_aliases[1:]
        label = primary_alias
        if other_aliases:
            label += f" ({', '.join(other_aliases)})"
        plot_labels.append(label)

    plt.figure(figsize=(14, 9))
    bars = top_donors_aggregated.plot(kind='bar')
    if plot_labels:
        bars.set_xticklabels(plot_labels)
    plt.title('Top 10 Donors (Total Amount Donated - Grouped by Similar Names)')
    plt.xlabel('Donor Name (Aliases)')
    plt.ylabel('Total Amount Donated (USD)')
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    print("Displaying top donors plot...")
    plt.show()

def list_top_donors(top_n_to_list):
    """Lists the top N donors to the console with aliases and amounts."""
    if top_n_to_list <= 0:
        print("Number of donors to list must be a positive integer.")
        return

    top_donors_aggregated, alias_map = get_aggregated_donor_data(top_n=top_n_to_list)

    if top_donors_aggregated is None or top_donors_aggregated.empty:
        print(f"No data to list for top {top_n_to_list} donors.")
        return

    print(f"\n--- Top {len(top_donors_aggregated)} Donors (Grouped by Similar Names) ---")
    rank = 1
    for canonical_id, total_amount in top_donors_aggregated.items():
        original_aliases = sorted(list(alias_map.get(canonical_id, {str(canonical_id)})))
        primary_alias = original_aliases[0] if original_aliases else str(canonical_id)
        other_aliases_str = ""
        if len(original_aliases) > 1:
            other_aliases_str = f" (aka: {', '.join(original_aliases[1:])})"
        
        print(f"{rank}. {primary_alias}{other_aliases_str}: ${total_amount:,.2f}")
        rank += 1
    print("--- End of List ---")


def main():
    parser = argparse.ArgumentParser(description="Scrape GiveSendGo campaign data and optionally visualize or list donors.")
    
    scrape_input_group = parser.add_argument_group('Scraping Input (conditionally required)')
    input_method_group = scrape_input_group.add_mutually_exclusive_group()
    input_method_group.add_argument("-url", metavar='URL', help="A single GiveSendGo campaign URL to scrape.")
    input_method_group.add_argument("-file", metavar='FILEPATH', help="Path to a .txt file containing line-separated GiveSendGo URLs.")
    
    parser.add_argument("-rescrape", action="store_true", help="Rescrape URLs even if they appear in campaigns.csv. Default is to skip.")
    
    # Analysis options (mutually exclusive with each other for simplicity, and run independently of scraping)
    analysis_group = parser.add_argument_group('Analysis Options (run independently of scraping)')
    analysis_action_group = analysis_group.add_mutually_exclusive_group()
    analysis_action_group.add_argument("-visualize", action="store_true", help="Visualize top 10 donors from donations.csv and exit.")
    analysis_action_group.add_argument("-list", "--list_donors", metavar='N', type=int, help="List the top N donors from donations.csv to the console and exit.")

    args = parser.parse_args()

    init_csv_files() 

    if args.visualize:
        visualize_top_donors()
        return
    
    if args.list_donors is not None:
        list_top_donors(args.list_donors)
        return

    if not args.url and not args.file:
        print("Error: You must provide either -url or -file for scraping if not using -visualize or -list.")
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
        if scraped_campaigns_set:
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
        scrape_campaign(url_item, args.rescrape)

if __name__ == "__main__":
    main()