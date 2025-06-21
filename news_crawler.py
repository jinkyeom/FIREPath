import datetime, requests, re, pandas as pd, feedparser, base64, urllib.parse as ul
from bs4 import BeautifulSoup
from newspaper import Article
import trafilatura
from readability import Document
import lxml.html

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
    # trafilatura → newspaper3k 백업
    try:
        txt = trafilatura.extract(trafilatura.fetch_url(url), include_comments=False)
        if txt and len(txt) > 120:
            return txt
    except Exception:
        pass
    try:
        art = Article(url, language="ko"); art.download(); art.parse()
        return art.text
    except Exception:
        return ""

# ───────── Google News RSS 크롤러 ─────────
UA = {"User-Agent": "Mozilla/5.0"}

def google_to_origin(url: str) -> str:
    if "news.google.com" not in url:
        return url

    # 1) ?url= 파라미터
    q = ul.urlparse(url).query
    if "url=" in q:
        return ul.parse_qs(q)["url"][0]

    # 2) /articles/…  Base64 URLSAFE 디코드 (더 다양한 패턴 지원)
    m = re.search(r"/articles/([^?]+)", url)
    if m:
        token = m.group(1)

        # 일부 토큰은 'CB...' 'CA...' 접두사가 붙어 있어 디코딩이 실패할 수 있으므로
        # 여러 위치를 시도하며 첫 http 링크가 나오면 반환한다.
        for start in range(0, min(8, len(token))):
            seg = token[start:]
            if not seg:
                continue
            seg_padded = seg + "=" * (-len(seg) % 4)
            try:
                plain = base64.urlsafe_b64decode(seg_padded).decode("utf-8", "ignore")
                hit = re.search(r"https?://[^&\s]+", plain)
                if hit:
                    href = hit.group(0)
                    if href.startswith("http") and "news.google.com" not in href:
                        return href
            except Exception:
                continue

    # 3) 중계 HTML → meta / a[href] 파싱
    try:
        html = requests.get(url, headers=UA, timeout=8).text
        soup = BeautifulSoup(html, "html.parser")
        for tag in [
            soup.find("meta", attrs={"http-equiv": "refresh"}),
            soup.find("meta", property="og:url"),
            soup.find("link", rel="canonical"),
            soup.find("a", href=re.compile(r"^https?://")),
        ]:
            if tag:
                href = (tag.get("content") or tag.get("href") or "")
                if href.startswith("http") and "news.google.com" not in href:
                    return href
    except Exception:
        pass

    # 4) Google internal API decoding (fallback)
    try:
        # gn_id 추출
        gn_match = re.search(r"/articles/([^?]+)", url)
        if gn_match:
            gn_id = gn_match.group(1)

            # Step A: 기사 페이지에서 signature, timestamp 수집
            page = requests.get(f"https://news.google.com/rss/articles/{gn_id}", headers=UA, timeout=8)
            soup = BeautifulSoup(page.text, "lxml")
            div  = soup.select_one("c-wiz > div")
            if div and div.get("data-n-a-sg") and div.get("data-n-a-ts"):
                sg = div["data-n-a-sg"]
                ts = div["data-n-a-ts"]

                # Step B: batchexecute 호출로 원본 URL 디코딩
                req = [
                    "Fbv4je",
                    (
                        "[\"garturlreq\","  # 메서드명\n"
                        "[[\"X\",\"X\",[\"X\",\"X\"],null,null,1,1,\"US:en\",null,1,null,null,null,null,null,0,1],"
                        "\"X\",\"X\",1,[1,1,1],1,1,null,0,0,null,0],"
                        f"\"{gn_id}\",{ts},\"{sg}\"]"
                    )
                ]

                import json, urllib.parse
                payload = "f.req=" + urllib.parse.quote(json.dumps([[req]]))
                resp = requests.post(
                    "https://news.google.com/_/DotsSplashUi/data/batchexecute",
                    headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
                    data=payload,
                    timeout=8,
                )
                if resp.ok and "[" in resp.text:
                    try:
                        body = resp.text.split("\n\n")[1]
                        arr  = json.loads(body)
                        decoded = json.loads(arr[0][2])[1]
                        if decoded.startswith("http") and "news.google.com" not in decoded:
                            return decoded
                    except Exception:
                        pass
    except Exception:
        pass
    return url

def crawl_google_news(keyword: str, max_items: int = 3) -> pd.DataFrame:
    rss = f"https://news.google.com/rss/search?q={ul.quote(keyword)}&hl=ko&gl=KR&ceid=KR:ko"
    feed = feedparser.parse(rss)
    rows = []
    for e in feed.entries[:max_items]:
        rows.append(
            {
                "keyword": keyword,
                "title": e.title,
                "url": google_to_origin(e.link),
                "date": datetime.date.today(),
            }
        )
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
