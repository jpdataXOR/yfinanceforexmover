import streamlit as st
import pandas as pd
import numpy as np
import time
from datetime import datetime, timedelta, timezone

from config import SYMBOLS, REFRESH_INTERVAL, HOURLY_REFRESH_INTERVAL
from calculations import calculate_metrics, update_hourly_with_5m_data, calculate_extended_metrics
from data_fetcher import load_hourly_data, fetch_latest_5m

# --- Streamlit UI ---
st.set_page_config(layout="wide", page_title="Forex Streaming Dashboard")
st.title("📈 Forex Streaming App (Hourly + 5-min Updates)")

HOURLY_REFRESH_INTERVAL = 3600  # 1 hour in seconds
FIVEM_REFRESH_INTERVAL = 300    # 5 minutes in seconds

# --- Session State Init ---
if "last_hourly_refresh" not in st.session_state:
    st.session_state.last_hourly_refresh = datetime.now(timezone.utc)
if "last_5m_refresh" not in st.session_state:
    st.session_state.last_5m_refresh = datetime.now(timezone.utc)
if "hourly_data" not in st.session_state:
    with st.spinner("Loading initial data..."):
        st.session_state.hourly_data = {}
        for name, symbol in SYMBOLS.items():
            st.session_state.hourly_data[name] = load_hourly_data(symbol)

# --- Timer Calculation ---
next_hourly_refresh = st.session_state.last_hourly_refresh + timedelta(seconds=HOURLY_REFRESH_INTERVAL)
next_5m_refresh = st.session_state.last_5m_refresh + timedelta(seconds=FIVEM_REFRESH_INTERVAL)

# --- Countdown Calculation ---
now_local = datetime.now().astimezone()
seconds_to_next_5m = int((next_5m_refresh.astimezone() - now_local).total_seconds())
if seconds_to_next_5m < 0:
    seconds_to_next_5m = 0
minutes, seconds = divmod(seconds_to_next_5m, 60)
countdown_str = f"{minutes:02d}:{seconds:02d}"

# --- UI Timers ---
status_col1, status_col2, status_col3 = st.columns([1, 1, 2])
with status_col1:
    st.metric("Next Hourly Refresh", next_hourly_refresh.astimezone().strftime("%H:%M:%S"))
with status_col2:
    st.metric("Next 5m Refresh", next_5m_refresh.astimezone().strftime("%H:%M:%S"))
    st.write(f"⏳ Countdown to next 5m refresh: **{countdown_str}**")
with status_col3:
    st.metric("Last Update", now_local.strftime("%Y-%m-%d %H:%M:%S"))

# --- Refresh Logic ---
now = datetime.now(timezone.utc)
do_hourly_refresh = (now - st.session_state.last_hourly_refresh).total_seconds() >= HOURLY_REFRESH_INTERVAL
do_5m_refresh = (now - st.session_state.last_5m_refresh).total_seconds() >= FIVEM_REFRESH_INTERVAL

if do_hourly_refresh:
    # Full refresh: reload hourly and 5m data
    with st.spinner("Refreshing hourly and 5m data..."):
        st.session_state.hourly_data = {}
        for name, symbol in SYMBOLS.items():
            st.session_state.hourly_data[name] = load_hourly_data(symbol)
        st.session_state.last_hourly_refresh = now
        st.session_state.last_5m_refresh = now  # Also update 5m timer
    st.rerun()
elif do_5m_refresh:
    # Only refresh 5m data and recalculate metrics
    with st.spinner("Refreshing 5m data..."):
        for name, symbol in SYMBOLS.items():
            hourly_df = st.session_state.hourly_data[name]
            df_5m = fetch_latest_5m(symbol)
            # Update hourly data with latest 5m close if needed
            if not df_5m.empty:
                st.session_state.hourly_data[name] = update_hourly_with_5m_data(hourly_df, df_5m)
        st.session_state.last_5m_refresh = now
    st.rerun()

# --- Main Display Function ---
def update_and_display():
    """Update data and display the dashboard along with extended metrics."""
    extended_metrics_list = []
    metrics_list = []

    for name, symbol in SYMBOLS.items():
        hourly_df = st.session_state.hourly_data[name].copy()

        # Fetch latest 5-minute data
        df_5m = fetch_latest_5m(symbol)

        # Update hourly data with latest 5m close
        if not df_5m.empty:
            hourly_df = update_hourly_with_5m_data(hourly_df, df_5m)
            st.session_state.hourly_data[name] = hourly_df

        # Extended metrics calculation
        extended = calculate_extended_metrics(name, hourly_df, df_5m)
        extended_metrics_list.append(extended)

        # Existing metrics calculation
        metrics = calculate_metrics(name, hourly_df, df_5m)
        metrics_list.append(metrics)

    # Display Extended Metrics table
    if extended_metrics_list:
        df_extended = pd.DataFrame(extended_metrics_list)
        # Reorder columns to move overallavg and overallavgabsolute after Latest 5m Timestamp
        cols = list(df_extended.columns)
        idx_5m = cols.index("Latest 5m Timestamp")
        cols.remove("overallavg")
        cols.remove("overallavgabsolute")
        cols.insert(idx_5m + 1, "overallavg")
        cols.insert(idx_5m + 2, "overallavgabsolute")
        df_extended = df_extended[cols]
        # Sort by overallavgabsolute descending
        df_extended = df_extended.sort_values("overallavgabsolute", ascending=False)

        # Color styling for overallavg
        def style_overallavg(val):
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

        styled_df_extended = df_extended.style.applymap(style_overallavg, subset=["overallavg"])
        st.markdown("### Extended Metrics")
        st.dataframe(styled_df_extended, use_container_width=True)

    # Create display dataframe for regular metrics
    df_display = pd.DataFrame(metrics_list)

    # Format the regular metrics dataframe for better display
    if not df_display.empty:
        # Convert percentage columns to proper format
        pct_cols = [col for col in df_display.columns if col.startswith("Δ-")]
        for col in pct_cols:
            df_display[col] = df_display[col].apply(lambda x: round(float(x), 2)
                if pd.notna(x) and str(x) != "N/A" and not isinstance(x, pd.Series)
                else "N/A")

        # Simple color styling function for percentages
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
#if should_refresh():
#    st.rerun()

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

# --- Debug Window ---
with st.expander("🐞 Debug Window - AUD/USD Data"):
    if "AUD/USD" in st.session_state.hourly_data:
        aud_data = st.session_state.hourly_data["AUD/USD"]
        if not aud_data.empty:
            st.write("**Total number of entries:**", len(aud_data))
            st.write("**First entry (index & values):**", 
                {"Timestamp": str(aud_data.index[0]), **aud_data.iloc[0].to_dict()})
            st.write("**Last entry (index & values):**", 
                {"Timestamp": str(aud_data.index[-1]), **aud_data.iloc[-1].to_dict()})
        else:
            st.info("AUD/USD data is empty")
    else:
        st.error("AUD/USD data not loaded")

# Footer
st.markdown("---")
st.caption(
    f"Data provided by Yahoo Finance • Last updated: {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S')} (Local Time)"
)