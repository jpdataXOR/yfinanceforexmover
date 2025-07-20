import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import time
from datetime import datetime, timedelta

# --- Configuration ---
symbols = {
    "BTC-USD": "BTC-USD",
    "AUD/USD": "AUDUSD=X",
    "USD/JPY": "USDJPY=X"
}
refresh_interval = 30  # seconds

# --- Functions ---

@st.cache_data
def load_initial_data(symbol):
    end = datetime.utcnow()
    start = end - timedelta(days=365)
    df = yf.download(symbol, start=start, end=end, interval="1h", progress=False)
    df.dropna(inplace=True)
    return df

def fetch_latest_data(symbol):
    df = yf.download(symbol, period="1d", interval="5m", progress=False)
    df.dropna(inplace=True)
    return df

def calculate_metrics(symbol_name, df):
    print(f"\n--- Debug: {symbol_name} ---")
    print(f"Data length: {len(df)}")
    print(f"Last index: {df.index[-1] if not df.empty else 'Empty'}")
    if df.empty:
        print("Empty dataframe!")
        return {
            "Instrument": symbol_name,
            "Last Fetch": "Insufficient Data",
            "Latest Close": np.nan,
        }

    # Extract scalar latest close price properly
    latest_close = df['Close'].iloc[-1]
    if isinstance(latest_close, pd.Series):
        latest_close = float(latest_close.iloc[0])
    else:
        latest_close = float(latest_close)

    last_time = df.index[-1]
    last_time_str = last_time.strftime("%Y-%m-%d %H:%M")

    last_6_closes = df['Close'].iloc[-6:]
    print(f"Last 6 closes:\n{last_6_closes}")

    close_pct_changes = last_6_closes.pct_change().dropna() * 100
    print(f"Close pct changes (last 6):\n{close_pct_changes}")

    def get_pct_change(periods_ago):
        try:
            past_value = df['Close'].iloc[-1 - periods_ago]
            # Handle if past_value is Series:
            if isinstance(past_value, pd.Series):
                past_value = float(past_value.iloc[0])
            else:
                past_value = float(past_value)

            change = ((latest_close - past_value) / past_value) * 100
            print(f"Change vs -{periods_ago}: {change:.4f}% (latest_close={latest_close}, past_value={past_value})")
            return change
        except IndexError:
            print(f"IndexError: Not enough data for -{periods_ago} periods ago")
            return np.nan

    changes = {}
    for p in [6, 13, 624, 1324]:
        changes[f'Δ vs -{p}'] = get_pct_change(p)

    metrics = {
        "Instrument": symbol_name,
        "Last Fetch": last_time_str,
        "Latest Close": latest_close,
    }

    for i, pct in enumerate(close_pct_changes[::-1]):
        metrics[f"Δ-{i+1}"] = pct

    metrics.update(changes)
    return metrics

# --- Streamlit UI ---
st.title("📈 Forex Streaming App (Powered by yfinance)")

# Data Store
if 'data_store' not in st.session_state:
    st.session_state.data_store = {}
    for name, symbol in symbols.items():
        st.session_state.data_store[name] = load_initial_data(symbol)

placeholder = st.empty()

def update_and_display():
    metric_list = []

    for name, symbol in symbols.items():
        df = st.session_state.data_store[name]

        # Fetch latest 5-minute data
        latest_df = fetch_latest_data(symbol)
        if not latest_df.empty and latest_df.index[-1] > df.index[-1]:
            # Append latest row if it's new
            new_row = latest_df.iloc[[-1]]
            df = pd.concat([df, new_row])
            df = df[~df.index.duplicated(keep='last')]
            st.session_state.data_store[name] = df

        # --- Calculate summary metrics ---
        metrics = calculate_metrics(name, df)
        metric_list.append(metrics)

    # Create DataFrame from collected metrics
    result_df = pd.DataFrame(metric_list)

    # Identify percentage change columns
    percentage_cols = [col for col in result_df.columns if "Δ" in col]

    # Safely convert and round only numeric columns
    for col in percentage_cols:
        result_df[col] = pd.to_numeric(result_df[col], errors="coerce").round(2)

    # Optional: replace NaN with 'N/A'
    result_df[percentage_cols] = result_df[percentage_cols].fillna("N/A")

    # Display the DataFrame
    placeholder.dataframe(result_df, use_container_width=True)

# --- Run the auto-updater loop ---
while True:
    update_and_display()
    time.sleep(refresh_interval)
