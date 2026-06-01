import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, root_mean_squared_error
from database import get_connection
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def fetch_history_from_db():
    """Fetches all historical cryptocurrency records from SQLite database."""
    conn = get_connection()
    query = "SELECT timestamp, bitcoin_price, ethereum_price, solana_price FROM crypto_records ORDER BY timestamp ASC"
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def prepare_features(df, coin_name='bitcoin'):
    """
    Prepares supervised learning features for a given coin.
    Features:
    - Current Price
    - Previous Price
    - Price Change
    - Timestamp Hour, Minute, Day of Week
    Target:
    - Next Price (shifted by -1)
    """
    price_col = f"{coin_name}_price"
    if price_col not in df.columns:
        raise ValueError(f"Coin price column {price_col} not found in historical data.")
        
    data = df[['timestamp', price_col]].copy()
    data.rename(columns={price_col: 'current_price'}, inplace=True)
    
    # Lag features
    data['previous_price'] = data['current_price'].shift(1)
    data['price_change'] = data['current_price'] - data['previous_price']
    
    # DateTime features
    datetimes = pd.to_datetime(data['timestamp'], unit='s')
    data['hour'] = datetimes.dt.hour
    data['minute'] = datetimes.dt.minute
    data['dayofweek'] = datetimes.dt.dayofweek
    
    # Next price is the target (what we want to predict)
    data['next_price'] = data['current_price'].shift(-1)
    
    # Drop rows with NaNs in features (the very first row won't have a previous_price)
    data_clean = data.dropna(subset=['previous_price', 'price_change']).copy()
    
    return data_clean

def train_and_predict(coin_name='bitcoin'):
    """
    Trains a RandomForestRegressor on historical data and predicts the next price.
    Returns:
    - predicted_price (float)
    - mae (float)
    - rmse (float)
    - latest_actual_price (float)
    """
    df = fetch_history_from_db()
    
    # We need at least 5 records to do any meaningful feature extraction & prediction
    if len(df) < 5:
        logging.warning("Not enough historical data in SQLite to train Random Forest. Fallback active.")
        return None, 0.0, 0.0, 0.0
        
    try:
        data = prepare_features(df, coin_name)
        
        # The last row in our data has next_price as NaN because we don't know the future yet.
        # This last row will be our prediction input (X_new).
        predict_row = data[data['next_price'].isna()]
        
        # The rest of the rows are our training set.
        train_data = data.dropna(subset=['next_price'])
        
        if len(train_data) < 3:
            logging.warning("Insufficient completed training samples. Need more streaming ticks.")
            return None, 0.0, 0.0, 0.0
            
        feature_cols = ['current_price', 'previous_price', 'price_change', 'hour', 'minute', 'dayofweek']
        
        X = train_data[feature_cols]
        y = train_data['next_price']
        
        # Simple train/test split for validation (last 20% for testing)
        split_idx = int(len(train_data) * 0.8)
        if split_idx > 0:
            X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
            y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
        else:
            X_train, X_test = X, X
            y_train, y_test = y, y
            
        # Train Random Forest Regressor
        model = RandomForestRegressor(n_estimators=50, random_state=42)
        model.fit(X_train, y_train)
        
        # Make validation predictions
        y_pred = model.predict(X_test)
        
        # Calculate performance metrics
        # sklearn's root_mean_squared_error is standard in newer versions, fallback to np.sqrt(mean_squared_error) if needed
        mae = float(mean_absolute_error(y_test, y_pred))
        try:
            rmse = float(root_mean_squared_error(y_test, y_pred))
        except NameError:
            from sklearn.metrics import mean_squared_error
            rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
            
        # Fit on all available historical data to get the absolute best next-price prediction
        final_model = RandomForestRegressor(n_estimators=50, random_state=42)
        final_model.fit(X, y)
        
        # Predict the next price using the current features
        X_new = predict_row[feature_cols]
        predicted_price = float(final_model.predict(X_new)[0])
        
        latest_actual_price = float(predict_row['current_price'].values[0])
        
        logging.info(f"🌲 RandomForest Prediction for {coin_name}: Next Price -> ${predicted_price:,.2f} | MAE: {mae:.4f} | RMSE: {rmse:.4f}")
        return predicted_price, mae, rmse, latest_actual_price
        
    except Exception as e:
        logging.error(f"Error during Random Forest prediction: {e}")
        return None, 0.0, 0.0, 0.0

if __name__ == "__main__":
    # Test execution
    pred, mae, rmse, actual = train_and_predict('bitcoin')
    print(f"Pred: {pred}, MAE: {mae}, RMSE: {rmse}, Actual: {actual}")
