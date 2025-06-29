import sqlite3
import os

# --- Configuration ---
DATABASE_FILE = 'corn_trading.db'

def clear_all_data():
    """
    Deletes all entries from the transactions, farmers, and buyers tables
    after asking for user confirmation.
    """
    # Safety check to prevent accidental deletion
    confirm = input(
        "🚨 WARNING: This will permanently delete all transaction, farmer, and "
        "buyer data from the database.\n"
        "   Your admin login will NOT be affected.\n"
        "   Are you sure you want to continue? (y/N): "
    )

    if confirm.lower() != 'y':
        print("\n🚫 Deletion cancelled.")
        return

    if not os.path.exists(DATABASE_FILE):
        print(f"❌ Error: Database file '{DATABASE_FILE}' not found.")
        return

    try:
        # Connect to the SQLite database
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        print(f"\n✅ Connected to database: {DATABASE_FILE}")

        # Define the tables to clear, in the correct order
        # (child tables first, then parent tables)
        tables_to_clear = [
            'inward_transactions',
            'outward_transactions',
            'farmers',
            'buyers'
        ]

        for table in tables_to_clear:
            print(f"   > Clearing table: {table}...")
            cursor.execute(f"DELETE FROM {table};")
            # Optional: Reset the auto-incrementing ID counter
            cursor.execute(f"DELETE FROM sqlite_sequence WHERE name='{table}';")
        
        # Commit the changes to the database
        conn.commit()
        print("\n✅ All specified data has been successfully deleted.")

    except sqlite3.Error as e:
        print(f"❌ A database error occurred: {e}")
    finally:
        # Ensure the database connection is closed
        if conn:
            conn.close()
            print("✅ Database connection closed.")


if __name__ == '__main__':
    clear_all_data()
