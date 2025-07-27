import pandas as pd
from datetime import datetime, timedelta
import streamlit as st
from config import REFRESH_INTERVAL
import math

def calculate_metrics(symbol_name: str, hourly_df: pd.DataFrame, df_5m: pd.DataFrame) -> dict:
    """Calculate all metrics for display.

    Args:
        symbol_name (str): The display name of the instrument.
        hourly_df (pd.DataFrame): The dataframe with hourly data.
        df_5m (pd.DataFrame): The dataframe with 5-minute data.

    Returns:
        dict: A dictionary containing calculated metrics.
    """
    metrics = {
        "Instrument": symbol_name,
        "Latest Close": "N/A",
        "First Hourly": "N/A",
        "Last Hourly": "N/A",
        "Last 5m Timestamp": "N/A",
        "Next Update": (datetime.utcnow() + timedelta(seconds=REFRESH_INTERVAL)).strftime("%Y-%m-%d %H:%M:%S")
    }

    if not hourly_df.empty:
        # Remove any duplicate timestamps
        hourly_df = hourly_df[~hourly_df.index.duplicated(keep="last")]
        
        metrics["First Hourly"] = hourly_df.index[0].strftime("%Y-%m-%d %H:%M")
        metrics["Last Hourly"] = hourly_df.index[-1].strftime("%Y-%m-%d %H:%M")
        metrics["Latest Close"] = round(float(hourly_df['Close'].iloc[-1]), 4)

        # Calculate percentage changes
        close_changes = hourly_df["Close"].pct_change().dropna() * 100
        last_n = 5
        
        # Get the most recent changes
        recent_changes = close_changes.tail(last_n)

        # Assign changes in reverse order (most recent first)
        for i in range(last_n):
            if i < len(recent_changes):
                # Use negative indexing to get most recent first and convert to scalar
                change_value = recent_changes.iloc[-(i+1)]
                metrics[f"Δ-{i+1}"] = round(float(change_value), 2)
            else:
                metrics[f"Δ-{i+1}"] = "N/A"

    if not df_5m.empty:
        latest_5m_time = df_5m.index[-1]
        metrics["Last 5m Timestamp"] = latest_5m_time.strftime("%Y-%m-%d %H:%M")

    return metrics

def update_hourly_with_5m_data(hourly_df: pd.DataFrame, df_5m: pd.DataFrame) -> pd.DataFrame:
    """Update hourly data with latest 5-minute close price.

    Args:
        hourly_df (pd.DataFrame): The dataframe with hourly data.
        df_5m (pd.DataFrame): The dataframe with 5-minute data.

    Returns:
        pd.DataFrame: The updated hourly dataframe.
    """
    if df_5m.empty or hourly_df.empty:
        return hourly_df
    
    hourly_df = hourly_df.copy()
    
    latest_5m_time = df_5m.index[-1]
    latest_5m_close = float(df_5m["Close"].iloc[-1])
    
    current_hour = latest_5m_time.replace(minute=0, second=0, microsecond=0)
    last_hourly_time = hourly_df.index[-1]
    
    if current_hour > last_hourly_time:
        new_row = pd.DataFrame({
            'Open': [latest_5m_close],
            'High': [latest_5m_close],
            'Low': [latest_5m_close],
            'Close': [latest_5m_close]
        }, index=[current_hour])
        hourly_df = pd.concat([hourly_df, new_row])
    else:
        hourly_df.loc[last_hourly_time, 'Close'] = latest_5m_close
    
    return hourly_df

def calculate_extended_metrics(symbol_name: str, hourly_df: pd.DataFrame, df_5m: pd.DataFrame) -> dict:
    """
    Calculate extended metrics:
      - Instrument
      - Latest Close (from 5m data if available, else hourly)
      - Latest Hourly Close (last value in hourly_df)
      - Last Hourly Timestamp
      - Percentage difference between latest hourly and 6, 13, 100, and 200 hours ago.
    """
    from datetime import timedelta
    extended = {
       "Instrument": symbol_name,
       "Latest Close": "N/A",
       "Latest Hourly Close": "N/A",
       "Last Hourly Timestamp": "N/A",
       "Pct Diff 6h": "N/A",
       "Pct Diff 13h": "N/A",
       "Pct Diff 100h": "N/A",
       "Pct Diff 200h": "N/A",
    }
    if hourly_df.empty:
        return extended

    # Remove duplicate timestamps and sort
    hourly_df = hourly_df[~hourly_df.index.duplicated(keep='last')]
    hourly_df.sort_index(inplace=True)
    
    # Latest hourly info
    last_hourly_time = hourly_df.index[-1]
    latest_hourly_close = hourly_df['Close'].iloc[-1]
    extended["Latest Hourly Close"] = round(float(latest_hourly_close), 4)
    extended["Last Hourly Timestamp"] = last_hourly_time.strftime("%Y-%m-%d %H:%M")
    
    # Latest Close: use 5-minute data if available, else hourly
    if not df_5m.empty:
        latest_close = float(df_5m["Close"].iloc[-1])
        extended["Latest Close"] = round(latest_close, 4)
    else:
        extended["Latest Close"] = round(float(latest_hourly_close), 4)
    
    # Helper to compute percentage difference using searchsorted to get closest past value
    def calc_pct_diff(offset_hours):
        target_time = last_hourly_time - timedelta(hours=offset_hours)
        # Find the insertion index for the target time
        idx = hourly_df.index.searchsorted(target_time)
        if idx == 0:
            return "N/A"
        try:
            past_close = float(hourly_df["Close"].iloc[idx - 1])
        except Exception:
            return "N/A"
        if math.isnan(past_close) or past_close == 0:
            return "N/A"
        return round(((latest_hourly_close - past_close) / past_close) * 100, 2)
    
    extended["Pct Diff 6h"] = calc_pct_diff(6)
    extended["Pct Diff 13h"] = calc_pct_diff(13)
    extended["Pct Diff 100h"] = calc_pct_diff(100)
    extended["Pct Diff 200h"] = calc_pct_diff(200)
    
    return extended