from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
import os
from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-this')

# Database configuration
DATABASE = 'corn_trading.db'

def init_db():
    """Initialize the database with required tables"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Admin user table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Farmers table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS farmers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            mobile TEXT UNIQUE NOT NULL,
            place TEXT NOT NULL,
            acres_owned REAL,
            acres_cultivated REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Buyers table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS buyers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            mobile TEXT UNIQUE NOT NULL,
            place TEXT NOT NULL,
            business_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Inward transactions (from farmers)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inward_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            farmer_id INTEGER NOT NULL,
            weight_tons REAL NOT NULL,
            market_price REAL NOT NULL,
            confirmed_amount REAL NOT NULL,
            transaction_date DATE NOT NULL,
            payment_status TEXT DEFAULT 'Pending',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (farmer_id) REFERENCES farmers (id)
        )
    ''')
    
    # Outward transactions (to buyers)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS outward_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            buyer_id INTEGER NOT NULL,
            weight_tons REAL NOT NULL,
            selling_price REAL NOT NULL,
            total_amount REAL NOT NULL,
            transaction_date DATE NOT NULL,
            payment_status TEXT DEFAULT 'Pending',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (buyer_id) REFERENCES buyers (id)
        )
    ''')
    
    # Create default admin user if not exists
    cursor.execute('SELECT COUNT(*) FROM admin_users')
    if cursor.fetchone()[0] == 0:
        password_hash = generate_password_hash('admin123')
        cursor.execute('INSERT INTO admin_users (username, password_hash) VALUES (?, ?)', 
                       ('admin', password_hash))
    
    conn.commit()
    conn.close()

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM admin_users WHERE username = ?', (username,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db_connection()
    
    # Get dashboard statistics
    total_farmers = conn.execute('SELECT COUNT(*) as count FROM farmers').fetchone()['count']
    total_buyers = conn.execute('SELECT COUNT(*) as count FROM buyers').fetchone()['count']
    
    # Recent inward transactions
    recent_inward = conn.execute('''
        SELECT i.*, f.name as farmer_name 
        FROM inward_transactions i 
        JOIN farmers f ON i.farmer_id = f.id 
        ORDER BY i.created_at DESC 
        LIMIT 5
    ''').fetchall()
    
    # Recent outward transactions
    recent_outward = conn.execute('''
        SELECT o.*, b.name as buyer_name 
        FROM outward_transactions o 
        JOIN buyers b ON o.buyer_id = b.id 
        ORDER BY o.created_at DESC 
        LIMIT 5
    ''').fetchall()
    
    # Pending payments
    pending_inward = conn.execute('''
        SELECT SUM(confirmed_amount) as total 
        FROM inward_transactions 
        WHERE payment_status = "Pending"
    ''').fetchone()['total'] or 0
    
    pending_outward = conn.execute('''
        SELECT SUM(total_amount) as total 
        FROM outward_transactions 
        WHERE payment_status = "Pending"
    ''').fetchone()['total'] or 0
    
    conn.close()
    
    return render_template('dashboard.html', 
                           total_farmers=total_farmers,
                           total_buyers=total_buyers,
                           recent_inward=recent_inward,
                           recent_outward=recent_outward,
                           pending_inward=pending_inward,
                           pending_outward=pending_outward)

@app.route('/farmers')
@login_required
def farmers():
    conn = get_db_connection()
    farmers = conn.execute('SELECT * FROM farmers ORDER BY created_at DESC').fetchall()
    conn.close()
    return render_template('farmers.html', farmers=farmers)

@app.route('/add_farmer', methods=['GET', 'POST'])
@login_required
def add_farmer():
    if request.method == 'POST':
        name = request.form['name']
        mobile = request.form['mobile']
        place = request.form['place']
        acres_owned = request.form.get('acres_owned', '')
        acres_cultivated = request.form.get('acres_cultivated', '')
        
        conn = get_db_connection()
        try:
            conn.execute('''
                INSERT INTO farmers (name, mobile, place, acres_owned, acres_cultivated)
                VALUES (?, ?, ?, ?, ?)
            ''', (name, mobile, place, 
                  float(acres_owned) if acres_owned else None,
                  float(acres_cultivated) if acres_cultivated else None))
            conn.commit()
            flash('Farmer added successfully!')
            return redirect(url_for('farmers'))
        except sqlite3.IntegrityError:
            flash('Mobile number already exists!')
        except Exception as e:
            flash(f'Error adding farmer: {str(e)}')
        finally:
            conn.close()
    
    return render_template('add_farmer.html')

@app.route('/edit_farmer/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_farmer(id):
    conn = get_db_connection()
    farmer = conn.execute('SELECT * FROM farmers WHERE id = ?', (id,)).fetchone()

    if request.method == 'POST':
        name = request.form['name']
        mobile = request.form['mobile']
        place = request.form['place']
        acres_owned = request.form.get('acres_owned', '')
        acres_cultivated = request.form.get('acres_cultivated', '')

        try:
            conn.execute('''
                UPDATE farmers 
                SET name = ?, mobile = ?, place = ?, acres_owned = ?, acres_cultivated = ?
                WHERE id = ?
            ''', (name, mobile, place, 
                  float(acres_owned) if acres_owned else None,
                  float(acres_cultivated) if acres_cultivated else None,
                  id))
            conn.commit()
            flash('Farmer details updated successfully!')
            return redirect(url_for('farmers'))
        except sqlite3.IntegrityError:
            flash('Mobile number already exists for another farmer!')
        except Exception as e:
            flash(f'Error updating farmer: {str(e)}')
        finally:
            conn.close()
    
    conn.close()
    if farmer is None:
        flash('Farmer not found!')
        return redirect(url_for('farmers'))
        
    return render_template('edit_farmer.html', farmer=farmer)

@app.route('/delete_farmer/<int:id>', methods=['POST'])
@login_required
def delete_farmer(id):
    conn = get_db_connection()
    try:
        # Check if the farmer has associated transactions
        transactions = conn.execute('SELECT COUNT(*) FROM inward_transactions WHERE farmer_id = ?', (id,)).fetchone()[0]
        if transactions > 0:
            flash('Cannot delete farmer. They have existing inward transactions.', 'error')
            return redirect(url_for('farmers'))

        conn.execute('DELETE FROM farmers WHERE id = ?', (id,))
        conn.commit()
        flash('Farmer deleted successfully!')
    except Exception as e:
        flash(f'Error deleting farmer: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('farmers'))

@app.route('/delete_farmers_batch', methods=['POST'])
@login_required
def delete_farmers_batch():
    data = request.get_json()
    ids_to_delete = data.get('ids', [])

    if not ids_to_delete:
        return jsonify({'success': False, 'message': 'No farmers selected.'}), 400

    conn = get_db_connection()
    try:
        # Data Integrity Check: Ensure none of the farmers have transactions
        placeholders = ','.join(['?'] * len(ids_to_delete))
        query = f'SELECT COUNT(*) FROM inward_transactions WHERE farmer_id IN ({placeholders})'
        transaction_count = conn.execute(query, ids_to_delete).fetchone()[0]

        if transaction_count > 0:
            flash(f'Deletion failed. One or more selected farmers have existing transactions.', 'error')
            return jsonify({'success': False, 'message': 'Cannot delete farmers with transactions.'}), 409

        # Proceed with deletion
        conn.execute(f'DELETE FROM farmers WHERE id IN ({placeholders})', ids_to_delete)
        conn.commit()
        flash(f'Successfully deleted {len(ids_to_delete)} farmer(s).')
        return jsonify({'success': True})
    except Exception as e:
        flash(f'An error occurred during batch deletion: {str(e)}', 'error')
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()

@app.route('/buyers')
@login_required
def buyers():
    conn = get_db_connection()
    buyers = conn.execute('SELECT * FROM buyers ORDER BY created_at DESC').fetchall()
    conn.close()
    return render_template('buyers.html', buyers=buyers)

@app.route('/add_buyer', methods=['GET', 'POST'])
@login_required
def add_buyer():
    if request.method == 'POST':
        name = request.form['name']
        mobile = request.form['mobile']
        place = request.form['place']
        business_type = request.form.get('business_type', '')
        
        conn = get_db_connection()
        try:
            conn.execute('''
                INSERT INTO buyers (name, mobile, place, business_type)
                VALUES (?, ?, ?, ?)
            ''', (name, mobile, place, business_type))
            conn.commit()
            flash('Buyer added successfully!')
            return redirect(url_for('buyers'))
        except sqlite3.IntegrityError:
            flash('Mobile number already exists!')
        except Exception as e:
            flash(f'Error adding buyer: {str(e)}')
        finally:
            conn.close()
    
    return render_template('add_buyer.html')

@app.route('/edit_buyer/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_buyer(id):
    conn = get_db_connection()
    buyer = conn.execute('SELECT * FROM buyers WHERE id = ?', (id,)).fetchone()

    if request.method == 'POST':
        name = request.form['name']
        mobile = request.form['mobile']
        place = request.form['place']
        business_type = request.form.get('business_type', '')

        try:
            conn.execute('''
                UPDATE buyers 
                SET name = ?, mobile = ?, place = ?, business_type = ?
                WHERE id = ?
            ''', (name, mobile, place, business_type, id))
            conn.commit()
            flash('Buyer details updated successfully!')
            return redirect(url_for('buyers'))
        except sqlite3.IntegrityError:
            flash('Mobile number already exists for another buyer!')
        except Exception as e:
            flash(f'Error updating buyer: {str(e)}')
        finally:
            conn.close()
    
    conn.close()
    if buyer is None:
        flash('Buyer not found!')
        return redirect(url_for('buyers'))
        
    return render_template('edit_buyer.html', buyer=buyer)

@app.route('/delete_buyer/<int:id>', methods=['POST'])
@login_required
def delete_buyer(id):
    conn = get_db_connection()
    try:
        # Check if the buyer has associated transactions
        transactions = conn.execute('SELECT COUNT(*) FROM outward_transactions WHERE buyer_id = ?', (id,)).fetchone()[0]
        if transactions > 0:
            flash('Cannot delete buyer. They have existing outward transactions.', 'error')
            return redirect(url_for('buyers'))

        conn.execute('DELETE FROM buyers WHERE id = ?', (id,))
        conn.commit()
        flash('Buyer deleted successfully!')
    except Exception as e:
        flash(f'Error deleting buyer: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('buyers'))

@app.route('/delete_buyers_batch', methods=['POST'])
@login_required
def delete_buyers_batch():
    data = request.get_json()
    ids_to_delete = data.get('ids', [])

    if not ids_to_delete:
        return jsonify({'success': False, 'message': 'No buyers selected.'}), 400

    conn = get_db_connection()
    try:
        # Data Integrity Check: Ensure none of the buyers have transactions
        placeholders = ','.join(['?'] * len(ids_to_delete))
        query = f'SELECT COUNT(*) FROM outward_transactions WHERE buyer_id IN ({placeholders})'
        transaction_count = conn.execute(query, ids_to_delete).fetchone()[0]

        if transaction_count > 0:
            flash(f'Deletion failed. One or more selected buyers have existing transactions.', 'error')
            return jsonify({'success': False, 'message': 'Cannot delete buyers with transactions.'}), 409

        # Proceed with deletion
        conn.execute(f'DELETE FROM buyers WHERE id IN ({placeholders})', ids_to_delete)
        conn.commit()
        flash(f'Successfully deleted {len(ids_to_delete)} buyer(s).')
        return jsonify({'success': True})
    except Exception as e:
        flash(f'An error occurred during batch deletion: {str(e)}', 'error')
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()

@app.route('/inward')
@login_required
def inward():
    conn = get_db_connection()
    transactions = conn.execute('''
        SELECT i.*, f.name as farmer_name, f.mobile as farmer_mobile
        FROM inward_transactions i 
        JOIN farmers f ON i.farmer_id = f.id 
        ORDER BY i.transaction_date DESC
    ''').fetchall()
    conn.close()
    return render_template('inward.html', transactions=transactions)

@app.route('/add_inward', methods=['GET', 'POST'])
@login_required
def add_inward():
    conn = get_db_connection()
    
    if request.method == 'POST':
        farmer_id = request.form['farmer_id']
        weight_tons = float(request.form['weight_tons'])
        market_price = float(request.form['market_price'])
        transaction_date = request.form['transaction_date']
        notes = request.form.get('notes', '')
        
        confirmed_amount = weight_tons * market_price
        
        try:
            conn.execute('''
                INSERT INTO inward_transactions 
                (farmer_id, weight_tons, market_price, confirmed_amount, transaction_date, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (farmer_id, weight_tons, market_price, confirmed_amount, transaction_date, notes))
            conn.commit()
            flash('Inward transaction added successfully!')
            return redirect(url_for('inward'))
        except Exception as e:
            flash(f'Error adding transaction: {str(e)}')
    
    farmers = conn.execute('SELECT * FROM farmers ORDER BY name').fetchall()
    conn.close()
    return render_template('add_inward.html', farmers=farmers)

@app.route('/edit_inward/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_inward(id):
    conn = get_db_connection()
    transaction = conn.execute('SELECT * FROM inward_transactions WHERE id = ?', (id,)).fetchone()

    if request.method == 'POST':
        farmer_id = request.form['farmer_id']
        weight_tons = float(request.form['weight_tons'])
        market_price = float(request.form['market_price'])
        transaction_date = request.form['transaction_date']
        notes = request.form.get('notes', '')
        
        confirmed_amount = weight_tons * market_price
        
        try:
            conn.execute('''
                UPDATE inward_transactions
                SET farmer_id = ?, weight_tons = ?, market_price = ?, confirmed_amount = ?, transaction_date = ?, notes = ?
                WHERE id = ?
            ''', (farmer_id, weight_tons, market_price, confirmed_amount, transaction_date, notes, id))
            conn.commit()
            flash('Inward transaction updated successfully!')
            return redirect(url_for('inward'))
        except Exception as e:
            flash(f'Error updating transaction: {str(e)}')
        finally:
            conn.close()
            
    if transaction is None:
        flash('Transaction not found!')
        conn.close()
        return redirect(url_for('inward'))
        
    farmers = conn.execute('SELECT * FROM farmers ORDER BY name').fetchall()
    conn.close()
    return render_template('edit_inward.html', transaction=transaction, farmers=farmers)

@app.route('/delete_inward/<int:id>', methods=['POST'])
@login_required
def delete_inward(id):
    conn = get_db_connection()
    try:
        conn.execute('DELETE FROM inward_transactions WHERE id = ?', (id,))
        conn.commit()
        flash('Inward transaction deleted successfully!')
    except Exception as e:
        flash(f'Error deleting transaction: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('inward'))

@app.route('/delete_inward_batch', methods=['POST'])
@login_required
def delete_inward_batch():
    data = request.get_json()
    ids_to_delete = data.get('ids', [])

    if not ids_to_delete:
        return jsonify({'success': False, 'message': 'No transactions selected.'}), 400

    conn = get_db_connection()
    try:
        placeholders = ','.join(['?'] * len(ids_to_delete))
        conn.execute(f'DELETE FROM inward_transactions WHERE id IN ({placeholders})', ids_to_delete)
        conn.commit()
        flash(f'Successfully deleted {len(ids_to_delete)} inward transaction(s).')
        return jsonify({'success': True})
    except Exception as e:
        flash(f'An error occurred during batch deletion: {str(e)}', 'error')
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()

@app.route('/outward')
@login_required
def outward():
    conn = get_db_connection()
    transactions = conn.execute('''
        SELECT o.*, b.name as buyer_name, b.mobile as buyer_mobile
        FROM outward_transactions o 
        JOIN buyers b ON o.buyer_id = b.id 
        ORDER BY o.transaction_date DESC
    ''').fetchall()
    conn.close()
    return render_template('outward.html', transactions=transactions)


@app.route('/add_outward', methods=['GET', 'POST'])
@login_required
def add_outward():
    conn = get_db_connection()

    if request.method == 'POST':
        try:
            # --- Date and Initial Entry Validation ---
            first_inward = conn.execute('SELECT MIN(transaction_date) as first_date FROM inward_transactions').fetchone()
            first_inward_date_str = first_inward['first_date'] if first_inward else None

            if not first_inward_date_str:
                flash('Cannot add outward transaction. The first transaction must be an inward entry.', 'error')
                return redirect(url_for('add_outward'))

            transaction_date_str = request.form['transaction_date']
            transaction_date_obj = datetime.strptime(transaction_date_str, '%Y-%m-%d').date()
            first_inward_date_obj = datetime.strptime(first_inward_date_str, '%Y-%m-%d').date()

            if transaction_date_obj < first_inward_date_obj:
                flash(f'Outward transaction date cannot be before the first inward transaction date ({first_inward_date_str}).', 'error')
                return redirect(url_for('add_outward'))

            # --- Stock Quantity Validation ---
            weight_tons = float(request.form['weight_tons'])
            total_inward = conn.execute('SELECT COALESCE(SUM(weight_tons), 0) as total FROM inward_transactions').fetchone()['total']
            total_outward = conn.execute('SELECT COALESCE(SUM(weight_tons), 0) as total FROM outward_transactions').fetchone()['total']
            available_stock = total_inward - total_outward

            if weight_tons > available_stock:
                flash(f'Cannot add outward transaction. Insufficient stock. Available: {available_stock:.2f} tons.', 'error')
                return redirect(url_for('add_outward'))

            # --- Proceed with insertion ---
            buyer_id = request.form['buyer_id']
            selling_price = float(request.form['selling_price'])
            notes = request.form.get('notes', '')
            total_amount = weight_tons * selling_price

            conn.execute('''
                INSERT INTO outward_transactions 
                (buyer_id, weight_tons, selling_price, total_amount, transaction_date, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (buyer_id, weight_tons, selling_price, total_amount, transaction_date_str, notes))
            conn.commit()
            flash('Outward transaction added successfully!')
            return redirect(url_for('outward'))

        except Exception as e:
            flash(f'An error occurred: {str(e)}', 'error')
            return redirect(url_for('add_outward'))
        finally:
            conn.close()

    # --- MODIFIED FOR GET REQUEST ---
    # This part runs when the page is loaded initially
    try:
        buyers = conn.execute('SELECT * FROM buyers ORDER BY name').fetchall()

        # Calculate available stock and pass it to the template
        total_inward = conn.execute('SELECT COALESCE(SUM(weight_tons), 0) as total FROM inward_transactions').fetchone()['total']
        total_outward = conn.execute('SELECT COALESCE(SUM(weight_tons), 0) as total FROM outward_transactions').fetchone()['total']
        available_stock = total_inward - total_outward

        return render_template('add_outward.html', buyers=buyers, available_stock=available_stock)
    finally:
        if conn:
            conn.close()

@app.route('/edit_outward/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_outward(id):
    conn = get_db_connection()

    if request.method == 'POST':
        try:
            # --- Date Validation ---
            first_inward = conn.execute('SELECT MIN(transaction_date) as first_date FROM inward_transactions').fetchone()
            first_inward_date_str = first_inward['first_date'] if first_inward else None

            if not first_inward_date_str:
                flash('Data integrity error: Cannot find any inward transactions to validate against.', 'error')
                return redirect(url_for('outward'))

            transaction_date_str = request.form['transaction_date']
            transaction_date_obj = datetime.strptime(transaction_date_str, '%Y-%m-%d').date()
            first_inward_date_obj = datetime.strptime(first_inward_date_str, '%Y-%m-%d').date()

            if transaction_date_obj < first_inward_date_obj:
                flash(f'Outward transaction date cannot be before the first inward transaction date ({first_inward_date_str}).', 'error')
                return redirect(url_for('edit_outward', id=id))

            # --- Stock Quantity Validation ---
            weight_tons = float(request.form['weight_tons'])
            total_inward = conn.execute('SELECT COALESCE(SUM(weight_tons), 0) FROM inward_transactions').fetchone()[0]
            total_outward = conn.execute('SELECT COALESCE(SUM(weight_tons), 0) FROM outward_transactions WHERE id != ?', (id,)).fetchone()[0]
            available_stock = total_inward - total_outward

            if weight_tons > available_stock:
                flash(f'Cannot update transaction. Insufficient stock. Available for this transaction: {available_stock:.2f} tons.', 'error')
                return redirect(url_for('edit_outward', id=id))

            # --- Proceed with update ---
            buyer_id = request.form['buyer_id']
            selling_price = float(request.form['selling_price'])
            notes = request.form.get('notes', '')
            total_amount = weight_tons * selling_price

            conn.execute('''
                UPDATE outward_transactions
                SET buyer_id = ?, weight_tons = ?, selling_price = ?, total_amount = ?, transaction_date = ?, notes = ?
                WHERE id = ?
            ''', (buyer_id, weight_tons, selling_price, total_amount, transaction_date_str, notes, id))
            conn.commit()
            flash('Outward transaction updated successfully!')
            return redirect(url_for('outward'))

        except Exception as e:
            flash(f'An error occurred: {str(e)}', 'error')
            return redirect(url_for('edit_outward', id=id))
        finally:
            conn.close()

    # GET request
    transaction = conn.execute('SELECT * FROM outward_transactions WHERE id = ?', (id,)).fetchone()
    if transaction is None:
        flash('Transaction not found!')
        conn.close()
        return redirect(url_for('outward'))

    buyers = conn.execute('SELECT * FROM buyers ORDER BY name').fetchall()
    conn.close()
    return render_template('edit_outward.html', transaction=transaction, buyers=buyers)

@app.route('/delete_outward/<int:id>', methods=['POST'])
@login_required
def delete_outward(id):
    conn = get_db_connection()
    try:
        conn.execute('DELETE FROM outward_transactions WHERE id = ?', (id,))
        conn.commit()
        flash('Outward transaction deleted successfully!')
    except Exception as e:
        flash(f'Error deleting transaction: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('outward'))

@app.route('/delete_outward_batch', methods=['POST'])
@login_required
def delete_outward_batch():
    data = request.get_json()
    ids_to_delete = data.get('ids', [])

    if not ids_to_delete:
        return jsonify({'success': False, 'message': 'No transactions selected.'}), 400

    conn = get_db_connection()
    try:
        placeholders = ','.join(['?'] * len(ids_to_delete))
        conn.execute(f'DELETE FROM outward_transactions WHERE id IN ({placeholders})', ids_to_delete)
        conn.commit()
        flash(f'Successfully deleted {len(ids_to_delete)} outward transaction(s).')
        return jsonify({'success': True})
    except Exception as e:
        flash(f'An error occurred during batch deletion: {str(e)}', 'error')
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()

@app.route('/update_payment_status', methods=['POST'])
@login_required
def update_payment_status():
    transaction_id = request.form['transaction_id']
    transaction_type = request.form['transaction_type']
    status = request.form['status']
    
    conn = get_db_connection()
    
    if transaction_type == 'inward':
        conn.execute('UPDATE inward_transactions SET payment_status = ? WHERE id = ?', 
                     (status, transaction_id))
    else:
        conn.execute('UPDATE outward_transactions SET payment_status = ? WHERE id = ?', 
                     (status, transaction_id))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/api/dashboard_stats')
@login_required
def api_dashboard_stats():
    """API endpoint to get dashboard statistics"""
    conn = get_db_connection()
    
    try:
        # Total counts
        total_farmers = conn.execute('SELECT COUNT(*) as count FROM farmers').fetchone()['count']
        total_buyers = conn.execute('SELECT COUNT(*) as count FROM buyers').fetchone()['count']
        
        # Total inward and outward transactions
        total_inward_weight = conn.execute('SELECT COALESCE(SUM(weight_tons), 0) as total FROM inward_transactions').fetchone()['total']
        total_inward_amount = conn.execute('SELECT COALESCE(SUM(confirmed_amount), 0) as total FROM inward_transactions').fetchone()['total']
        
        total_outward_weight = conn.execute('SELECT COALESCE(SUM(weight_tons), 0) as total FROM outward_transactions').fetchone()['total']
        total_outward_amount = conn.execute('SELECT COALESCE(SUM(total_amount), 0) as total FROM outward_transactions').fetchone()['total']
        
        # Current stock (inward - outward)
        current_stock = total_inward_weight - total_outward_weight
        
        # Pending amounts
        pending_from_buyers = conn.execute('''
            SELECT COALESCE(SUM(total_amount), 0) as total 
            FROM outward_transactions 
            WHERE payment_status = "Pending"
        ''').fetchone()['total']
        
        pending_to_farmers = conn.execute('''
            SELECT COALESCE(SUM(confirmed_amount), 0) as total 
            FROM inward_transactions 
            WHERE payment_status = "Pending"
        ''').fetchone()['total']
        
        # Today's transactions
        today_str = datetime.now().strftime('%Y-%m-%d')
        
        today_inward = conn.execute('''
            SELECT COALESCE(SUM(weight_tons), 0) as weight, COALESCE(SUM(confirmed_amount), 0) as amount 
            FROM inward_transactions 
            WHERE transaction_date = ?
        ''', (today_str,)).fetchone()
        
        today_outward = conn.execute('''
            SELECT COALESCE(SUM(weight_tons), 0) as weight, COALESCE(SUM(total_amount), 0) as amount 
            FROM outward_transactions 
            WHERE transaction_date = ?
        ''', (today_str,)).fetchone()
        
        # Recent transactions for activity feed
        recent_inward = conn.execute('''
            SELECT i.*, f.name as farmer_name 
            FROM inward_transactions i 
            JOIN farmers f ON i.farmer_id = f.id 
            ORDER BY i.created_at DESC 
            LIMIT 5
        ''').fetchall()
        
        recent_outward = conn.execute('''
            SELECT o.*, b.name as buyer_name 
            FROM outward_transactions o 
            JOIN buyers b ON o.buyer_id = b.id 
            ORDER BY o.created_at DESC 
            LIMIT 5
        ''').fetchall()
        
        conn.close()
        
        return jsonify({
            'success': True,
            'data': {
                'total_farmers': total_farmers,
                'total_buyers': total_buyers,
                'total_inward_weight': round(total_inward_weight, 2),
                'total_inward_amount': round(total_inward_amount, 2),
                'total_outward_weight': round(total_outward_weight, 2),
                'total_outward_amount': round(total_outward_amount, 2),
                'current_stock': round(current_stock, 2),
                'pending_from_buyers': round(pending_from_buyers, 2),
                'pending_to_farmers': round(pending_to_farmers, 2),
                'today_inward_weight': round(today_inward['weight'], 2),
                'today_inward_amount': round(today_inward['amount'], 2),
                'today_outward_weight': round(today_outward['weight'], 2),
                'today_outward_amount': round(today_outward['amount'], 2),
                'recent_inward': [dict(row) for row in recent_inward],
                'recent_outward': [dict(row) for row in recent_outward]
            }
        })
        
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/corn_price')
@login_required
def api_corn_price():
    """API endpoint to get current corn price (mock data - replace with real API)"""
    # This is mock data. In production, you would fetch from a real commodity price API
    # or maintain a price table in your database
    mock_price = {
        'price_per_ton': 25000.00,  # Price in your currency per ton
        'currency': 'INR',
        'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'change': '+2.5%',
        'trend': 'up'  # up, down, stable
    }
    
    return jsonify({
        'success': True,
        'data': mock_price
    })

@app.route('/api/monthly_summary')
@login_required
def api_monthly_summary():
    """API endpoint to get monthly transaction summary"""
    conn = get_db_connection()
    
    try:
        # Get last 12 months data
        monthly_data = conn.execute('''
            SELECT 
                strftime('%Y-%m', transaction_date) as month,
                SUM(weight_tons) as inward_weight,
                SUM(confirmed_amount) as inward_amount
            FROM inward_transactions 
            WHERE transaction_date >= date('now', '-12 months')
            GROUP BY strftime('%Y-%m', transaction_date)
            ORDER BY month
        ''').fetchall()
        
        monthly_outward = conn.execute('''
            SELECT 
                strftime('%Y-%m', transaction_date) as month,
                SUM(weight_tons) as outward_weight,
                SUM(total_amount) as outward_amount
            FROM outward_transactions 
            WHERE transaction_date >= date('now', '-12 months')
            GROUP BY strftime('%Y-%m', transaction_date)
            ORDER BY month
        ''').fetchall()
        
        conn.close()
        
        # Combine inward and outward data
        combined_data = []
        inward_dict = {row['month']: row for row in monthly_data}
        outward_dict = {row['month']: row for row in monthly_outward}
        
        all_months = set(inward_dict.keys()) | set(outward_dict.keys())
        
        for month in sorted(all_months):
            inward = inward_dict.get(month, {'inward_weight': 0, 'inward_amount': 0})
            outward = outward_dict.get(month, {'outward_weight': 0, 'outward_amount': 0})
            
            combined_data.append({
                'month': month,
                'inward_weight': round(inward['inward_weight'] or 0, 2),
                'inward_amount': round(inward['inward_amount'] or 0, 2),
                'outward_weight': round(outward['outward_weight'] or 0, 2),
                'outward_amount': round(outward['outward_amount'] or 0, 2)
            })
        
        return jsonify({
            'success': True,
            'data': combined_data
        })
        
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'error': str(e)}), 500
    
if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))