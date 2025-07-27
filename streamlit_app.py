import streamlit as st
import pandas as pd
import numpy as np
import time
from datetime import datetime, timedelta

from config import SYMBOLS, REFRESH_INTERVAL, HOURLY_REFRESH_INTERVAL
from calculations import calculate_metrics, update_hourly_with_5m_data
from data_fetcher import load_hourly_data, fetch_latest_5m

# --- Streamlit UI ---
st.set_page_config(layout="wide", page_title="Forex Streaming Dashboard")
st.title("📈 Forex Streaming App (Hourly + 5-min Updates)")

# Add a status indicator
status_col1, status_col2, status_col3 = st.columns([1, 1, 2])
with status_col1:
    st.metric("Refresh Interval", f"{REFRESH_INTERVAL}s")
with status_col2:
    st.metric("Last Update", datetime.utcnow().strftime("%H:%M:%S"))

# --- Session State Init ---
if "hourly_data" not in st.session_state:
    with st.spinner("Loading initial data..."):
        st.session_state.hourly_data = {}
        for name, symbol in SYMBOLS.items():
            st.session_state.hourly_data[name] = load_hourly_data(symbol)

if "last_update" not in st.session_state:
    st.session_state.last_update = datetime.utcnow()

# --- Auto-refresh Logic ---
def should_refresh():
    """Check if it's time to refresh"""
    now = datetime.utcnow()
    return (now - st.session_state.last_update).total_seconds() >= REFRESH_INTERVAL

# --- Main Display Function ---
def update_and_display():
    """Update data and display the dashboard"""
    metrics_list = []

    for name, symbol in SYMBOLS.items():
        hourly_df = st.session_state.hourly_data[name].copy()

        # Fetch latest 5-minute data
        df_5m = fetch_latest_5m(symbol)

        # Update hourly data with latest 5m close
        if not df_5m.empty:
            hourly_df = update_hourly_with_5m_data(hourly_df, df_5m)
            st.session_state.hourly_data[name] = hourly_df

        # Calculate metrics using shared code
        metrics = calculate_metrics(name, hourly_df, df_5m)
        metrics_list.append(metrics)

    # Create display dataframe
    df_display = pd.DataFrame(metrics_list)

    # Format the dataframe for better display
    if not df_display.empty:
        # Convert percentage columns to proper format
        pct_cols = [col for col in df_display.columns if col.startswith("Δ-")]
        for col in pct_cols:
            df_display[col] = df_display[col].apply(lambda x: round(float(x), 2)
                if pd.notna(x) and str(x) != "N/A" and not isinstance(x, pd.Series)
                else "N/A")

        # Simple color styling function that works with scalars
        def style_percentage(val):
            if val == "N/A" or pd.isna(val):
                return ""
            try:
                if float(val) > 0:
                    return "background-color: #d4edda; color: #155724"
                elif float(val) < 0:
                    return "background-color: #f8d7da; color: #721c24"
            except:
                pass
            return ""

        try:
            if pct_cols:
                styled_df = df_display.style.applymap(style_percentage, subset=pct_cols)
                st.dataframe(styled_df, use_container_width=True)
            else:
                st.dataframe(df_display, use_container_width=True)
        except Exception as e:
            st.dataframe(df_display, use_container_width=True)

        # Update last refresh time
        st.session_state.last_update = datetime.utcnow()
    else:
        st.error("No data to display")

# --- Display Data ---
update_and_display()

# --- Auto-refresh Setup ---
if should_refresh():
    st.rerun()

# Add refresh button for manual updates
if st.button("🔄 Manual Refresh", help="Click to refresh data immediately"):
    try:
        st.cache_data.clear()
        with st.spinner("Refreshing data..."):
            st.session_state.hourly_data = {}
            for name, symbol in SYMBOLS.items():
                st.session_state.hourly_data[name] = load_hourly_data(symbol)
        st.success("Data refreshed successfully!")
        st.rerun()
    except Exception as e:
        st.error(f"Error refreshing data: {e}")

# --- Additional Info ---
with st.expander("ℹ️ App Information"):
    st.write("""
    **How it works:**
    - Fetches hourly data for the past year (cached for 1 hour)
    - Updates every 15 seconds with latest 5-minute data
    - Δ-1 through Δ-5 show the last 5 hourly percentage changes
    - Δ-1 is the most recent change, Δ-5 is the oldest of the last 5

    **Instruments:**
    - BTC-USD: Bitcoin to US Dollar
    - AUD/USD: Australian Dollar to US Dollar  
    - USD/JPY: US Dollar to Japanese Yen

    **Colors:**
    - 🟢 Green: Positive percentage change
    - 🔴 Red: Negative percentage change
    """)

# Footer
st.markdown("---")
st.caption(f"Data provided by Yahoo Finance • Last updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")