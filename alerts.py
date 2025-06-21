from enum import IntEnum, auto

class Level(IntEnum):
    INFO = 3
    WARN = 2
    CRIT = 1          # 숫자가 낮을수록 높은 등급

def check_alerts(df):
    """Return list of alert messages based on latest row of indicator DataFrame."""
    alerts = []
    if df.empty:
        return alerts

    last = df.iloc[-1]

    # RSI
    if last["RSI"] > 80:
        alerts.append(("RSI 과매수", Level.CRIT))
    elif last["RSI"] > 70:
        alerts.append(("RSI 주의", Level.WARN))
    elif last["RSI"] < 20:
        alerts.append(("RSI 과매도", Level.CRIT))

    # MACD crossover (need previous row)
    if len(df) >= 2 and {c in df.columns for c in ["MACD_12_26_9", "MACDs_12_26_9"]}:
        prev = df.iloc[-2]
        if (last["MACD_12_26_9"] > last["MACDs_12_26_9"] and
                prev["MACD_12_26_9"] <= prev["MACDs_12_26_9"]):
            alerts.append(("MACD 골든크로스", Level.WARN))
        elif (last["MACD_12_26_9"] < last["MACDs_12_26_9"] and
                  prev["MACD_12_26_9"] >= prev["MACDs_12_26_9"]):
            alerts.append(("MACD 데드크로스", Level.WARN))

    # Volume spike
    if "Volume" in df.columns and "VOL_MA20" in df.columns:
        if last["Volume"] > last["VOL_MA20"] * 2:
            alerts.append(("거래량 급증", Level.INFO))

    return alerts 