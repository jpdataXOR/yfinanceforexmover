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
    end = datetime.utcnow()
    start = end - timedelta(days=365)
    df = yf.download(symbol, start=start, end=end, interval="1h", progress=False)
    df.dropna(inplace=True)
    return df

def fetch_latest_5m(symbol):
    df = yf.download(symbol, period="1d", interval="5m", progress=False)
    df.dropna(inplace=True)
    return df

def calculate_metrics(symbol_name, hourly_df, df_5m):
    metrics = {
        "Instrument": symbol_name,
        "Latest Close": "N/A",
        "First Hourly": "N/A",
        "Last Hourly": "N/A",
        "Last 5m Timestamp": "N/A",
        "Next Update": (datetime.utcnow() + timedelta(seconds=refresh_interval)).strftime("%Y-%m-%d %H:%M:%S")
    }

    if not hourly_df.empty:
        hourly_df = hourly_df[~hourly_df.index.duplicated(keep="last")]
        metrics["First Hourly"] = hourly_df.index[0].strftime("%Y-%m-%d %H:%M")
        metrics["Last Hourly"] = hourly_df.index[-1].strftime("%Y-%m-%d %H:%M")
        metrics["Latest Close"] = float(hourly_df['Close'].iloc[-1])

        # Calculate last 5 percentage changes safely
        close_changes = hourly_df["Close"].pct_change().dropna() * 100
        last_n = 5
        recent_changes = close_changes.iloc[-last_n:] if len(close_changes) >= last_n else close_changes

        for i in range(last_n):
            if i < len(recent_changes):
                metrics[f"Δ-{i+1}"] = round(recent_changes.iloc[i], 2)
            else:
                metrics[f"Δ-{i+1}"] = "N/A"

    if not df_5m.empty:
        latest_5m_time = df_5m.index[-1]
        metrics["Last 5m Timestamp"] = latest_5m_time.strftime("%Y-%m-%d %H:%M")

    return metrics

# --- Streamlit UI ---
st.set_page_config(layout="wide")
st.title("📈 Forex Streaming App (Hourly + 5-min Updates)")

# --- Session State Init ---
if "hourly_data" not in st.session_state:
    st.session_state.hourly_data = {
        name: load_hourly_data(symbol) for name, symbol in symbols.items()
    }

# --- Live Display Placeholder ---
placeholder = st.empty()

def update_and_display():
    metrics_list = []

    for name, symbol in symbols.items():
        hourly_df = st.session_state.hourly_data[name]

        # Fetch 5-minute data
        df_5m = fetch_latest_5m(symbol)

        # Replace last hourly candle with the last 5m close
        if not df_5m.empty:
            latest_5m_time = df_5m.index[-1]
            latest_5m_close = df_5m["Close"].iloc[-1]

            if not hourly_df.empty:
                last_hour_time = hourly_df.index[-1]
                # Replace only if the 5m time is within current hour
                if latest_5m_time > last_hour_time:
                    new_row = pd.DataFrame(
                        {"Close": [latest_5m_close]},
                        index=[latest_5m_time.replace(minute=0, second=0, microsecond=0)]
                    )
                    hourly_df = pd.concat([hourly_df, new_row])
                    hourly_df = hourly_df[~hourly_df.index.duplicated(keep="last")]
                    st.session_state.hourly_data[name] = hourly_df
                else:
                    # Replace the last row's close with latest 5m close
                    hourly_df.iloc[-1, hourly_df.columns.get_loc("Close")] = latest_5m_close
                    st.session_state.hourly_data[name] = hourly_df

        metrics = calculate_metrics(name, hourly_df, df_5m)
        metrics_list.append(metrics)

    df_display = pd.DataFrame(metrics_list)

    # Format percentage columns
    pct_cols = [col for col in df_display.columns if col.startswith("Δ-")]
    for col in pct_cols:
        df_display[col] = pd.to_numeric(df_display[col], errors="coerce").round(2).fillna("N/A")

    # Display
    with placeholder.container():
        st.dataframe(df_display, use_container_width=True)

# --- Main Loop ---
while True:
    update_and_display()
    time.sleep(refresh_interval)