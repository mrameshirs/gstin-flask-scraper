# app.py
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
# from webdriver_manager.chrome import ChromeDriverManager # Not typically used in Docker/Render if chromedriver is installed manually
from geopy.geocoders import Nominatim, ArcGIS
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable, GeocoderServiceError
import time
import pandas as pd
import re
import os

app = Flask(__name__)


def driversetup_render():
    """Custom driver setup for Render (headless by default)."""
    options = ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")  # Essential for running in containers
    options.add_argument("--disable-gpu")  # Recommended for headless
    options.add_argument("--window-size=1920,1080")  # Can help with some page layouts
    options.add_argument("--disable-dev-shm-usage")  # Crucial for Docker/CI environments
    options.add_argument("lang=en")
    options.add_argument("start-maximized")  # Less relevant in headless but harmless
    options.add_argument("disable-infobars")
    options.add_argument("--disable-extensions")
    # options.add_argument("--incognito") # Headless is somewhat like incognito
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(
        "user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36")  # Generic Linux user agent

    try:
        # In a Docker environment (like on Render with a Dockerfile),
        # chromedriver should be installed and in the PATH.
        # If you've installed it to a specific location in your Dockerfile,
        # you might need to specify executable_path in ChromeService.
        # For now, we assume it's in PATH.
        print("Setting up ChromeDriver for Render environment...")
        # Check if running in Render by checking for a Render specific env var
        # Or just assume chromedriver is in PATH if not using webdriver-manager
        if os.environ.get('RENDER'):
            # Path where chromedriver is often installed in Docker containers
            # This path might need adjustment based on your Dockerfile
            chromedriver_path = os.environ.get('CHROMEDRIVER_PATH', '/usr/bin/chromedriver')
            print(f"Using chromedriver path for Render: {chromedriver_path}")
            service = ChromeService(executable_path=chromedriver_path)
        else:
            # Fallback for local testing if needed, though Docker should be primary for Render
            from webdriver_manager.chrome import ChromeDriverManager  # Keep for local testing convenience
            print("Setting up ChromeDriver using WebDriver Manager (likely local test)...")
            service = ChromeService(ChromeDriverManager().install())

        driver = webdriver.Chrome(service=service, options=options)
        print("ChromeDriver setup successful.")
    except Exception as e:
        print(f"Error setting up ChromeDriver: {e}")
        # In a production app, you might want to raise this or handle it more gracefully
        return None

    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
    return driver


def clean_address(address_str):
    if not isinstance(address_str, str):
        return ""
    cleaned_address = ' '.join(address_str.split())
    cleaned_address = re.sub(r'floor-\s*[\w\s]+,?', '', cleaned_address, flags=re.IGNORECASE)
    cleaned_address = cleaned_address.replace(' ,', ',').replace(',,', ',')
    cleaned_address = ', '.join(filter(None, (s.strip() for s in cleaned_address.split(','))))
    if "india" not in cleaned_address.lower() and (
            "mumbai" in cleaned_address.lower() or "maharashtra" in cleaned_address.lower()):
        cleaned_address += ", India"
    return cleaned_address


def geocode_address_with_fallbacks(address_str, attempt_count=0):
    if not address_str or not address_str.strip():
        print("Address string is empty, cannot geocode.")
        return None, None

    cleaned_address = clean_address(address_str)
    print(f"Attempting to geocode cleaned address: '{cleaned_address}' (Attempt {attempt_count + 1})")

    nominatim_user_agent = f"gstin_flask_app_render_{int(time.time())}"
    geocoders_to_try = [
        ("Nominatim", Nominatim(user_agent=nominatim_user_agent)),
        ("ArcGIS", ArcGIS(timeout=10))
    ]

    for name, geolocator in geocoders_to_try:
        try:
            print(f"Trying geocoder: {name}...")
            location = geolocator.geocode(cleaned_address, timeout=15)  # Increased timeout
            if location:
                print(f"Success with {name}: Lat: {location.latitude}, Lon: {location.longitude}")
                return location.latitude, location.longitude
            else:
                print(f"{name} could not geocode the address.")
        except GeocoderTimedOut:
            print(f"{name} geocoding timed out.")
        except GeocoderUnavailable:
            print(f"{name} geocoding service unavailable.")
        except GeocoderServiceError as e:
            print(f"{name} geocoding service error: {e}")
        except Exception as e:
            print(f"An unexpected error occurred with {name}: {e}")
        time.sleep(1)

    if attempt_count == 0:
        parts = [s.strip() for s in cleaned_address.split(',') if s.strip()]
        if len(parts) > 3:  # Try removing first one or two parts
            generic_address = ', '.join(parts[1:])  # Skip first part
            print(f"Trying a more generic address (v1): '{generic_address}'")
            lat, lon = geocode_address_with_fallbacks(generic_address, attempt_count + 1)
            if lat is not None:
                return lat, lon
            if len(parts) > 4:  # Try skipping first two parts
                generic_address_v2 = ', '.join(parts[2:])
                print(f"Trying a more generic address (v2): '{generic_address_v2}'")
                return geocode_address_with_fallbacks(generic_address_v2, attempt_count + 1)

    print("All geocoding attempts failed for the address.")
    return None, None


def get_gstin_details_scraper(gstin_number):
    """Scrapes GSTIN details."""
    url = "https://www.mastersindia.co/gst-number-search-and-gstin-verification/"
    print(f"Initiating scraper for GSTIN: {gstin_number}")
    driver = driversetup_render()

    if driver is None:
        print("WebDriver not initialized for scraper.")
        return {"error": "WebDriver initialization failed."}

    extracted_data = {"gstin_queried": gstin_number}  # Include the queried GSTIN
    wait_time = 30  # Increased for potentially slower container environments

    try:
        driver.get(url)
        print(f"Navigated to URL: {url}")

        gstin_input_css_selector = 'input[placeholder="XXXAAAYYYYZ01Z5"]'
        WebDriverWait(driver, wait_time).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, gstin_input_css_selector))
        )
        gstin_input = driver.find_element(By.CSS_SELECTOR, gstin_input_css_selector)
        gstin_input.clear()
        gstin_input.send_keys(gstin_number)
        print(f"Entered GSTIN: {gstin_number}")

        search_button_css_selector = 'button[aria-label="Search"]'
        WebDriverWait(driver, wait_time).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, search_button_css_selector))
        )
        search_button = driver.find_element(By.CSS_SELECTOR, search_button_css_selector)
        driver.execute_script("arguments[0].click();", search_button)
        print("Clicked Search button.")

        results_table_container_css_selector_for_wait = "div.eaKoeQ table"
        WebDriverWait(driver, wait_time).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, results_table_container_css_selector_for_wait))
        )
        print("Results table container found.")
        time.sleep(4)  # Allow JS rendering

        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')

        table_container_div = soup.select_one("div.eaKoeQ")
        table = None
        if table_container_div:
            table = table_container_div.find('table')
        if not table:
            table = soup.find('table')

        if not table:
            print("No data table found on the page after search.")
            if "captcha" in page_source.lower():
                return {"error": "CAPTCHA detected during scraping.", "gstin_queried": gstin_number}
            elif "No details found" in page_source or "Invalid GSTIN" in page_source:
                return {"error": f"No details found for GSTIN {gstin_number} or invalid GSTIN.",
                        "gstin_queried": gstin_number}
            return {"error": "Data table not found after search.", "gstin_queried": gstin_number}

        rows = table.find_all('tr')
        raw_data = {}
        for row in rows:
            header_element = row.find('th', class_=lambda x: x and 'eLVLDP' in x.split())
            value_element = row.find('td', class_=lambda x: x and 'jdgLDg' in x.split())
            if header_element and value_element:
                raw_data[header_element.get_text(strip=True)] = value_element.get_text(strip=True)
            elif len(row.find_all('td')) == 2:
                cells = row.find_all('td')
                if cells[0].get_text(strip=True):
                    raw_data[cells[0].get_text(strip=True)] = cells[1].get_text(strip=True)

        if not raw_data:
            print("Could not parse any data from the table rows.")
            return {"error": "Failed to parse data from table.", "gstin_queried": gstin_number}

        fields_to_extract = {
            "Principal Place of Business": "PrincipalPlace_Business",
            "Additional Place of Business": "AdditionalPlace_Business",
            "State Jurisdiction": "StateJurisdiction",
            "Centre Jurisdiction": "CentreJurisdiction",
            "Date of Registration": "DateRegistration",
            "Constitution of Business": "ConstitutionBusiness",
            "Taxpayer Type": "TaxpayerType",
            "GSTIN Status": "GSTINStatus"
        }
        for key_from_web, key_to_dict in fields_to_extract.items():
            extracted_data[key_to_dict] = raw_data.get(key_from_web, "Not Found")

        address_to_geocode = extracted_data.get("PrincipalPlace_Business")
        if address_to_geocode not in [None, "Not Found", ""]:
            lat, lon = geocode_address_with_fallbacks(address_to_geocode)
            extracted_data["PrincipalPlace_Latitude"] = lat
            extracted_data["PrincipalPlace_Longitude"] = lon
        else:
            extracted_data["PrincipalPlace_Latitude"] = None
            extracted_data["PrincipalPlace_Longitude"] = None
            if extracted_data.get("PrincipalPlace_Business"):
                print("Principal Place of Business not found or empty, skipping geocoding.")

        print(f"Successfully scraped data for {gstin_number}")
        return extracted_data

    except Exception as e:
        print(f"An error occurred during scraping process for {gstin_number}: {e}")
        # import traceback
        # traceback.print_exc()
        return {"error": f"Scraping process failed: {str(e)}", "gstin_queried": gstin_number}
    finally:
        if 'driver' in locals() and driver is not None:
            try:
                driver.quit()
                print("Browser closed.")
            except Exception as e:
                print(f"Error quitting driver: {e}")


@app.route('/')
def home():
    return jsonify({
        "message": "GSTIN Scraper API. Use /api/gstin/<gstin_number> to get details.",
        "example": "/api/gstin/27AAFCD5562R1Z5"
    })


@app.route('/api/gstin/<string:gstin_number>', methods=['GET'])
def api_get_gstin_details(gstin_number):
    print(f"Received API request for GSTIN: {gstin_number}")
    if not (len(gstin_number) == 15 and gstin_number.isalnum()):
        print(f"Invalid GSTIN format: {gstin_number}")
        return jsonify({"error": "Invalid GSTIN format. Must be 15 alphanumeric characters."}), 400

    details = get_gstin_details_scraper(gstin_number.upper())

    if "error" in details:
        print(f"Error processing GSTIN {gstin_number}: {details['error']}")
        # Determine appropriate status code based on error
        if "WebDriver initialization failed" in details["error"]:
            return jsonify(details), 503  # Service Unavailable
        if "CAPTCHA" in details["error"] or "Scraping process failed" in details["error"]:
            return jsonify(details), 502  # Bad Gateway (upstream issue)
        if "No details found" in details["error"] or "invalid GSTIN" in details["error"]:
            return jsonify(details), 404  # Not Found
        return jsonify(details), 500  # Internal Server Error for other parsing/generic errors

    print(f"Successfully returned details for GSTIN: {gstin_number}")
    return jsonify(details), 200


if __name__ == '__main__':
    # For local development, Render will use Gunicorn specified in Procfile or render.yaml
    port = int(os.environ.get("PORT", 5000))  # Render sets PORT env var
    app.run(host='0.0.0.0', port=port, debug=False)  # debug=False for production/Render