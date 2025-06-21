import pandas as pd
import pandas_ta as ta


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add RSI(14), MACD, and 20-day volume MA columns to given OHLCV DataFrame."""
    data = df.copy()

    # RSI
    data["RSI"] = ta.rsi(data["Close"], length=14)

    # MACD (fast 12, slow 26, signal 9)
    macd = ta.macd(data["Close"], fast=12, slow=26, signal=9)
    data = pd.concat([data, macd], axis=1)

    # Bollinger Bands (20, 2.0)
    bb = ta.bbands(data["Close"], length=20, std=2.0)
    data = pd.concat([data, bb], axis=1)

    # Stochastic Oscillator (14,3,3)
    stoch = ta.stoch(data["High"], data["Low"], data["Close"], k=14, d=3)
    data = pd.concat([data, stoch], axis=1)

    # 20-day volume moving average
    if "Volume" in data.columns:
        data["VOL_MA20"] = data["Volume"].rolling(20).mean()

    return data
