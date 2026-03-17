import streamlit as st
import pandas as pd
import time
import altair as alt
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from storage.database import ObservabilityDB

# --- Page Config ---
st.set_page_config(
    page_title="Observability Platform",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- Custom CSS for Stability & Dark Mode ---
st.markdown("""
<style>
    .stApp {
        background-color: #0E1117;
    }
    .metric-card {
        background-color: #262730;
        padding: 15px;
        border-radius: 5px;
        border-left: 5px solid #4CAF50;
        color: white;
    }
    .metric-card.error {
        border-left: 5px solid #FF4B4B;
    }
    .metric-card h3 {
        margin: 0;
        font-size: 1.2rem;
    }
    .metric-card p {
        font-size: 0.9rem;
        color: #B0B0B0;
    }
</style>
""", unsafe_allow_html=True)

# --- Constants ---
REFRESH_RATE = 2  # Seconds
HISTORY_WINDOW = 600 # Seconds to look back

# --- Main App ---
def main():
    st.title("📡 Live System Observability")
    
    # 1. Initialize Layout Placeholders
    # Top: System Overview
    st.markdown("### 🏥 System Health")
    top_row = st.empty()
    
    # Middle: API Metrics
    st.markdown("### 🌐 External API Reliability")
    api_metrics_placeholder = st.empty()
    
    # Bottom: Pipeline Health
    st.markdown("### 🏭 Internal Data Pipeline")
    pipeline_health_placeholder = st.empty()
    
    db = ObservabilityDB()

    # 2. Real-time Loop
    while True:
        # Fetch Data
        try:
            api_data = db.get_recent_api_metrics(seconds=HISTORY_WINDOW)
            pipeline_data = db.get_latest_pipeline_status()
            
            # --- TOP SECTION: Aggregated Health ---
            api_status = "Healthy"
            pipeline_status = "Unknown"
            
            # Check API Health
            if api_data:
                recent = pd.DataFrame(api_data)
                failure_rate = 1 - recent['is_success'].mean()
                if failure_rate > 0.1: # >10% failure
                    api_status = "Degraded"
                if failure_rate > 0.5:
                    api_status = "Down"
            else:
                api_status = "No Data"

            # Check Pipeline Health
            last_run = None
            if pipeline_data:
                # Simple logic: if last event was error -> Error, else if recent success -> Healthy
                last_event = pipeline_data[0] # Sorted DESC
                if last_event['event_type'] == 'error':
                    pipeline_status = "Critical Error"
                elif time.time() - last_event['timestamp'] > 300: # 5 mins since last activity
                    pipeline_status = "Stalled"
                else:
                    pipeline_status = "Healthy"
                    
            with top_row.container():
                c1, c2, c3 = st.columns(3)
                
                # Helper to color metrics
                def get_color(status):
                    if status in ["Healthy", "Active"]: return "normal"
                    if status in ["Degraded", "Stalled"]: return "off" # Streamlit 'off' is grey/yellow-ish
                    return "inverse" # Red-ish usually

                c1.metric("API System Status", api_status, delta=None, delta_color="normal" if api_status=="Healthy" else "inverse")
                c2.metric("Pipeline System", pipeline_status, delta=None, delta_color="normal" if pipeline_status=="Healthy" else "inverse")
                c3.metric("Last Updated", time.strftime("%H:%M:%S"))

            # --- MIDDLE SECTION: API Charts ---
            with api_metrics_placeholder.container():
                if api_data:
                    df = pd.DataFrame(api_data)
                    df['time_str'] = pd.to_datetime(df['timestamp'], unit='s')
                    
                    # Latency Chart
                    chart = alt.Chart(df).mark_line(point=True).encode(
                        x=alt.X('time_str', axis=alt.Axis(format='%H:%M:%S', title='Time')),
                        y=alt.Y('latency_ms', title='Latency (ms)'),
                        color='api_name',
                        tooltip=['api_name', 'latency_ms', 'status_code']
                    ).properties(
                        height=300
                    )
                    st.altair_chart(chart, use_container_width=True)
                    
                    # Error Count
                    errors = df[~df['is_success']]
                    if not errors.empty:
                        st.error(f"⚠️ {len(errors)} Errors detected in last window!")
                else:
                    st.info("Waiting for API metrics...")

            # --- BOTTOM SECTION: Pipeline Logs/Stats ---
            with pipeline_health_placeholder.container():
                if pipeline_data:
                    # Show last 5 events as specific table
                    df_p = pd.DataFrame(pipeline_data)
                    df_p['time_str'] = pd.to_datetime(df_p['timestamp'], unit='s').dt.strftime('%H:%M:%S')
                    
                    # Compute lag
                    lag = db.get_pipeline_lag()
                    lag_str = f"{lag:.1f}s" if lag else "N/A"
                    
                    c1, c2 = st.columns([1, 3])
                    c1.metric("Pipeline Lag", lag_str)
                    
                    c2.dataframe(
                        df_p[['time_str', 'stage', 'event_type', 'metrics_json']].head(10),
                        hide_index=True,
                        use_container_width=True
                    )
                else:
                    st.info("No pipeline events detected yet.")

        except Exception as e:
            st.error(f"Dashboard Error: {e}")
        
        time.sleep(REFRESH_RATE)

if __name__ == "__main__":
    main()
