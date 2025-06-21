import yfinance as yf


def fetch_financials(ticker: str) -> dict:
    """Return ROE, PBR, PER from yfinance info. Values may be None."""
    info = yf.Ticker(ticker).info
    return {
        "ROE": info.get("returnOnEquity"),
        "PBR": info.get("priceToBook"),
        "PER": info.get("trailingPE"),
    } 