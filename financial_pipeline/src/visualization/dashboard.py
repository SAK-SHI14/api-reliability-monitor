import sys
import os
import time

# Add project root to sys.path to allow imports from src
current_dir = os.path.dirname(os.path.abspath(__file__))
# current_dir = .../src/visualization
# parent = .../src
# project_root = .../financial_pipeline
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.append(project_root)

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from src.analysis.statistics_engine import StatisticsEngine
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Page Config
st.set_page_config(page_title="Financial Data Dashboard", layout="wide")

# Title
st.title("Financial Data Pipeline Dashboard (Real-Time)")

# Auto-refresh
refresh_rate = st.sidebar.slider("Refresh Rate (seconds)", 5, 300, 60)

# Load Data
def load_data():
    try:
        # Resolve path relative to project root
        # src/visualization/../../ -> project root
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        data_path = os.path.join(base_dir, "data", "processed", "analytics_data.parquet")
        
        if not os.path.exists(data_path):
            st.error(f"Data file not found at {data_path}. Please run the pipeline first.")
            return pd.DataFrame()
            
        df = pd.read_parquet(data_path)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return pd.DataFrame()

df = load_data()

if not df.empty:
    # Sidebar
    st.sidebar.header("Configuration")
    available_symbols = df['symbol'].unique()
    selected_symbol = st.sidebar.selectbox("Select Symbol", available_symbols)
    
    # Filter Data
    symbol_df = df[df['symbol'] == selected_symbol].copy()
    
    # --- Metrics ---
    st.header(f"Analysis for {selected_symbol}")
    
    stats_engine = StatisticsEngine()
    stats = stats_engine.compute_statistics(df) # Recomputing for simplicity, or could cache
    symbol_stats = stats[stats['symbol'] == selected_symbol].iloc[0]
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Mean Price", f"${symbol_stats['mean_price']:.2f}")
    col2.metric("Max Price", f"${symbol_stats['max_price']:.2f}")
    col3.metric("Volatility (Avg)", f"{symbol_stats['volatility_avg']:.4f}")
    col4.metric("Avg Daily Return", f"{symbol_stats['avg_daily_return']:.4%}")
    
    # --- Price Chart ---
    st.subheader("Price Trend & Moving Averages")
    fig_price = go.Figure()
    fig_price.add_trace(go.Scatter(x=symbol_df['timestamp'], y=symbol_df['close'], mode='lines', name='Close Price'))
    if 'sma_7' in symbol_df.columns:
        fig_price.add_trace(go.Scatter(x=symbol_df['timestamp'], y=symbol_df['sma_7'], mode='lines', name='SMA 7', line=dict(dash='dash')))
    if 'sma_30' in symbol_df.columns:
        fig_price.add_trace(go.Scatter(x=symbol_df['timestamp'], y=symbol_df['sma_30'], mode='lines', name='SMA 30', line=dict(dash='dot')))
    
    fig_price.update_layout(xaxis_title="Date", yaxis_title="Price", template="plotly_dark")
    st.plotly_chart(fig_price, use_container_width=True)
    
    # --- Volatility & Returns ---
    col_v1, col_v2 = st.columns(2)
    
    with col_v1:
        st.subheader("Rolling Volatility (7D)")
        fig_vol = px.line(symbol_df, x='timestamp', y='volatility_7d', template="plotly_dark")
        st.plotly_chart(fig_vol, use_container_width=True)
        
    with col_v2:
        st.subheader("Daily Returns Distribution")
        fig_hist = px.histogram(symbol_df, x='daily_return', nbins=50, template="plotly_dark")
        st.plotly_chart(fig_hist, use_container_width=True)
        
    # --- Raw Data ---
    with st.expander("View Raw Data"):
        st.dataframe(symbol_df)
        
    # Auto-refresh logic
    time.sleep(refresh_rate)
    st.rerun()

else:
    st.warning("No data found. Please run the pipeline first.")
    time.sleep(refresh_rate)
    st.rerun()
