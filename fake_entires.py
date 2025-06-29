import requests
from faker import Faker
import random
from datetime import datetime, timedelta

# --- Configuration ---
# The base URL of your running Flask application
BASE_URL = 'http://127.0.0.1:5000'

# Your admin login credentials
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'admin123'

# Number of fake records to create for each section
NUM_FARMERS = 15
NUM_BUYERS = 10
NUM_INWARD_TRANSACTIONS = 50
NUM_OUTWARD_TRANSACTIONS = 40

# --- Script ---

# Initialize the Faker library for generating fake data
fake = Faker('en_IN') # Using Indian locale for more relevant names/places

def login(session):
    """Logs into the application to establish a valid session."""
    login_url = f"{BASE_URL}/login"
    login_payload = {
        'username': ADMIN_USERNAME,
        'password': ADMIN_PASSWORD
    }
    try:
        response = session.post(login_url, data=login_payload, allow_redirects=True)
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
        if "dashboard" in response.url:
            print("✅ Login successful.")
            return True
        else:
            print("❌ Login failed. Check credentials or if the app is running.")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Could not connect to the server at {login_url}. Is the app running?")
        print(f"   Error: {e}")
        return False

def create_fake_farmers(session, count):
    """Creates a specified number of fake farmers."""
    print(f"\n--- Creating {count} fake farmers... ---")
    url = f"{BASE_URL}/add_farmer"
    for i in range(count):
        farmer_data = {
            'name': fake.name(),
            'mobile': fake.unique.phone_number(),
            'place': fake.city(),
            'acres_owned': round(random.uniform(2.5, 50.0), 2),
            'acres_cultivated': round(random.uniform(1.0, 25.0), 2)
        }
        response = session.post(url, data=farmer_data)
        if response.status_code == 200 or response.history: # 200 or redirect
            print(f"  > Created Farmer #{i+1}: {farmer_data['name']}")
        else:
            print(f"  > ❌ Failed to create Farmer #{i+1}. Status: {response.status_code}")

def create_fake_buyers(session, count):
    """Creates a specified number of fake buyers."""
    print(f"\n--- Creating {count} fake buyers... ---")
    url = f"{BASE_URL}/add_buyer"
    business_types = ['Factory', 'Trader', 'Exporter', 'Local Mill', 'Retailer']
    for i in range(count):
        buyer_data = {
            'name': fake.company(),
            'mobile': fake.unique.phone_number(),
            'place': fake.city(),
            'business_type': random.choice(business_types)
        }
        response = session.post(url, data=buyer_data)
        if response.status_code == 200 or response.history:
            print(f"  > Created Buyer #{i+1}: {buyer_data['name']}")
        else:
            print(f"  > ❌ Failed to create Buyer #{i+1}. Status: {response.status_code}")

def create_fake_inward_transactions(session, count, num_farmers):
    """Creates fake inward transactions, linking them to existing farmers."""
    print(f"\n--- Creating {count} fake inward transactions... ---")
    url = f"{BASE_URL}/add_inward"
    for i in range(count):
        transaction_date = (datetime.now() - timedelta(days=random.randint(0, 365))).strftime('%Y-%m-%d')
        weight = round(random.uniform(0.5, 10.0), 2)
        price = round(random.uniform(18000, 25000), 2)
        
        inward_data = {
            'farmer_id': random.randint(1, num_farmers),
            'weight_tons': weight,
            'market_price': price,
            'transaction_date': transaction_date,
            'notes': fake.sentence(nb_words=6)
        }
        response = session.post(url, data=inward_data)
        if response.status_code == 200 or response.history:
            print(f"  > Created Inward Transaction #{i+1}")
        else:
            print(f"  > ❌ Failed to create Inward Transaction #{i+1}. Status: {response.status_code}")

def create_fake_outward_transactions(session, count, num_buyers):
    """Creates fake outward transactions, linking them to existing buyers."""
    print(f"\n--- Creating {count} fake outward transactions... ---")
    url = f"{BASE_URL}/add_outward"
    for i in range(count):
        transaction_date = (datetime.now() - timedelta(days=random.randint(0, 180))).strftime('%Y-%m-%d')
        weight = round(random.uniform(5.0, 50.0), 2)
        price = round(random.uniform(23000, 30000), 2)
        
        outward_data = {
            'buyer_id': random.randint(1, num_buyers),
            'weight_tons': weight,
            'selling_price': price,
            'transaction_date': transaction_date,
            'notes': fake.sentence(nb_words=4)
        }
        response = session.post(url, data=outward_data)
        if response.status_code == 200 or response.history:
            print(f"  > Created Outward Transaction #{i+1}")
        else:
            print(f"  > ❌ Failed to create Outward Transaction #{i+1}. Status: {response.status_code}")


if __name__ == '__main__':
    # Use a session object to persist cookies (and thus the login session)
    with requests.Session() as s:
        if login(s):
            # Create records
            create_fake_farmers(s, NUM_FARMERS)
            create_fake_buyers(s, NUM_BUYERS)
            create_fake_inward_transactions(s, NUM_INWARD_TRANSACTIONS, NUM_FARMERS)
            create_fake_outward_transactions(s, NUM_OUTWARD_TRANSACTIONS, NUM_BUYERS)
            print("\n✅ Database seeding complete!")
