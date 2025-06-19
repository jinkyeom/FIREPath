import streamlit as st

# ★ 페이지 설정은 최상단에서 단 한 번!
st.set_page_config(
    page_title="주식 뉴스 요약 보드",
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
from news_crawler import crawl_google_news, get_article_text
from summarizer import summarize
from price_fetcher import fetch_prices
from streamlit_autorefresh import st_autorefresh

# ⬇︎ 5분마다 오토리프레시
st_autorefresh(interval=300_000, key="auto_refresh")

# ⬇︎ 캐싱된 함수들 선언(load_summarizer, cached_crawl, ...)

# 1) 무거운 모델은 '자원' 캐시
@st.cache_resource
def load_summarizer():
    from transformers import BartForConditionalGeneration, PreTrainedTokenizerFast
    model_name = "digit82/kobart-summarization"
    tok  = PreTrainedTokenizerFast.from_pretrained(model_name)
    bart = BartForConditionalGeneration.from_pretrained(model_name)
    return tok, bart

tokenizer, model = load_summarizer()

def summarize_cached(text:str, max_len=1024, summary_len=128) -> str:
    """요약 전용 래퍼 ‒ 모델·토크나이저는 이미 캐싱됨"""
    # 데이터 결과만 캐싱
    @st.cache_data(ttl=24*60*60)   # 24시간 유지
    def _summ(text):
        ids = tokenizer.encode(text, max_length=max_len,
                               truncation=True, return_tensors="pt")
        out = model.generate(ids, max_length=summary_len,
                             num_beams=4, early_stopping=True)
        return tokenizer.decode(out[0], skip_special_tokens=True)
    return _summ(text)

# 2) 뉴스 크롤링·본문 추출·주가도 전부 '데이터' 캐시
@st.cache_data(ttl=3600)
def cached_crawl(keyword):
    return crawl_google_news(keyword, max_items=3)

@st.cache_data(ttl=24*60*60)       # 24시간 유지
def cached_article(url:str):
    return get_article_text(url)   # newspaper3k 사용

@st.cache_data(ttl=30*60)          # 30분 유지
def cached_price(ticker:str):
    return fetch_prices(ticker, period="3mo")

@st.cache_data(ttl=24*60*60)       # 24시간 유지
def cached_summary(text:str) -> str:
    return summarize(text)

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
st.sidebar.subheader("📰 요약 뉴스 (최근 1건)")

max_sidebar_news = 1          # 사이드바에는 종목당 1개만
for t in tickers:
    keyword = MAG7.get(t, t.split('.')[0])
    news_df = cached_crawl(keyword).head(max_sidebar_news)
    if news_df.empty:
        continue

    # 기사 1건씩 요약
    row = news_df.iloc[0]
    with st.sidebar.expander(f"{keyword} · {row['title'][:25]}..."):
        st.sidebar.write(row["url"])

        # 요약은 캐싱되어 있으면 즉시, 없으면 1-2초
        try:
            full = cached_article(row["url"])
            if cached_summary(full):    # 이미 캐시된 경우
                st.sidebar.write(cached_summary(full))
            else:
                with st.spinner("요약 생성 중..."):
                    summ = cached_summary(full)
                    st.sidebar.write(summ)
        except Exception as e:
            summ = f"요약 오류: {e}"
            st.sidebar.write(summ)

        # ② 디버그: 요약 결과 원문 그대로 출력
        st.text("요약 DEBUG → " + repr(summ)[:150])

#################################################################
# 1) 오늘의 뉴스 · 요약  (메인 화면 오른쪽)
#################################################################
st.header("📰 오늘의 뉴스 · 요약")

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

        full_text = cached_article(row["url"])
        st.caption(f"본문 길이: {len(full_text)}")      # 디버그

        if not full_text:
            st.warning("🔗 본문 파싱 실패 – 원문 링크로 이동해 주세요.")
        else:
            st.write(cached_summary(full_text))

        st.markdown("---")

# 3) 주가 시세
st.header("📈 주가 차트")
for t in tickers:
    st.subheader(f"📊 {t} 종가 추이")
    price_df = cached_price(t)
    st.line_chart(price_df.set_index("Date")["Close"], height=180)
    st.caption(f"기간: {price_df['Date'].min().date()} ~ {price_df['Date'].max().date()}") 