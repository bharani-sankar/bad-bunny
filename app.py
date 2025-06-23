from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from flask_cors import CORS
import json
import os
from datetime import datetime
import secrets

# Import the authentication module
from auth import AuthManager, setup_auth_routes, login_required

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes, allowing your React app to connect

# Set a secret key for sessions (use environment variable in production)
app.secret_key = secrets.token_hex(32)
API_PREFIX = os.getenv('API_PREFIX', '')
DATA_FILE = 'data.json'  # Define the JSON file name

# Initialize authentication manager
auth_manager = AuthManager(credentials_file='credentials.json', secret_key=app.secret_key)

# Setup authentication routes
setup_auth_routes(app, auth_manager, API_PREFIX)

# --- Data Loading and Saving Functions ---
def load_data():
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        # If file doesn't exist, return initial structure (or an empty one)
        # Make sure to create data.json with initial data for first run
        return {
            "suppliers": [],
            "vendors": [],
            "inwards": [],
            "outwards": [],
            "returns": [],
            "paneer_redirects": [],
            "_current_id": 100  # Default starting ID if file is truly empty/missing
        }
    except json.JSONDecodeError:
        print(f"Error decoding JSON from {DATA_FILE}. Returning empty structure.")
        return {
            "suppliers": [],
            "vendors": [],
            "inwards": [],
            "outwards": [],
            "returns": [],
            "paneer_redirects": [],
            "_current_id": 100
        }

def save_data(data_to_save):
    with open(DATA_FILE, 'w') as f:
        json.dump(data_to_save, f, indent=4)  # Use indent for pretty-printing

# Load data on app startup
data = load_data()
# Initialize current_id from loaded data or default
current_id = data.get('_current_id', 100)  # Use .get() for safety

def get_next_id():
    global current_id
    current_id += 1
    data['_current_id'] = current_id  # Update the ID in the data structure before saving
    return current_id

def calculate_sales_quantity(outward_item):
    return outward_item['quantity'] - outward_item['returnedQuantity']

# --- Main Routes ---
@app.route('/')
def home():
    """Main page - show login if not authenticated, redirect to dashboard if authenticated"""
    user = auth_manager.get_current_user_from_session()
    if user:
        return redirect(url_for('dashboard'))
    
    print("Serving index.html")
    return render_template("index.html", api_prefix=API_PREFIX)

# Dashboard route is already defined in auth.py setup_auth_routes function
@app.route('/api/suppliers', methods=['GET'])
def get_suppliers():
    return jsonify([
        {"id": 1, "name": "Supplier A"},
        {"id": 2, "name": "Supplier B"}
    ])


# --- Protected API Endpoints (require authentication) ---
@app.route('/<resource_name>', methods=['GET'])
@login_required(auth_manager)
def get_all_resources(user, resource_name):
    """Get all resources - requires authentication"""
    resource_key = resource_name.replace('-', '_')  # <-- THIS IS THE KEY PART
    if resource_key in data:
        return jsonify(data[resource_key])
    return jsonify({"error": "Resource not found"}), 404

# Suppliers
@app.route('/suppliers', methods=['POST'])
@login_required(auth_manager)
def add_supplier(user):
    new_supplier = request.json
    new_supplier['id'] = get_next_id()
    new_supplier['created_by'] = user['id']  # Track who created it
    new_supplier['created_at'] = datetime.now().isoformat()
    data['suppliers'].append(new_supplier)
    save_data(data)  # Save after adding
    return jsonify(new_supplier), 201

@app.route('/suppliers/<int:supplier_id>', methods=['PUT'])
@login_required(auth_manager)
def update_supplier(user, supplier_id):
    updated_data = request.json
    found = False
    for i, s in enumerate(data['suppliers']):
        if s['id'] == supplier_id:
            data['suppliers'][i].update(updated_data)
            data['suppliers'][i]['id'] = supplier_id  # Ensure ID doesn't change
            data['suppliers'][i]['updated_by'] = user['id']  # Track who updated it
            data['suppliers'][i]['updated_at'] = datetime.now().isoformat()
            updated_resource = data['suppliers'][i]
            found = True
            break
    if found:
        save_data(data)  # Save after updating
        return jsonify(updated_resource)
    return jsonify({"error": "Supplier not found"}), 404

@app.route('/suppliers/<int:supplier_id>', methods=['DELETE'])
@login_required(auth_manager)
def delete_supplier(user, supplier_id):
    initial_len = len(data['suppliers'])
    data['suppliers'] = [s for s in data['suppliers'] if s['id'] != supplier_id]
    if len(data['suppliers']) < initial_len:
        save_data(data)  # Save after deleting
        return jsonify({"message": "Supplier deleted"}), 200
    return jsonify({"error": "Supplier not found"}), 404

# Vendors
@app.route('/vendors', methods=['POST'])
@login_required(auth_manager)
def add_vendor(user):
    new_vendor = request.json
    new_vendor['id'] = get_next_id()
    new_vendor['created_by'] = user['id']
    new_vendor['created_at'] = datetime.now().isoformat()
    data['vendors'].append(new_vendor)
    save_data(data)  # Save after adding
    return jsonify(new_vendor), 201

@app.route('/vendors/<int:vendor_id>', methods=['PUT'])
@login_required(auth_manager)
def update_vendor(user, vendor_id):
    updated_data = request.json
    found = False
    for i, v in enumerate(data['vendors']):
        if v['id'] == vendor_id:
            data['vendors'][i].update(updated_data)
            data['vendors'][i]['id'] = vendor_id
            data['vendors'][i]['updated_by'] = user['id']
            data['vendors'][i]['updated_at'] = datetime.now().isoformat()
            updated_resource = data['vendors'][i]
            found = True
            break
    if found:
        save_data(data)  # Save after updating
        return jsonify(updated_resource)
    return jsonify({"error": "Vendor not found"}), 404

@app.route('/vendors/<int:vendor_id>', methods=['DELETE'])
@login_required(auth_manager)
def delete_vendor(user, vendor_id):
    initial_len = len(data['vendors'])
    data['vendors'] = [v for v in data['vendors'] if v['id'] != vendor_id]
    if len(data['vendors']) < initial_len:
        save_data(data)  # Save after deleting
        return jsonify({"message": "Vendor deleted"}), 200
    return jsonify({"error": "Vendor not found"}), 404

# Inwards
@app.route('/inwards', methods=['POST'])
@login_required(auth_manager)
def add_inward(user):
    new_inward = request.json
    new_inward['id'] = get_next_id()
    new_inward['quantity'] = float(new_inward['quantity'])
    new_inward['fat'] = float(new_inward['fat'])
    new_inward['snf'] = float(new_inward['snf'])
    new_inward['created_by'] = user['id']
    new_inward['created_at'] = datetime.now().isoformat()
    data['inwards'].append(new_inward)
    save_data(data)  # Save after adding
    return jsonify(new_inward), 201

# Outwards
@app.route('/outwards', methods=['POST'])
@login_required(auth_manager)
def add_outward(user):
    new_outward = request.json
    new_outward['id'] = get_next_id()
    new_outward['returnedQuantity'] = 0.0
    new_outward['salesQuantity'] = None
    new_outward['status'] = "Pending"
    new_outward['quantity'] = float(new_outward['quantity'])
    new_outward['created_by'] = user['id']
    new_outward['created_at'] = datetime.now().isoformat()
    data['outwards'].append(new_outward)
    save_data(data)  # Save after adding
    return jsonify(new_outward), 201

# Returns - This endpoint should also update the corresponding outward
@app.route('/returns', methods=['POST'])
@login_required(auth_manager)
def add_return(user):
    return_data = request.json
    outward_id_to_update = return_data['outwardEntryId']
    return_quantity = float(return_data['quantity'])

    updated_outward_item = None
    for i, outward_item in enumerate(data['outwards']):
        if outward_item['id'] == outward_id_to_update:
            outward_item['returnedQuantity'] += return_quantity
            
            if outward_item['returnedQuantity'] >= outward_item['quantity'] or return_quantity == 0:
                outward_item['status'] = "Completed"
                outward_item['salesQuantity'] = calculate_sales_quantity(outward_item)
            elif outward_item['returnedQuantity'] > 0:
                outward_item['status'] = "Partial Return"
                outward_item['salesQuantity'] = None

            updated_outward_item = outward_item  # Reference to the modified item in data list
            break
    
    if updated_outward_item:
        return_data['id'] = get_next_id()  # Assign ID to the return record
        return_data['created_by'] = user['id']
        return_data['created_at'] = datetime.now().isoformat()
        data['returns'].append(return_data)
        save_data(data)  # Save after both return and outward update
        return jsonify(updated_outward_item), 200
    return jsonify({"error": "Outward entry not found for return"}), 404

# Mark Outward as Complete Endpoint
@app.route('/outwards/<int:outward_id>/complete', methods=['PUT'])
@login_required(auth_manager)
def mark_outward_complete(user, outward_id):
    updated_outward_item = None
    for i, outward_item in enumerate(data['outwards']):
        if outward_item['id'] == outward_id:
            outward_item['status'] = "Completed"
            outward_item['salesQuantity'] = calculate_sales_quantity(outward_item)
            outward_item['completed_by'] = user['id']
            outward_item['completed_at'] = datetime.now().isoformat()
            updated_outward_item = outward_item  # Reference to the modified item in data list
            break
    
    if updated_outward_item:
        save_data(data)  # Save after updating
        return jsonify(updated_outward_item), 200
    return jsonify({"error": "Outward entry not found"}), 404

# Paneer Redirects
@app.route('/paneer-redirects', methods=['POST'])
@login_required(auth_manager)
def add_paneer_redirect(user):
    new_redirect = request.json
    new_redirect['id'] = get_next_id()
    new_redirect['quantity'] = float(new_redirect['quantity'])
    new_redirect['created_by'] = user['id']
    new_redirect['created_at'] = datetime.now().isoformat()
    data['paneer_redirects'].append(new_redirect)
    save_data(data)  # Save after adding
    return jsonify(new_redirect), 201

# Add a route to check authentication status
@app.route('/api/check-auth', methods=['GET'])
def check_auth():
    """Check if user is authenticated"""
    user = auth_manager.get_current_user_from_session()
    if user:
        return jsonify({
            'authenticated': True,
            'user': {
                'id': user['id'],
                'name': user['name'],
                'email': user['email']
            }
        }), 200
    else:
        return jsonify({'authenticated': False}), 200

if __name__ == '__main__':
    app.run(debug=True, port=5000)