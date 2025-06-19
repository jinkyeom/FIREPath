import datetime, requests, re, pandas as pd, feedparser, base64, urllib.parse as ul
from bs4 import BeautifulSoup
from newspaper import Article
import trafilatura
from readability import Document
import lxml.html
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

# ──────────────────
# 1) 네이버 검색 뉴스 크롤링
# ──────────────────
def crawl_naver(keyword: str, pages: int = 1) -> pd.DataFrame:
    """
    네이버 통합검색(뉴스) 결과에서 제목·URL만 수집
    • keyword : 검색어(종목명, 키워드)
    • pages   : 1페이지=10건, 2페이지=20건 …
    """
    base = "https://search.naver.com/search.naver"
    rows = []
    for p in range(1, pages + 1):
        params = {"where": "news", "query": keyword, "start": (p - 1) * 10 + 1}
        html = requests.get(
            base,
            params=params,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        ).text
        # 제목·URL 태그 파싱
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup.select("a.news_tit"):
            rows.append(
                {
                    "keyword": keyword,
                    "title": tag["title"],
                    "url": tag["href"],
                    "date": datetime.date.today(),
                }
            )
    return pd.DataFrame(rows)


# ──────────────────
# 2) 기사 본문 추출
# ──────────────────
def get_article_text(url: str) -> str:
    """trafilatura → readability → newspaper 순 본문 추출"""
    try:
        txt = trafilatura.extract(trafilatura.fetch_url(url), include_comments=False)
        if txt and len(txt) > 120:
            return txt
    except Exception:
        pass
    try:
        html = requests.get(url, timeout=8).text
        clean = lxml.html.fromstring(Document(html).summary()).text_content()
        if len(clean) > 120:
            return clean
    except Exception:
        pass
    try:
        art = Article(url); art.download(); art.parse()
        return art.text
    except Exception:
        return ""

# ───────── Google News RSS 크롤러 ─────────
def _resolve_google_url(url: str) -> str:
    """Google News 중계 URL → 실제 언론사 URL(자바스크립트 리다이렉트 포함)"""
    if "news.google.com" not in url:
        return url
    try:
        _driver.get(url)
        return _driver.current_url          # JS 실행 후 최종 주소
    except Exception:
        return url

def crawl_google_news(keyword: str, max_items: int = 3) -> pd.DataFrame:
    rss = f"https://news.google.com/rss/search?q={ul.quote(keyword)}&hl=ko&gl=KR&ceid=KR:ko"
    feed = feedparser.parse(rss)
    rows = []
    for e in feed.entries[:max_items]:
        real = google_to_origin(e.link)         # ← 새 함수 사용
        rows.append({"keyword":keyword, "title":e.title, "url":real})
    return pd.DataFrame(rows)

# ───────── 기존 네이버 크롤러(crawl_naver) 그대로 두어 백업으로 사용 ─────────

NEWS_API_KEY = "YOUR_KEY"
def crawl_newsapi(keyword, page_size=5):
    url = ("https://newsapi.org/v2/everything?"
           f"q={keyword}&sortBy=publishedAt&pageSize={page_size}&language=ko&apiKey={NEWS_API_KEY}")
    data = requests.get(url, timeout=10).json()
    rows = [{
        "keyword": keyword,
        "title"  : a["title"],
        "url"    : a["url"],
        "date"   : datetime.datetime.fromisoformat(a["publishedAt"][:19]).date()
    } for a in data.get("articles", [])]
    return pd.DataFrame(rows)

# 1) Selenium 헤드리스 브라우저 1회 초기화
_opts = Options()
_opts.add_argument("--headless=new")
_driver = webdriver.Chrome(
    service=Service(ChromeDriverManager().install()),
    options=_opts,
)

UA = {"User-Agent": "Mozilla/5.0"}

def google_to_origin(url: str) -> str:
    """news.google.com (RSS·/articles) 링크 → 실제 언론사 URL"""

    if "news.google.com" not in url:
        return url

    # 1) ?url= 파라미터로 바로 들어있는 경우
    q = ul.urlparse(url).query
    if "url=" in q:
        return ul.parse_qs(q)["url"][0]

    # 2) /articles/CBMi…  ← Base64 URLSAFE 안에 http(s)://가 들어있음
    m = re.search(r"/articles/([A-Za-z0-9_\-]+)", url)
    if m:
        seg = m.group(1) + "=" * (-len(m.group(1)) % 4)   # 패딩
        try:
            plain = base64.urlsafe_b64decode(seg).decode("utf-8", "ignore")
            hit   = re.search(r"https?://[^&\s]+", plain)
            if hit:
                return hit.group(0)
        except Exception:
            pass

    # 3) HTML 열어서 meta refresh·<a> href 추출
    try:
        html = requests.get(url, headers=UA, timeout=8, allow_redirects=True)
        if html.history and "news.google.com" not in html.url:
            return html.url                     # 30x 리다이렉트 성공

        soup = BeautifulSoup(html.text, "html.parser")
        # 3-A meta refresh
        meta = soup.find("meta", attrs={"http-equiv": "refresh"})
        if meta and "url=" in meta["content"]:
            return meta["content"].split("url=")[1]

        # 3-B 첫 번째 외부 링크
        a = soup.find("a", href=re.compile(r"^https?://"))
        if a:
            return a["href"]
    except Exception:
        pass

    return url   # 전부 실패하면 원본 그대로

def google_articles_to_origin(url: str) -> str:
    """
    https://news.google.com/rss/articles/CBMi… → 원본 기사 URL
    ① ?url= 파라미터가 있으면 그대로 사용
    ② /articles/ 뒷부분(Base64-URLSAFE) 디코드
    ③ 실패 시 meta og:url·canonical 태그 파싱
    """
    if "news.google.com" not in url:
        return url

    # 1) ?url= 파라미터
    qs = ul.urlparse(url).query
    if "url=" in qs:
        return ul.parse_qs(qs)["url"][0]

    # 2) /articles/CBMi… 디코드
    m = re.search(r"/articles/([A-Za-z0-9_\-]+)", url)
    if m:
        seg = m.group(1)
        seg += "=" * (-len(seg) % 4)              # 패딩 보정
        try:
            decoded = base64.urlsafe_b64decode(seg).decode("utf-8", "ignore")
            hit = re.search(r"https?://[^&\s]+", decoded)
            if hit:
                return hit.group(0)
        except Exception:
            pass

    # 3) 마지막 – 실제 페이지 요청 후 meta 태그 파싱
    try:
        html = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=8).text
        for pattern in [r'<meta property="og:url" content="([^"]+)"',
                        r'<link rel="canonical" href="([^"]+)"']:
            mo = re.search(pattern, html)
            if mo:
                return mo.group(1)
    except Exception:
        pass
    return url   # 모든 방법 실패 시 원본 그대로
