import streamlit as st
import sqlite3
import pandas as pd
import numpy as np
import os
import requests
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from model import train_and_predict

# Configure Streamlit Page
st.set_page_config(page_title="Cryptocurrency Streaming Analytics & AI Dashboard", layout="wide")

DB_FILE = os.getenv('DB_FILE', 'crypto_data.db')
API_URL = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana&vs_currencies=usd"

def get_db_connection():
    """Create and return an SQLite connection."""
    return sqlite3.connect(DB_FILE)

def db_has_data():
    """Verify if the database exists and contains price records."""
    if not os.path.exists(DB_FILE):
        return False
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM crypto_records")
        count = cursor.fetchone()[0]
        conn.close()
        return count > 5  # Require at least 5 rows to ensure ML model works
    except Exception:
        return False

# ==========================================
# DATA RETRIEVAL FUNCTIONS
# ==========================================

def fetch_crypto_records(limit=100):
    conn = get_db_connection()
    query = f"SELECT * FROM crypto_records ORDER BY timestamp DESC LIMIT {limit}"
    df = pd.read_sql_query(query, conn)
    conn.close()
    if not df.empty:
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
        df = df.sort_values(by='timestamp')
    return df

def fetch_predictions(limit=50):
    conn = get_db_connection()
    query = f"SELECT * FROM predictions ORDER BY timestamp DESC LIMIT {limit}"
    df = pd.read_sql_query(query, conn)
    conn.close()
    if not df.empty:
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
        df = df.sort_values(by='timestamp')
    return df

def fetch_anomalies(limit=50):
    conn = get_db_connection()
    query = f"SELECT * FROM anomalies ORDER BY timestamp DESC LIMIT {limit}"
    df = pd.read_sql_query(query, conn)
    conn.close()
    if not df.empty:
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
    return df

def fetch_latest_ai_insight():
    conn = get_db_connection()
    query = "SELECT * FROM ai_insights ORDER BY id DESC LIMIT 1"
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df.iloc[0] if not df.empty else None

def fetch_recent_ai_insights(limit=5):
    conn = get_db_connection()
    query = f"SELECT timestamp, coin_name, current_price, predicted_price, risk_level, short_summary FROM ai_insights ORDER BY id DESC LIMIT {limit}"
    df = pd.read_sql_query(query, conn)
    conn.close()
    if not df.empty:
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
    return df

# ==========================================
# RENDER LOCAL PIPELINE (REAL DB)
# ==========================================

def render_db_dashboard():
    # Load raw records
    df_records = fetch_crypto_records()
    df_predictions = fetch_predictions()
    df_anomalies = fetch_anomalies()
    latest_insight = fetch_latest_ai_insight()
    df_recent_insights = fetch_recent_ai_insights()
    
    # Calculate live predictions on-the-fly for stats
    predicted_next, mae, rmse, latest_actual = train_and_predict('bitcoin')
    
    # Fetch latest evaluation error percentage
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT prediction_error FROM predictions WHERE actual_price IS NOT NULL ORDER BY timestamp DESC LIMIT 1")
    row = cursor.fetchone()
    last_error_pct = row[0] if row and row[0] is not None else 0.0
    conn.close()
    
    # ------------------------------------------
    # 1. Live Cryptocurrency Prices
    # ------------------------------------------
    latest_record = df_records.iloc[-1]
    
    st.subheader("📊 Live Cryptocurrency Prices")
    col1, col2, col3 = st.columns(3)
    col1.metric("Bitcoin (BTC)", f"${latest_record['bitcoin_price']:,.2f}")
    col2.metric("Ethereum (ETH)", f"${latest_record['ethereum_price']:,.2f}")
    col3.metric("Solana (SOL)", f"${latest_record['solana_price']:,.2f}")
    
    st.divider()
    
    # ------------------------------------------
    # 2. Machine Learning Predictions & Performance
    # ------------------------------------------
    st.subheader("🌲 Machine Learning Predictions (Random Forest)")
    
    col_ml1, col_ml2, col_ml3, col_ml4, col_ml5 = st.columns(5)
    col_ml1.metric("Current BTC Price", f"${latest_actual:,.2f}")
    col_ml2.metric("Predicted Next Price", f"${predicted_next:,.2f}" if predicted_next else "Calculating...")
    col_ml3.metric("Last Prediction Error", f"{last_error_pct:.2f}%" if last_error_pct > 0 else "N/A")
    col_ml4.metric("Model MAE", f"${mae:.2f}" if mae > 0 else "N/A")
    col_ml5.metric("Model RMSE", f"${rmse:.2f}" if rmse > 0 else "N/A")
    
    st.divider()

    # ------------------------------------------
    # 3. Forecast Visualization
    # ------------------------------------------
    st.subheader("📈 Forecast & Historical Trend Visualizations")
    tab_chart1, tab_chart2 = st.tabs(["Actual vs Predicted", "Historical Trends"])
    
    with tab_chart1:
        # Actual vs Predicted chart
        evaluated_preds = df_predictions[df_predictions['actual_price'].notna()]
        if not evaluated_preds.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=evaluated_preds['datetime'], y=evaluated_preds['actual_price'], mode='lines+markers', name='Actual Price', line=dict(color='blue')))
            fig.add_trace(go.Scatter(x=evaluated_preds['datetime'], y=evaluated_preds['predicted_price'], mode='lines+markers', name='Predicted Price', line=dict(color='orange', dash='dash')))
            fig.update_layout(title="Bitcoin Price: Actual vs Supervised Random Forest Forecast", xaxis_title="Timestamp", yaxis_title="USD ($)", hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Insufficient training iterations to visualize predictions. Actual vs Predicted comparison will render shortly.")
            
    with tab_chart2:
        # Full historical prices
        fig_hist = px.line(df_records, x='datetime', y=['bitcoin_price', 'ethereum_price', 'solana_price'], 
                           labels={"value": "Price in USD", "variable": "Cryptocurrency"},
                           title="Streaming Price Feed History")
        st.plotly_chart(fig_hist, use_container_width=True)
        
    st.divider()

    # ------------------------------------------
    # 4. AI Market Insights (Gemini)
    # ------------------------------------------
    st.subheader("🧠 Gemini AI Market Insights")
    if latest_insight is not None:
        col_ai1, col_ai2 = st.columns([2, 1])
        
        with col_ai1:
            st.markdown(f"#### Latest AI Report ({latest_insight['coin_name'].upper()})")
            st.success(latest_insight['ai_insight'])
            st.markdown(f"**Simplified Explanation:** *\"{latest_insight['short_summary']}\"*")
            
        with col_ai2:
            # Color indicator for risk level
            risk = latest_insight['risk_level']
            if risk == "High" or risk == "Critical":
                st.error(f"🚨 **Risk Assessment Level:** {risk}")
            elif risk == "Medium":
                st.warning(f"⚠️ **Risk Assessment Level:** {risk}")
            else:
                st.info(f"🟢 **Risk Assessment Level:** {risk}")
                
            st.info(f"**Model Context:** Current price ${latest_insight['current_price']:,.2f} | Forecast ${latest_insight['predicted_price']:,.2f}")
            st.markdown("##### Possible Market Drivers:")
            st.markdown(latest_insight['possible_causes'])
            
        with st.expander("📂 View Recent AI Analysis Reports"):
            if not df_recent_insights.empty:
                st.dataframe(df_recent_insights[['datetime', 'coin_name', 'current_price', 'predicted_price', 'risk_level', 'short_summary']], use_container_width=True)
    else:
        st.info("No Gemini market insights generated yet. The AI is triggered when prediction errors exceed 5% or price changes cross threshold.")

    st.divider()

    # ------------------------------------------
    # 5. Anomaly Monitoring
    # ------------------------------------------
    st.subheader("🚨 Anomaly Monitoring & Alerts")
    col_anom1, col_anom2 = st.columns([1, 3])
    
    with col_anom1:
        st.metric("Total Flagged Anomalies", len(df_anomalies), delta=None, delta_color="inverse")
        
    with col_anom2:
        if not df_anomalies.empty:
            st.dataframe(df_anomalies[['datetime', 'coin_name', 'price', 'reason']].sort_values(by='datetime', ascending=False), use_container_width=True)
        else:
            st.success("No anomalies detected in the streaming windows.")
            
    st.divider()

    # ------------------------------------------
    # 6. Historical Analytics
    # ------------------------------------------
    st.subheader("📉 Historical Analytics (Bitcoin)")
    btc_prices = df_records['bitcoin_price']
    
    col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
    col_stat1.metric("Highest Bitcoin Price", f"${btc_prices.max():,.2f}")
    col_stat2.metric("Lowest Bitcoin Price", f"${btc_prices.min():,.2f}")
    col_stat3.metric("Average Bitcoin Price", f"${btc_prices.mean():,.2f}")
    col_stat4.metric("Volatility (Std Dev)", f"${btc_prices.std():.2f}")

# ==========================================
# SIMULATED CLOUD METHOD (DEMO / NO DB)
# ==========================================

def render_simulated_dashboard():
    st.info("🌐 **Demo Mode (Cloud Fallback)** — Simulating streaming pipeline data. Run with Docker locally for actual Kafka ingestion.")
    
    # Generate seed data in st.session_state
    if 'sim_records' not in st.session_state:
        np.random.seed(42)
        base_btc = 65000.0
        base_eth = 3500.0
        base_sol = 150.0
        
        records = []
        preds = []
        anoms = []
        
        now = int(datetime.now().timestamp())
        for i in range(30):
            t = now - (30 - i) * 5
            noise_btc = np.random.normal(0, 150)
            noise_eth = np.random.normal(0, 15)
            noise_sol = np.random.normal(0, 1)
            
            btc_p = base_btc + i * 80 + noise_btc
            eth_p = base_eth + i * 5 + noise_eth
            sol_p = base_sol + i * 0.2 + noise_sol
            
            records.append({
                'timestamp': t,
                'bitcoin_price': btc_p,
                'ethereum_price': eth_p,
                'solana_price': sol_p,
                'datetime': pd.to_datetime(t, unit='s')
            })
            
            # Simulated model predictions (lagged prediction)
            if i > 0:
                pred_val = btc_p + np.random.normal(0, 50)
                preds.append({
                    'timestamp': t,
                    'coin_name': 'bitcoin',
                    'actual_price': btc_p,
                    'predicted_price': pred_val,
                    'prediction_error': abs(btc_p - pred_val) / btc_p * 100,
                    'datetime': pd.to_datetime(t, unit='s')
                })
        
        # Add 1 anomaly manually for presentation
        anoms.append({
            'timestamp': now - 50,
            'coin_name': 'bitcoin',
            'price': base_btc + 10 * 80 + 800,  # Sudden artificial swing
            'reason': "Extreme price swing detected: 5.24%",
            'datetime': pd.to_datetime(now - 50, unit='s')
        })
        
        st.session_state.sim_records = pd.DataFrame(records)
        st.session_state.sim_preds = pd.DataFrame(preds)
        st.session_state.sim_anoms = pd.DataFrame(anoms)
        
    df_records = st.session_state.sim_records
    df_predictions = st.session_state.sim_preds
    df_anomalies = st.session_state.sim_anoms
    
    # 1. Live Cryptocurrency Prices
    latest_record = df_records.iloc[-1]
    st.subheader("📊 Live Cryptocurrency Prices")
    col1, col2, col3 = st.columns(3)
    col1.metric("Bitcoin (BTC)", f"${latest_record['bitcoin_price']:,.2f}")
    col2.metric("Ethereum (ETH)", f"${latest_record['ethereum_price']:,.2f}")
    col3.metric("Solana (SOL)", f"${latest_record['solana_price']:,.2f}")
    st.divider()
    
    # 2. Machine Learning Predictions
    st.subheader("🌲 Machine Learning Predictions (Random Forest)")
    col_ml1, col_ml2, col_ml3, col_ml4, col_ml5 = st.columns(5)
    col_ml1.metric("Current BTC Price", f"${latest_record['bitcoin_price']:,.2f}")
    col_ml2.metric("Predicted Next Price", f"${latest_record['bitcoin_price'] + 45.20:,.2f}")
    col_ml3.metric("Last Prediction Error", "0.78%")
    col_ml4.metric("Model MAE", "$84.50")
    col_ml5.metric("Model RMSE", "$112.40")
    st.divider()
    
    # 3. Forecast Visualization
    st.subheader("📈 Forecast & Historical Trend Visualizations")
    tab_chart1, tab_chart2 = st.tabs(["Actual vs Predicted", "Historical Trends"])
    with tab_chart1:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df_predictions['datetime'], y=df_predictions['actual_price'], mode='lines+markers', name='Actual Price'))
        fig.add_trace(go.Scatter(x=df_predictions['datetime'], y=df_predictions['predicted_price'], mode='lines+markers', name='Predicted Price', line=dict(dash='dash')))
        fig.update_layout(title="Bitcoin Price: Actual vs Supervised Random Forest Forecast", xaxis_title="Timestamp", yaxis_title="USD ($)")
        st.plotly_chart(fig, use_container_width=True)
    with tab_chart2:
        fig_hist = px.line(df_records, x='datetime', y=['bitcoin_price', 'ethereum_price', 'solana_price'], title="Streaming Price Feed History")
        st.plotly_chart(fig_hist, use_container_width=True)
    st.divider()
    
    # 4. AI Market Insights
    st.subheader("🧠 Gemini AI Market Insights")
    col_ai1, col_ai2 = st.columns([2, 1])
    with col_ai1:
        st.markdown("#### Latest AI Report (BITCOIN)")
        st.success("The Bitcoin market shows consistent upward support as buying activity continues. The Random Forest prediction aligns with local moving average support benchmarks, demonstrating high statistical model convergence.")
        st.markdown("**Simplified Explanation:** *\"Bitcoin continues its steady climb with strong upward momentum. The ML model predicts next tick to settle close to current trading benchmarks.\"*")
    with col_ai2:
        st.warning("⚠️ **Risk Assessment Level:** Medium")
        st.info(f"**Model Context:** Current price ${latest_record['bitcoin_price']:,.2f} | Forecast ${latest_record['bitcoin_price'] + 45.20:,.2f}")
        st.markdown("##### Possible Market Drivers:")
        st.markdown("• Increased trading volumes\n• Tech breakout above historical support line\n• Macro sentiment positive")
    st.divider()
    
    # 5. Anomaly Monitoring
    st.subheader("🚨 Anomaly Monitoring & Alerts")
    col_anom1, col_anom2 = st.columns([1, 3])
    with col_anom1:
        st.metric("Total Flagged Anomalies", len(df_anomalies))
    with col_anom2:
        st.dataframe(df_anomalies[['datetime', 'coin_name', 'price', 'reason']], use_container_width=True)
    st.divider()
    
    # 6. Historical Analytics
    st.subheader("📉 Historical Analytics (Bitcoin)")
    btc_prices = df_records['bitcoin_price']
    col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
    col_stat1.metric("Highest Bitcoin Price", f"${btc_prices.max():,.2f}")
    col_stat2.metric("Lowest Bitcoin Price", f"${btc_prices.min():,.2f}")
    col_stat3.metric("Average Bitcoin Price", f"${btc_prices.mean():,.2f}")
    col_stat4.metric("Volatility (Std Dev)", f"${btc_prices.std():.2f}")

# ==========================================
# MAIN APP ENTRYPOINT
# ==========================================

def main():
    st.title("🚀 Real-Time Cryptocurrency Analytics, ML & AI Pipeline")
    st.markdown("Advanced pipeline featuring **Apache Kafka**, **SQLite**, **Scikit-Learn Random Forest Regressor** & **Google Gemini AI**.")
    
    if st.button('🔄 Refresh Dashboard'):
        pass
    
    if db_has_data():
        render_db_dashboard()
    else:
        render_simulated_dashboard()

if __name__ == "__main__":
    main()
