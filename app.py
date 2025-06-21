import streamlit as st

# ★ 페이지 설정은 최상단에서 단 한 번!
st.set_page_config(
    page_title="주식 뉴스 보드",
    layout="wide",
    page_icon="📰",
)

import nltk
# 이미 있으면 바로 통과, 없으면 다운로드
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)

import pandas as pd
from news_crawler import crawl_google_news
from price_fetcher import fetch_prices
from streamlit_autorefresh import st_autorefresh
from indicators import add_indicators
from alerts import check_alerts, Level
from kakao import send_kakao

# ⬇︎ 5분마다 오토리프레시
st_autorefresh(interval=300_000, key="auto_refresh")

# ⬇︎ 캐싱된 함수들 선언(cached_crawl, ...)

# 1) 뉴스 크롤링·주가 데이터는 '데이터' 캐시
@st.cache_data(ttl=3600)
def cached_crawl(keyword):
    return crawl_google_news(keyword, max_items=3)

@st.cache_data(ttl=30*60)          # 30분 유지
def cached_price(ticker:str):
    return fetch_prices(ticker, period="3mo")

#################################################################
# 1) M7 매핑 테이블 추가
#################################################################
MAG7 = {
    "AAPL":  "애플",
    "MSFT":  "마이크로소프트",
    "AMZN":  "아마존",
    "GOOGL": "구글",          # 알파벳(클래스A)
    "META":  "메타",
    "TSLA":  "테슬라",
    "NVDA":  "엔비디아",
}

#################################################################
# 2) 관심 종목 선택 UI 확장
#################################################################
st.sidebar.header("관심 종목 설정")

# "M7 전체" 한 번에 불러오기용 체크박스
use_mag7 = st.sidebar.checkbox("💫 Magnificent 7 전체 보기", value=True)

# 기본 후보 목록
tickers_default = list(MAG7.keys())
# 멀티셀렉트 – M7 선택 여부 따라 기본값 조정
tickers = st.sidebar.multiselect(
    "티커를 선택/추가하세요",
    options=tickers_default + ["005930.KS", "035420.KS"],   # 한국 주식 등 추가 가능
    default=tickers_default if use_mag7 else [],
)

# M7 전용 설명
if use_mag7:
    st.sidebar.caption("M7: AAPL·MSFT·AMZN·GOOGL·META·TSLA·NVDA")

#################################################################
# 사이드바 하단 : 뉴스 요약 영역
#################################################################
st.sidebar.divider()
st.sidebar.subheader("📰 최신 뉴스 (최근 1건)")

max_sidebar_news = 1          # 사이드바에는 종목당 1개만
for t in tickers:
    keyword = MAG7.get(t, t.split('.')[0])
    news_df = cached_crawl(keyword).head(max_sidebar_news)
    if news_df.empty:
        continue

    # 기사 1건씩 링크 표시
    row = news_df.iloc[0]
    with st.sidebar.expander(f"{keyword}"):
        st.sidebar.markdown(f"[{row['title']}]({row['url']})")

#################################################################
# 1) 오늘의 뉴스
#################################################################
st.header("📰 오늘의 뉴스")

for t in tickers:
    keyword = MAG7.get(t, t.split('.')[0])
    news_df = cached_crawl(keyword).head(3)

    # ─ 디버그 ─
    st.write("DEBUG:", keyword, len(news_df))

    if news_df.empty:
        continue

    st.subheader(f"🔖 {keyword}")

    for _, row in news_df.iterrows():
        st.markdown(f"**{row['title']}**  \n[{row['url']}]({row['url']})")
        st.markdown("---")

# 3) 주가 시세
st.header("📈 주가 차트 & 지표")
for t in tickers:
    price_df = cached_price(t)
    indic_df = add_indicators(price_df)

    st.subheader(f"📊 {t} 종가 · RSI · 거래량")
    st.line_chart(indic_df.set_index("Date")["Close"], height=180)
    st.line_chart(indic_df.set_index("Date")["RSI"], height=120)
    st.bar_chart(indic_df.set_index("Date")["Volume"], height=120)

    # 알림 체크
    alerts = check_alerts(indic_df)
    if alerts:
        msg_join = " · ".join([m for m, _ in alerts])
        st.error(msg_join)
    else:
        st.success("특이사항 없음 ✅")

    st.caption(f"기간: {indic_df['Date'].min().date()} ~ {indic_df['Date'].max().date()}")

    # 화면 출력
    for msg, lvl in alerts:
        if lvl == Level.CRIT:
            st.error(msg)
        elif lvl == Level.WARN:
            st.warning(msg)
        else:
            st.info(msg)

    # 카카오톡 푸시 (Lv1 이상만)
    crit_msgs = [m for m,l in alerts if l == Level.CRIT]
    if crit_msgs:
        send_kakao(f"{t}: " + " | ".join(crit_msgs)) 