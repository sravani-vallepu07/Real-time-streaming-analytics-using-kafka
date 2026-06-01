import json
import sqlite3
import logging
import os
from kafka import KafkaConsumer

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# Kafka configuration
KAFKA_BROKER = os.getenv('KAFKA_BROKER', 'localhost:9092')
KAFKA_TOPIC = 'crypto_prices'

# SQLite configuration
DB_FILE = os.getenv('DB_FILE', 'crypto_data.db')

# Simple Anomaly Thresholds (Example: if Bitcoin price < 30000 or > 100000)
BTC_MIN_THRESHOLD = 30000
BTC_MAX_THRESHOLD = 100000

def init_db():
    """Initialize SQLite database and create tables if they don't exist."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Table for all records
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS crypto_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp INTEGER,
            bitcoin_price REAL,
            ethereum_price REAL,
            solana_price REAL
        )
    ''')
    
    # Table for anomalies
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS crypto_anomalies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp INTEGER,
            coin_name TEXT,
            price REAL,
            reason TEXT
        )
    ''')
    
    conn.commit()
    conn.close()
    logging.info("Database initialized successfully.")

def save_record(timestamp, btc_price, eth_price, sol_price):
    """Save a normal record to the database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO crypto_records (timestamp, bitcoin_price, ethereum_price, solana_price) VALUES (?, ?, ?, ?)",
        (timestamp, btc_price, eth_price, sol_price)
    )
    conn.commit()
    conn.close()

def save_anomaly(timestamp, coin_name, price, reason):
    """Save an anomaly record to the database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO crypto_anomalies (timestamp, coin_name, price, reason) VALUES (?, ?, ?, ?)",
        (timestamp, coin_name, price, reason)
    )
    conn.commit()
    conn.close()
    logging.warning(f"ANOMALY DETECTED: {coin_name} at {price} ({reason})")

def detect_anomaly(timestamp, data):
    """Check for simple anomalies based on hardcoded thresholds."""
    btc_price = data.get('bitcoin', {}).get('usd', 0)
    
    if btc_price > 0:
        if btc_price < BTC_MIN_THRESHOLD:
            save_anomaly(timestamp, 'bitcoin', btc_price, f'Price dropped below {BTC_MIN_THRESHOLD}')
        elif btc_price > BTC_MAX_THRESHOLD:
            save_anomaly(timestamp, 'bitcoin', btc_price, f'Price spiked above {BTC_MAX_THRESHOLD}')

def main():
    init_db()
    
    try:
        consumer = KafkaConsumer(
            KAFKA_TOPIC,
            bootstrap_servers=[KAFKA_BROKER],
            auto_offset_reset='earliest',
            enable_auto_commit=True,
            group_id='crypto_consumer_group',
            value_deserializer=lambda x: json.loads(x.decode('utf-8'))
        )
        
        logging.info(f"Started consumer. Listening to topic: {KAFKA_TOPIC}")
        
        for message in consumer:
            payload = message.value
            timestamp = payload.get('timestamp')
            data = payload.get('data', {})
            
            btc_price = data.get('bitcoin', {}).get('usd')
            eth_price = data.get('ethereum', {}).get('usd')
            sol_price = data.get('solana', {}).get('usd')
            
            if btc_price and eth_price and sol_price:
                # Store normal record
                save_record(timestamp, btc_price, eth_price, sol_price)
                logging.info(f"Saved record: BTC=${btc_price}, ETH=${eth_price}, SOL=${sol_price}")
                
                # Check for anomalies
                detect_anomaly(timestamp, data)
                
    except Exception as e:
        logging.error(f"Consumer error: {e}")

if __name__ == "__main__":
    main()
