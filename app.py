import streamlit as st
import sqlite3
import pandas as pd
import os
import plotly.express as px
from datetime import datetime

# Streamlit page configuration
st.set_page_config(page_title="Real-Time Crypto Streaming Analytics", layout="wide")

DB_FILE = os.getenv('DB_FILE', 'crypto_data.db')

def get_db_connection():
    """Create a database connection."""
    conn = sqlite3.connect(DB_FILE)
    return conn

def fetch_recent_data(limit=100):
    """Fetch the most recent normal records."""
    conn = get_db_connection()
    query = f"SELECT * FROM crypto_records ORDER BY timestamp DESC LIMIT {limit}"
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if not df.empty:
        # Convert timestamp integer to readable datetime string
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
        # Sort ascending for plotting
        df = df.sort_values(by='timestamp')
    return df

def fetch_anomalies(limit=50):
    """Fetch the most recent anomalies."""
    conn = get_db_connection()
    query = f"SELECT * FROM crypto_anomalies ORDER BY timestamp DESC LIMIT {limit}"
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if not df.empty:
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
    return df

def main():
    st.title("🚀 Real-Time Cryptocurrency Analytics Dashboard")
    st.markdown("Live streaming data pipeline using **Apache Kafka**, **SQLite**, and **Streamlit**.")
    
    # Auto-refresh using Streamlit fragment or simply manual refresh button
    if st.button('Refresh Data'):
        pass # Streamlit reruns the script on button click
        
    df_records = fetch_recent_data()
    df_anomalies = fetch_anomalies()
    
    if df_records.empty:
        st.warning("No data found in the database. Ensure Kafka producer and consumer are running.")
        return

    # 1. Summary Metrics
    st.subheader("📊 Current Metrics (Latest Prices)")
    latest = df_records.iloc[-1]
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Bitcoin (BTC)", f"${latest['bitcoin_price']:.2f}")
    col2.metric("Ethereum (ETH)", f"${latest['ethereum_price']:.2f}")
    col3.metric("Solana (SOL)", f"${latest['solana_price']:.2f}")
    
    anomaly_count = len(df_anomalies)
    col4.metric("Anomalies Detected", anomaly_count, delta_color="inverse")

    # 2. Charts
    st.subheader("📈 Real-Time Price Trends")
    tab1, tab2, tab3 = st.tabs(["Bitcoin", "Ethereum", "Solana"])
    
    with tab1:
        fig_btc = px.line(df_records, x='datetime', y='bitcoin_price', title="Bitcoin Price over Time", markers=True)
        st.plotly_chart(fig_btc, use_container_width=True)
        
    with tab2:
        fig_eth = px.line(df_records, x='datetime', y='ethereum_price', title="Ethereum Price over Time", markers=True, color_discrete_sequence=['orange'])
        st.plotly_chart(fig_eth, use_container_width=True)
        
    with tab3:
        fig_sol = px.line(df_records, x='datetime', y='solana_price', title="Solana Price over Time", markers=True, color_discrete_sequence=['green'])
        st.plotly_chart(fig_sol, use_container_width=True)

    # 3. Latest Records & Anomalies
    st.divider()
    col_table1, col_table2 = st.columns(2)
    
    with col_table1:
        st.subheader("📋 Latest Records")
        st.dataframe(df_records[['datetime', 'bitcoin_price', 'ethereum_price', 'solana_price']].sort_values(by='datetime', ascending=False).head(10))
        
    with col_table2:
        st.subheader("🚨 Detected Anomalies")
        if df_anomalies.empty:
            st.success("No anomalies detected yet!")
        else:
            st.dataframe(df_anomalies[['datetime', 'coin_name', 'price', 'reason']].head(10))

if __name__ == "__main__":
    main()
