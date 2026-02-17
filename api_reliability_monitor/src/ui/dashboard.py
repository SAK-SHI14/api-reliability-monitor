import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import time
import os
import sys
import datetime

# Add project root to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.append(project_root)

from src.storage.metrics_store import MetricsStore
from src.processor.stats import StatsProcessor

# --- PAGE CONFIGURATION (Run once) ---
st.set_page_config(
    page_title="API Reliability Monitor",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- CUSTOM CSS ---
st.markdown("""
<style>
    .stApp { background-color: #0E1117; }
    /* Card Styles */
    .metric-card {
        background-color: #262730;
        border: 1px solid #464B5C;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 10px;
    }
    .metric-value { font-size: 24px; color: #E0E0E0; font-weight: bold; }
    .metric-label { font-size: 14px; color: #A0A0A0; }
    /* Status Badges */
    .status-badge { padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 12px; }
    .status-up { background-color: #004d40; color: #00e676; border: 1px solid #00e676; }
    .status-down { background-color: #4b1113; color: #ff5252; border: 1px solid #ff5252; }
    .status-degraded { background-color: #423608; color: #ffeb3b; border: 1px solid #ffeb3b; }
</style>
""", unsafe_allow_html=True)

# --- INITIALIZATION ---
if 'store' not in st.session_state:
    st.session_state.store = MetricsStore()

# Sidebar Settings
with st.sidebar:
    st.header("Settings")
    refresh_rate = st.slider("Update Interval (s)", 1, 10, 2)
    window_minutes = st.slider("History Window (min)", 5, 60, 15)
    run_live = st.checkbox("Live Updates", value=True)
    st.divider()
    st.info("System Mode: Active Monitoring")

processor = StatsProcessor(window_minutes=window_minutes)

# --- STATIC LAYOUT (Rendered Once) ---
col_head_1, col_head_2 = st.columns([3, 1])
with col_head_1:
    st.title("📡 API Reliability Command Center")
with col_head_2:
    # Placeholder for the clock to avoid full header redraws
    clock_placeholder = st.empty()

st.markdown("---")

# Placeholders for Dynamic Content
# 1. Top KPI Row
kpi_placeholder = st.empty()

# 2. Main Charts Area
chart_row_placeholder = st.empty()

# 3. Detailed Metrics Area
metrics_row_placeholder = st.empty()

def get_status_class(row):
    if row['status'] == "DOWN": return "status-down"
    if row['error_rate_pct'] > 5: return "status-degraded"
    return "status-up"

def render_kpis(stats_df):
    if stats_df.empty: return
    
    with kpi_placeholder.container():
        cols = st.columns(len(stats_df))
        for idx, (index, row) in enumerate(stats_df.iterrows()):
            msg_class = get_status_class(row)
            with cols[idx]:
                st.markdown(f"""
                <div class="metric-card" style="border-left: 5px solid {'#FF5252' if row['status']=='DOWN' else '#00E676'};">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-weight: bold; color: #FFF;">{row['api_name']}</span>
                        <span class="status-badge {msg_class}">{row['status']}</span>
                    </div>
                    <div style="margin-top: 10px;">
                        <div style="display: flex; justify-content: space-between;">
                            <span class="metric-label">Latency</span>
                            <span style="color: #FFF; font-weight: bold;">{row['avg_latency_ms']} ms</span>
                        </div>
                        <div style="display: flex; justify-content: space-between;">
                            <span class="metric-label">Error Rate</span>
                            <span style="color: {'#FF5252' if row['error_rate_pct'] > 0 else '#00E676'}; font-weight: bold;">{row['error_rate_pct']}%</span>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

def render_charts(ts_df, stats_df):
    with chart_row_placeholder.container():
        col1, col2 = st.columns([2.5, 1])
        
        with col1:
            st.subheader("Live Latency Telemetry")
            if not ts_df.empty:
                fig = go.Figure()
                for api in ts_df['api_name'].unique():
                    data = ts_df[ts_df['api_name'] == api]
                    fig.add_trace(go.Scatter(
                        x=data['timestamp'], y=data['latency_ms'],
                        mode='lines', name=api, line=dict(width=2)
                    ))
                fig.update_layout(
                    template="plotly_dark", height=350,
                    margin=dict(l=10, r=10, t=10, b=10),
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    xaxis=dict(showgrid=True, gridcolor='#333'),
                    yaxis=dict(showgrid=True, gridcolor='#333', title="Latency (ms)"),
                    legend=dict(orientation="h", y=1.1)
                )
                st.plotly_chart(fig, use_container_width=True, key=f"latency_chart_{time.time()}")

        with col2:
            st.subheader("Operational Metrics")
            if not stats_df.empty:
                st.markdown("##### Latency Percentiles")
                style_df = stats_df[['api_name', 'p95_latency_ms', 'p99_latency_ms']].set_index('api_name')
                st.dataframe(style_df.style.highlight_max(axis=0, color='#4b1113'), use_container_width=True)
                
                st.markdown("##### Request Count")
                st.bar_chart(stats_df.set_index('api_name')['total_requests'])

def update_dashboard():
    # Fetch Data
    raw_data = st.session_state.store.load_recent(limit=5000)
    
    if not raw_data:
        kpi_placeholder.warning("Waiting for data stream...")
        return

    # Process
    stats_df = processor.process(raw_data)
    ts_df = processor.get_timeseries(raw_data)

    # Render Components
    clock_placeholder.markdown(f"<div style='text-align: right; color: gray; padding-top: 20px;'>Last Update: {datetime.datetime.now().strftime('%H:%M:%S')}</div>", unsafe_allow_html=True)
    render_kpis(stats_df)
    render_charts(ts_df, stats_df)

# --- MAIN LOOP ---
if run_live:
    try:
        # Initial render
        update_dashboard()
        
        # Loop for updates
        while True:
            time.sleep(refresh_rate)
            update_dashboard()
            
    except Exception as e:
        st.error(f"Dashboard Error: {e}")
else:
    st.info("Live updates paused.")
    if st.button("Refresh Once"):
        update_dashboard()
