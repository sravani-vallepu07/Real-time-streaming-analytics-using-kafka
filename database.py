import sqlite3
import os
import logging

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# SQLite Database File Path
DB_FILE = os.getenv('DB_FILE', 'crypto_data.db')

def get_connection():
    """Establishes and returns a connection to the SQLite database."""
    db_dir = os.path.dirname(DB_FILE)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    return sqlite3.connect(DB_FILE)

def init_db():
    """Initializes the database schema with necessary tables if they do not exist."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Crypto Records Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS crypto_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp INTEGER UNIQUE,
            bitcoin_price REAL,
            ethereum_price REAL,
            solana_price REAL
        )
    ''')
    
    # 2. Predictions Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp INTEGER UNIQUE,
            coin_name TEXT,
            actual_price REAL,
            predicted_price REAL,
            prediction_error REAL
        )
    ''')
    
    # 3. Anomalies Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS anomalies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp INTEGER,
            coin_name TEXT,
            price REAL,
            reason TEXT
        )
    ''')
    
    # 4. GenAI Insights Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_insights (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp INTEGER,
            coin_name TEXT,
            current_price REAL,
            predicted_price REAL,
            ai_insight TEXT,
            risk_level TEXT,
            possible_causes TEXT,
            short_summary TEXT
        )
    ''')
    
    conn.commit()
    conn.close()
    logging.info("SQLite database tables initialized successfully.")

def save_crypto_record(timestamp, btc_price, eth_price, sol_price):
    """Saves a fresh API price record to the database."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT OR IGNORE INTO crypto_records (timestamp, bitcoin_price, ethereum_price, solana_price)
            VALUES (?, ?, ?, ?)
        ''', (timestamp, btc_price, eth_price, sol_price))
        conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Error saving crypto record: {e}")
    finally:
        conn.close()

def save_prediction(timestamp, coin_name, actual_price, predicted_price, prediction_error):
    """Saves model predictions to the database."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT OR REPLACE INTO predictions (timestamp, coin_name, actual_price, predicted_price, prediction_error)
            VALUES (?, ?, ?, ?, ?)
        ''', (timestamp, coin_name, actual_price, predicted_price, prediction_error))
        conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Error saving prediction: {e}")
    finally:
        conn.close()

def update_prediction_actual(coin_name, actual_price):
    """
    Looks up the most recent prediction that does not have an actual price yet,
    updates it with the actual price, and calculates the absolute error percentage.
    Returns:
        prediction_error_pct (float or None)
        predicted_price (float or None)
    """
    conn = get_connection()
    cursor = conn.cursor()
    error_pct = None
    predicted_price = None
    try:
        # Get the latest prediction that has not been evaluated yet
        cursor.execute('''
            SELECT id, predicted_price FROM predictions 
            WHERE coin_name = ? AND actual_price IS NULL
            ORDER BY timestamp DESC LIMIT 1
        ''', (coin_name,))
        row = cursor.fetchone()
        
        if row:
            pred_id, predicted_price = row
            if actual_price > 0:
                error_pct = abs(actual_price - predicted_price) / actual_price * 100
                
            cursor.execute('''
                UPDATE predictions 
                SET actual_price = ?, prediction_error = ? 
                WHERE id = ?
            ''', (actual_price, error_pct, pred_id))
            conn.commit()
            logging.info(f"🔮 PREDICTION EVALUATED: {coin_name} - Actual: ${actual_price:,.2f} | Predicted: ${predicted_price:,.2f} | Error: {error_pct:.2f}%")
    except sqlite3.Error as e:
        logging.error(f"Error updating prediction actual: {e}")
    finally:
        conn.close()
    return error_pct, predicted_price

def get_last_prices(coin_name='bitcoin'):
    """Returns the two most recent prices of a cryptocurrency for comparison."""
    conn = get_connection()
    cursor = conn.cursor()
    price_col = f"{coin_name}_price"
    try:
        cursor.execute(f'''
            SELECT {price_col} FROM crypto_records 
            ORDER BY timestamp DESC LIMIT 2
        ''')
        rows = cursor.fetchall()
        if len(rows) == 2:
            return rows[0][0], rows[1][0] # (current_price, previous_price)
        elif len(rows) == 1:
            return rows[0][0], None
    except sqlite3.Error as e:
        logging.error(f"Error getting last prices: {e}")
    finally:
        conn.close()
    return None, None

def save_anomaly(timestamp, coin_name, price, reason):
    """Saves a detected price or prediction anomaly."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO anomalies (timestamp, coin_name, price, reason)
            VALUES (?, ?, ?, ?)
        ''', (timestamp, coin_name, price, reason))
        conn.commit()
        logging.warning(f"🚨 ANOMALY SAVED: {coin_name} at ${price:,.2f} - Reason: {reason}")
    except sqlite3.Error as e:
        logging.error(f"Error saving anomaly: {e}")
    finally:
        conn.close()

def save_ai_insight(timestamp, coin_name, current_price, predicted_price, ai_insight, risk_level, possible_causes, short_summary):
    """Saves a Gemini AI-generated market analysis insight."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO ai_insights (timestamp, coin_name, current_price, predicted_price, ai_insight, risk_level, possible_causes, short_summary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (timestamp, coin_name, current_price, predicted_price, ai_insight, risk_level, possible_causes, short_summary))
        conn.commit()
        logging.info("🧠 AI INSIGHT SAVED: Gemini analysis stored successfully.")
    except sqlite3.Error as e:
        logging.error(f"Error saving AI insight: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    init_db()
