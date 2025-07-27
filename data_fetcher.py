import warnings
warnings.filterwarnings("ignore")

import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from config import HOURLY_REFRESH_INTERVAL

@st.cache_data(ttl=HOURLY_REFRESH_INTERVAL)
def load_hourly_data(symbol: str) -> pd.DataFrame:
    """Load hourly data for the past year.

    Args:
        symbol (str): The ticker symbol to load data for.

    Returns:
        pd.DataFrame: A dataframe with hourly data, or an empty dataframe on error.
    """
    end = datetime.utcnow()
    start = end - timedelta(days=365)
    try:
        df = yf.download(symbol, start=start, end=end, interval="1h", progress=False, auto_adjust=True)
        df.dropna(inplace=True)
        return df
    except Exception as e:
        st.error(f"Error loading hourly data for {symbol}: {e}")
        return pd.DataFrame()

def fetch_latest_5m(symbol: str) -> pd.DataFrame:
    """Fetch latest 5-minute data for today.

    Args:
        symbol (str): The ticker symbol to load data for.

    Returns:
        pd.DataFrame: A dataframe with 5-minute data, or an empty dataframe on error.
    """
    try:
        df = yf.download(symbol, period="1d", interval="5m", progress=False, auto_adjust=True)
        df.dropna(inplace=True)
        return df
    except Exception as e:
        st.error(f"Error fetching 5m data for {symbol}: {e}")
        return pd.DataFrame()