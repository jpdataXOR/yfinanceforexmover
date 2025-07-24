import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import time

# --- Configuration ---
symbols = {
    "BTC-USD": "BTC-USD",
    "AUD/USD": "AUDUSD=X",
    "USD/JPY": "USDJPY=X"
}
refresh_interval = 15  # seconds
hourly_refresh_interval = 3600  # seconds

# --- Functions ---

@st.cache_data(ttl=hourly_refresh_interval)
def load_hourly_data(symbol):
    """Load hourly data for the past year"""
    end = datetime.utcnow()
    start = end - timedelta(days=365)
    try:
        df = yf.download(symbol, start=start, end=end, interval="1h", progress=False)
        df.dropna(inplace=True)
        return df
    except Exception as e:
        st.error(f"Error loading hourly data for {symbol}: {e}")
        return pd.DataFrame()

def fetch_latest_5m(symbol):
    """Fetch latest 5-minute data for today"""
    try:
        df = yf.download(symbol, period="1d", interval="5m", progress=False)
        df.dropna(inplace=True)
        return df
    except Exception as e:
        st.error(f"Error fetching 5m data for {symbol}: {e}")
        return pd.DataFrame()

def calculate_metrics(symbol_name, hourly_df, df_5m):
    """Calculate all metrics for display"""
    metrics = {
        "Instrument": symbol_name,
        "Latest Close": "N/A",
        "First Hourly": "N/A",
        "Last Hourly": "N/A",
        "Last 5m Timestamp": "N/A",
        "Next Update": (datetime.utcnow() + timedelta(seconds=refresh_interval)).strftime("%Y-%m-%d %H:%M:%S")
    }

    if not hourly_df.empty:
        # Remove any duplicate timestamps
        hourly_df = hourly_df[~hourly_df.index.duplicated(keep="last")]
        
        metrics["First Hourly"] = hourly_df.index[0].strftime("%Y-%m-%d %H:%M")
        metrics["Last Hourly"] = hourly_df.index[-1].strftime("%Y-%m-%d %H:%M")
        metrics["Latest Close"] = round(float(hourly_df['Close'].iloc[-1]), 4)

        # Calculate percentage changes - FIXED VERSION
        close_changes = hourly_df["Close"].pct_change().dropna() * 100
        last_n = 5
        
        # Get the most recent changes
        if len(close_changes) >= last_n:
            recent_changes = close_changes.iloc[-last_n:]
        else:
            recent_changes = close_changes

        # Assign changes in reverse order (most recent first)
        for i in range(last_n):
            if i < len(recent_changes):
                # Use negative indexing to get most recent first and convert to scalar
                change_value = recent_changes.iloc[-(i+1)]
                # Ensure it's a scalar value, not a Series
                if hasattr(change_value, 'item'):
                    metrics[f"Δ-{i+1}"] = round(change_value.item(), 2)
                else:
                    metrics[f"Δ-{i+1}"] = round(float(change_value), 2)
            else:
                metrics[f"Δ-{i+1}"] = "N/A"

    if not df_5m.empty:
        latest_5m_time = df_5m.index[-1]
        metrics["Last 5m Timestamp"] = latest_5m_time.strftime("%Y-%m-%d %H:%M")

    return metrics

def update_hourly_with_5m_data(hourly_df, df_5m):
    """Update hourly data with latest 5-minute close price"""
    if df_5m.empty or hourly_df.empty:
        return hourly_df
    
    # Make a copy to avoid modifying original data
    hourly_df = hourly_df.copy()
    
    latest_5m_time = df_5m.index[-1]
    latest_5m_close = float(df_5m["Close"].iloc[-1])  # Ensure it's a scalar
    
    # Get the current hour timestamp
    current_hour = latest_5m_time.replace(minute=0, second=0, microsecond=0)
    last_hourly_time = hourly_df.index[-1]
    
    # If we're in a new hour, add a new row
    if current_hour > last_hourly_time:
        # Create new hourly candle with 5m close as all OHLC values
        new_row = pd.DataFrame({
            'Open': [latest_5m_close],
            'High': [latest_5m_close], 
            'Low': [latest_5m_close],
            'Close': [latest_5m_close],
            'Volume': [0]  # Default volume
        }, index=[current_hour])
        
        hourly_df = pd.concat([hourly_df, new_row])
    else:
        # Update the close price of the current hour using iloc for safer indexing
        try:
            if 'Close' in hourly_df.columns:
                # Use iloc to avoid index issues
                hourly_df.iloc[-1, hourly_df.columns.get_loc('Close')] = latest_5m_close
        except Exception as e:
            # If update fails, just return the original data
            st.warning(f"Could not update hourly close price: {e}")
            pass
    
    # Remove duplicates and return
    return hourly_df[~hourly_df.index.duplicated(keep="last")]

# --- Streamlit UI ---
st.set_page_config(layout="wide", page_title="Forex Streaming Dashboard")
st.title("📈 Forex Streaming App (Hourly + 5-min Updates)")

# Add a status indicator
status_col1, status_col2, status_col3 = st.columns([1, 1, 2])
with status_col1:
    st.metric("Refresh Interval", f"{refresh_interval}s")
with status_col2:
    st.metric("Last Update", datetime.utcnow().strftime("%H:%M:%S"))

# --- Session State Init ---
if "hourly_data" not in st.session_state:
    with st.spinner("Loading initial data..."):
        st.session_state.hourly_data = {}
        for name, symbol in symbols.items():
            st.session_state.hourly_data[name] = load_hourly_data(symbol)

if "last_update" not in st.session_state:
    st.session_state.last_update = datetime.utcnow()

# --- Auto-refresh Logic ---
def should_refresh():
    """Check if it's time to refresh"""
    now = datetime.utcnow()
    return (now - st.session_state.last_update).total_seconds() >= refresh_interval

# --- Main Display Function ---
def update_and_display():
    """Update data and display the dashboard"""
    metrics_list = []

    for name, symbol in symbols.items():
        hourly_df = st.session_state.hourly_data[name].copy()

        # Fetch latest 5-minute data
        df_5m = fetch_latest_5m(symbol)

        # Update hourly data with latest 5m close
        if not df_5m.empty:
            hourly_df = update_hourly_with_5m_data(hourly_df, df_5m)
            st.session_state.hourly_data[name] = hourly_df

        # Calculate metrics
        metrics = calculate_metrics(name, hourly_df, df_5m)
        metrics_list.append(metrics)

    # Create display dataframe
    df_display = pd.DataFrame(metrics_list)

    # Format the dataframe for better display
    if not df_display.empty:
        # Convert percentage columns to proper format
        pct_cols = [col for col in df_display.columns if col.startswith("Δ-")]
        
        # Clean up the percentage columns - convert Series to scalar values
        for col in pct_cols:
            df_display[col] = df_display[col].apply(lambda x: 
                round(float(x), 2) if pd.notna(x) and str(x) != "N/A" and not isinstance(x, pd.Series) 
                else "N/A"
            )
        
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
        
        # Apply styling only if we have percentage columns
        try:
            if pct_cols:
                styled_df = df_display.style.applymap(style_percentage, subset=pct_cols)
                st.dataframe(styled_df, use_container_width=True)
            else:
                st.dataframe(df_display, use_container_width=True)
        except Exception as e:
            # Fallback to plain dataframe
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
        # Clear cache to force fresh data
        st.cache_data.clear()
        
        # Reload hourly data for all symbols
        with st.spinner("Refreshing data..."):
            st.session_state.hourly_data = {}
            for name, symbol in symbols.items():
                st.session_state.hourly_data[name] = load_hourly_data(symbol)
        
        st.success("Data refreshed successfully!")
        st.rerun()
    except Exception as e:
        st.error(f"Error refreshing data: {e}")
        # Try to continue with existing data
        pass

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