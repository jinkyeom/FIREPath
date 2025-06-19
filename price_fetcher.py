import yfinance as yf, pandas as pd

def fetch_prices(ticker:str, period="1mo", interval="1d") -> pd.DataFrame:
    df = yf.Ticker(ticker).history(period=period, interval=interval)
    df.reset_index(inplace=True)
    return df[["Date","Close"]] 