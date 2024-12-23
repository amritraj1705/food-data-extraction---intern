import itertools
import csv
import time
import traceback
import sys
from appium import webdriver
from appium.options.common.base import AppiumOptions
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Define Appium options
options = AppiumOptions()
options.load_capabilities({
    "platformName": "Android",
    "appium:platformVersion": "12",
    "appium:deviceName": "emulator-5554",
    "appium:automationName": "UiAutomator2",
    "appium:noReset": True,
    "appium:ensureWebviewsHavePages": True,
    "appium:newCommandTimeout": 3600,
    "appium:connectHardwareKeyboard": True
})

print("Initializing Appium driver...")
try:
    driver = webdriver.Remote("http://127.0.0.1:4723/wd/hub", options=options)
    print("Driver initialized successfully!")
except Exception as e:
    print(f"Error initializing Appium driver: {e}")
    sys.exit(1)

# Global dataset to store food details
dataset = []
processed_terms = set()

# File paths
data_file = "food_details_dataset.csv"
temp_file = "temp_processed_terms.txt"

# Function to load existing dataset and processed terms
def load_existing_data():
    try:
        with open(data_file, "r", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                dataset.append(row)
        print("Existing dataset loaded.")
    except FileNotFoundError:
        print("No existing dataset found. Starting fresh.")

    try:
        with open(temp_file, "r", encoding="utf-8") as file:
            for line in file:
                processed_terms.add(line.strip())
        print("Processed terms loaded from temporary file.")
    except FileNotFoundError:
        print("No temporary file found. Starting fresh.")

# Function to save dataset to a CSV file
def save_dataset_to_csv():
    try:
        keys = ["Modified Name", "Proteins", "Carbs", "Fats", "Fiber", "Item Details"]
        with open(data_file, "w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=keys)
            writer.writeheader()
            writer.writerows(dataset)
        print("Dataset saved to 'food_details_dataset.csv'")
    except Exception as e:
        print(f"Error saving dataset to CSV: {e}")

# Function to save processed terms to a temporary file
def save_processed_terms():
    try:
        with open(temp_file, "w", encoding="utf-8") as file:
            for term in processed_terms:
                file.write(term + "\n")
        print("Processed terms saved to temporary file.")
    except Exception as e:
        print(f"Error saving processed terms: {e}")

# Function to handle keyboard interruptions and cleanup
def safe_exit():
    print("\nKeyboard interruption detected! Cleaning up resources...")
    save_dataset_to_csv()
    save_processed_terms()
    try:
        driver.quit()
        print("Driver session closed.")
    except Exception as e:
        print(f"Error closing Appium driver: {e}")
    sys.exit(0)

# Function to check for duplicates
def is_duplicate_entry(modified_name):
    return any(entry["Modified Name"] == modified_name for entry in dataset)

# Function to process a single search term
def process_search_term(term, current_iter, total_iter, retry_limit=2):
    retries = 0
    while retries < retry_limit:
        try:
            print(f"Processing search term ({current_iter}/{total_iter}): '{term}'")

            # Wait for the search box
            search_field = WebDriverWait(driver, 15).until(
                EC.visibility_of_element_located(
                    (AppiumBy.XPATH, "//android.widget.EditText[@resource-id='com.healthifyme.basic:id/et_search']")
                )
            )
            search_field.click()  # Focus on the search box
            search_field.clear()  # Clear previous text
            search_field.send_keys(term)  # Enter the search term
            print(f"Search term '{term}' entered.")

            # Wait for search results to load
            WebDriverWait(driver, 20).until(
                lambda d: len(d.find_elements(
                    AppiumBy.XPATH, "//android.widget.ImageView[@resource-id='com.healthifyme.basic:id/iv_expand_icon']"
                )) > 0
            )
            print("Search results loaded.")

            # Locate all '+' buttons
            plus_buttons = driver.find_elements(
                AppiumBy.XPATH, "//android.widget.ImageView[@resource-id='com.healthifyme.basic:id/iv_expand_icon']"
            )

            # Process each result for this search term
            for index, plus_button in enumerate(plus_buttons):
                process_item(index, plus_button)

            processed_terms.add(term)
            break  # Exit the retry loop if successful
        except Exception as e:
            retries += 1
            print(f"Error processing search term '{term}': {e}. Retrying ({retries}/{retry_limit})...")
            time.sleep(5)  # Wait before retrying

# Function to process a single item
def process_item(index, plus_button, retry_limit=2):
    retries = 0
    while retries < retry_limit:
        try:
            print(f"Processing result {index + 1}...")
            plus_button.click()
            print("Plus button clicked.")

            # Wait for Macronutrients Breakdown page
            WebDriverWait(driver, 20).until(
                EC.visibility_of_element_located(
                    (AppiumBy.XPATH, "//android.widget.TextView[@text='Macronutrients Breakdown']")
                )
            )
            print("Macronutrients Breakdown page loaded.")

            # Extract required data
            modified_name = driver.find_element(AppiumBy.XPATH, "//android.widget.TextView[@resource-id='com.healthifyme.basic:id/tv_item_title']").text
            proteins = driver.find_element(AppiumBy.ID, "com.healthifyme.basic:id/tv_protein_value").text
            carbs = driver.find_element(AppiumBy.ID, "com.healthifyme.basic:id/tv_carbs_value").text
            fats = driver.find_element(AppiumBy.ID, "com.healthifyme.basic:id/tv_fat_value").text
            fiber = driver.find_element(AppiumBy.ID, "com.healthifyme.basic:id/tv_fiber_value").text
            item_details = driver.find_element(AppiumBy.XPATH, "//android.widget.TextView[@resource-id='com.healthifyme.basic:id/tv_item_details']").text

            # Check for duplicates
            if is_duplicate_entry(modified_name):
                print(f"Duplicate entry for {modified_name}. Skipping.")
                driver.back()
                return

            print(f"Extracted: {modified_name} | Proteins={proteins}, Carbs={carbs}, Fats={fats}, Fiber={fiber}")

            # Add to dataset
            dataset.append({
                "Modified Name": modified_name,
                "Proteins": proteins,
                "Carbs": carbs,
                "Fats": fats,
                "Fiber": fiber,
                "Item Details": item_details
            })

            driver.back()
            break
        except Exception as e:
            retries += 1
            print(f"Error processing result {index + 1}: {e}. Retrying ({retries}/{retry_limit})...")
            time.sleep(5)

# Main function to process all search terms
def search_and_capture_food():
    search_terms = ["".join(combo) for combo in itertools.product("abcdefghijklmnopqrstuvwxyz", repeat=3)]
    total_iterations = len(search_terms)

    for term_index, term in enumerate(search_terms, start=1):
        if term in processed_terms:
            continue
        try:
            process_search_term(term, term_index, total_iterations)
            if term_index % 10 == 0:  # Save dataset periodically
                save_dataset_to_csv()
                save_processed_terms()
        except KeyboardInterrupt:
            safe_exit()
        except Exception as e:
            print(f"Unexpected error while processing term '{term}': {e}")
            traceback.print_exc()

# Main execution flow
try:
    load_existing_data()
    search_and_capture_food()
except KeyboardInterrupt:
    safe_exit()
except Exception as main_e:
    print(f"Error in main automation flow: {main_e}")
    traceback.print_exc()
finally:
    save_dataset_to_csv()
    save_processed_terms()
    try:
        driver.quit()
        print("Driver session closed.")
    except Exception as quit_e:
        print(f"Error closing Appium driver: {quit_e}")