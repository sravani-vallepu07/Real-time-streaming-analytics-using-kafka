import json
import logging
import os
from kafka import KafkaConsumer
from database import (
    init_db,
    save_crypto_record,
    update_prediction_actual,
    get_last_prices,
    save_anomaly,
    save_prediction
)
from model import train_and_predict
from genai_analysis import generate_ai_analysis

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Kafka configuration
KAFKA_BROKER = os.getenv('KAFKA_BROKER', 'localhost:9092')
KAFKA_TOPIC = 'crypto_prices'

# Anomaly Thresholds
PRICE_CHANGE_THRESHOLD = 5.0  # 5% price change
PREDICTION_ERROR_THRESHOLD = 5.0  # 5% prediction error

def run_anomaly_and_genai(timestamp, coin_name, current_price, previous_price, prediction_error_pct, predicted_price_prev):
    """
    Performs anomaly detection and determines if a GenAI report should be generated.
    Anomalies are stored, and Gemini AI analysis is triggered on threshold breach.
    """
    has_anomaly = False
    anomaly_reason = ""
    price_change_pct = 0.0
    
    # 1. Price Change Anomaly Check
    if previous_price and previous_price > 0:
        price_change_pct = ((current_price - previous_price) / previous_price) * 100
        if abs(price_change_pct) >= PRICE_CHANGE_THRESHOLD:
            has_anomaly = True
            anomaly_reason = f"Extreme price swing detected: {price_change_pct:.2f}%"
            save_anomaly(timestamp, coin_name, current_price, anomaly_reason)
            
    # 2. Prediction Error Anomaly Check
    if prediction_error_pct and prediction_error_pct >= PREDICTION_ERROR_THRESHOLD:
        has_anomaly = True
        reason = f"Large prediction error: {prediction_error_pct:.2f}% (Actual: ${current_price:,.2f}, Predicted: ${predicted_price_prev:,.2f})"
        anomaly_reason = anomaly_reason + " | " + reason if anomaly_reason else reason
        save_anomaly(timestamp, coin_name, current_price, reason)
        
    # 3. Trigger Gemini AI Analysis if any threshold is exceeded
    if has_anomaly or abs(price_change_pct) >= PRICE_CHANGE_THRESHOLD or (prediction_error_pct and prediction_error_pct >= PREDICTION_ERROR_THRESHOLD):
        logging.info(f"🔮 Triggering Gemini AI Market Insight for {coin_name.upper()}...")
        
        # Use fallback prev prediction price for the prompt if not fully tracked yet
        pred_val = predicted_price_prev if predicted_price_prev else current_price
        pred_error = prediction_error_pct if prediction_error_pct else 0.0
        
        generate_ai_analysis(
            timestamp=timestamp,
            coin_name=coin_name,
            current_price=current_price,
            predicted_price=pred_val,
            price_change_pct=price_change_pct,
            prediction_error_pct=pred_error
        )

def main():
    # Initialize SQLite database
    init_db()
    
    try:
        # Start Kafka Consumer
        consumer = KafkaConsumer(
            KAFKA_TOPIC,
            bootstrap_servers=[KAFKA_BROKER],
            auto_offset_reset='earliest',
            enable_auto_commit=True,
            group_id='crypto_consumer_group',
            value_deserializer=lambda x: json.loads(x.decode('utf-8'))
        )
        
        logging.info(f"Started consumer. Subscribed to topic: {KAFKA_TOPIC}")
        
        for message in consumer:
            payload = message.value
            timestamp = payload.get('timestamp')
            data = payload.get('data', {})
            
            btc_price = data.get('bitcoin', {}).get('usd')
            eth_price = data.get('ethereum', {}).get('usd')
            sol_price = data.get('solana', {}).get('usd')
            
            if btc_price and eth_price and sol_price:
                # 1. Save fresh record
                save_crypto_record(timestamp, btc_price, eth_price, sol_price)
                logging.info(f"📥 Saved record: BTC=${btc_price:,.2f}, ETH=${eth_price:,.2f}, SOL=${sol_price:,.2f}")
                
                # 2. Evaluate previously outstanding predictions against actual price
                prediction_error_pct, predicted_price_prev = update_prediction_actual('bitcoin', btc_price)
                
                # 3. Get last two prices to calculate live percentage changes
                current_btc, prev_btc = get_last_prices('bitcoin')
                
                # 4. Perform anomaly checks and trigger Gemini GenAI insights
                run_anomaly_and_genai(
                    timestamp=timestamp,
                    coin_name='bitcoin',
                    current_price=btc_price,
                    previous_price=prev_btc,
                    prediction_error_pct=prediction_error_pct,
                    predicted_price_prev=predicted_price_prev
                )
                
                # 5. Run Random Forest to predict the NEXT price tick (e.g. at timestamp + 5)
                predicted_next_price, mae, rmse, _ = train_and_predict('bitcoin')
                
                if predicted_next_price is not None:
                    # Save the prediction for the upcoming timestamp (approx + 5 seconds)
                    save_prediction(
                        timestamp=timestamp + 5,
                        coin_name='bitcoin',
                        actual_price=None,
                        predicted_price=predicted_next_price,
                        prediction_error=None
                    )
                    logging.info(f"🌲 Saved future prediction: Next BTC -> ${predicted_next_price:,.2f}")
                    
    except Exception as e:
        logging.error(f"Consumer execution error: {e}")

if __name__ == "__main__":
    main()
