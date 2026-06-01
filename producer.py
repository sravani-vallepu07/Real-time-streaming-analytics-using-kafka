import json
import time
import requests
import os
from kafka import KafkaProducer
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# Kafka configuration
KAFKA_BROKER = os.getenv('KAFKA_BROKER', 'localhost:9092')
KAFKA_TOPIC = 'crypto_prices'

# CoinGecko API URL
# We fetch prices for Bitcoin, Ethereum, and Solana in USD
API_URL = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana&vs_currencies=usd"

def create_producer():
    """Create and return a Kafka producer instance."""
    try:
        producer = KafkaProducer(
            bootstrap_servers=[KAFKA_BROKER],
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            retries=5
        )
        return producer
    except Exception as e:
        logging.error(f"Failed to connect to Kafka broker: {e}")
        return None

def fetch_crypto_data():
    """Fetch real-time cryptocurrency data from CoinGecko API."""
    try:
        response = requests.get(API_URL, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logging.error(f"Error fetching data from API: {e}")
        return None

def main():
    producer = create_producer()
    if not producer:
        return

    logging.info(f"Starting producer. Sending data to topic: {KAFKA_TOPIC}")
    
    while True:
        data = fetch_crypto_data()
        
        if data:
            # Add timestamp to the payload
            payload = {
                'timestamp': int(time.time()),
                'data': data
            }
            
            # Send data to Kafka topic
            producer.send(KAFKA_TOPIC, value=payload)
            producer.flush()
            
            logging.info(f"Sent: {payload}")
        
        # Wait for 5 seconds before next request (respecting API rate limits loosely)
        time.sleep(5)

if __name__ == "__main__":
    main()
