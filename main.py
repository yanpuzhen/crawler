import feedparser
import json
import os
import time
import requests
import re
from datetime import datetime
import pytz
from bs4 import BeautifulSoup

# Setup Directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# Enhanced RSS Feeds Configuration
FEEDS = {
    # Market News
    "CNBC_Top": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
    "CNBC_Politics": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000113",
    "CNBC_Tech": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=19854910",
    "Investing_News": "https://www.investing.com/rss/news.rss",
    "Investing_Stock": "https://www.investing.com/rss/stock_Market.rss",
    "MarketWatch_Top": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
    "WSJ_Markets": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
    "WSJ_Tech": "https://feeds.a.dj.com/rss/RSSWSJD.xml",
    
    # Macro / Econ
    "NYT_Economy": "https://rss.nytimes.com/services/xml/rss/nyt/Economy.xml",
    "Yahoo_Top": "https://finance.yahoo.com/news/rssindex",
}

def clean_html(html_content):
    if not html_content:
        return ""
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        return soup.get_text(separator=" ").strip()
    except:
        return html_content

def fetch_rss(feed_name, url):
    print(f"Fetching {feed_name}...")
    try:
        # Set User-Agent to avoid some basic blocking
        feedparser.USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko)"
        
        feed = feedparser.parse(url)
        entries = []
        
        # Parse top 20 items per feed
        for entry in feed.entries[:20]: 
            published = entry.get("published", entry.get("updated", datetime.now().isoformat()))
            summary_raw = entry.get("summary", entry.get("description", ""))
            
            # Basic Deduplication signature: Title
            entries.append({
                "source": feed_name,
                "title": entry.title,
                "link": entry.link,
                "published": published,
                "summary": clean_html(summary_raw),
                "guid": entry.get("id", entry.link),
                "crawled_at": datetime.now().isoformat()
            })
        return entries
    except Exception as e:
        print(f"Error fetching {feed_name}: {e}")
        return []


# Social Media Endpoints
URL_STOCKTWITS_TRENDING = "https://api.stocktwits.com/api/2/trending/symbols.json"
URL_REDDIT_WSB = "https://www.reddit.com/r/wallstreetbets/hot.json?limit=10"

def fetch_stocktwits():
    print("Fetching Stocktwits Trending...")
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
        }
        resp = requests.get(URL_STOCKTWITS_TRENDING, headers=headers, timeout=10)
        data = resp.json()
        
        items = []
        if 'symbols' in data:
            for s in data['symbols']:
                items.append({
                    "source": "Stocktwits_Trending",
                    "title": f"${s['symbol']} Trending on Stocktwits",
                    "link": f"https://stocktwits.com/symbol/{s['symbol']}",
                    "published": datetime.now().isoformat(),
                    "summary": s.get('title', '') + f" (Watchers: {s.get('watchlist_count', 0)})",
                    "guid": f"stocktwits_{s['symbol']}_{datetime.now().strftime('%Y%m%d')}",
                    "crawled_at": datetime.now().isoformat()
                })
        return items
    except Exception as e:
        print(f"Error fetching Stocktwits: {e}")
        return []

def fetch_reddit(subreddit="wallstreetbets"):
    print(f"Fetching Reddit r/{subreddit}...")
    try:
        url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit=10"
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) PythonBot/0.1"
        }
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            print(f"Reddit Status {resp.status_code}")
            return []
            
        data = resp.json()
        items = []
        
        children = data.get('data', {}).get('children', [])
        for post in children:
            p = post['data']
            if p.get('stickied'): continue # Skip sticky posts
            
            items.append({
                "source": f"Reddit_r/{subreddit}",
                "title": p.get('title'),
                "link": f"https://reddit.com{p.get('permalink')}",
                "published": datetime.fromtimestamp(p.get('created_utc', time.time())).isoformat(),
                "summary": p.get('selftext', '')[:200], # First 200 chars
                "guid": p.get('id'),
                "crawled_at": datetime.now().isoformat()
            })
        return items
    except Exception as e:
        print(f"Error fetching Reddit: {e}")
        return []

def main():
    print("Starting Deep Crawler Job...")
    start_time = time.time()
    
    all_news = []
    seen_titles = set()
    
    # 1. RSS Feeds
    for name, url in FEEDS.items():
        news_items = fetch_rss(name, url)
        # Deduplicate
        for item in news_items:
            clean_title = re.sub(r'\\W+', '', item['title'].lower())
            if clean_title in seen_titles: continue
            seen_titles.add(clean_title)
            all_news.append(item)
        print(f"Fetched {len(news_items)} items from {name}")

    # 2. Google News Watchlist (Double Insurance)
    # Target major movers and ETFs to ensure "Search" coverage
    WATCHLIST = ["SPY", "QQQ", "NVDA", "TSLA", "AAPL", "MSFT", "AMD", "META", "AMZN", "GOOGL", "BTC", "ETH"]
    print("Fetching Google News for Watchlist...")
    
    for symbol in WATCHLIST:
        try:
            # Google News RSS Search
            g_url = f"https://news.google.com/rss/search?q={symbol}+stock+news+when:1d&hl=en-US&gl=US&ceid=US:en"
            # Use fetch_rss helper but label source
            g_items = fetch_rss(f"GoogleNews_{symbol}", g_url)
            
            count = 0
            for item in g_items:
                # Deduplicate
                clean_title = re.sub(r'\\W+', '', item['title'].lower())
                if clean_title in seen_titles: continue
                seen_titles.add(clean_title)
                all_news.append(item)
                count += 1
            # print(f"  + {symbol}: {count} new items")
        except Exception as e:
            print(f"Error fetching Google News for {symbol}: {e}")

    # 3. Social Media
    st_items = fetch_stocktwits()
    all_news.extend(st_items)
    print(f"Fetched {len(st_items)} items from Stocktwits")
    
    reddit_items = fetch_reddit("wallstreetbets")
    all_news.extend(reddit_items)
    print(f"Fetched {len(reddit_items)} items from Reddit")
    
    reddit_stocks = fetch_reddit("stocks")
    all_news.extend(reddit_stocks)
    print(f"Fetched {len(reddit_stocks)} items from Reddit Stocks")
    
    trading_items = fetch_reddit("trading") # Added for TradingView-like general discussions
    all_news.extend(trading_items)
    print(f"Fetched {len(trading_items)} items from Reddit Trading")

    # Save Daily Digest
    timestamp = datetime.now(pytz.utc).strftime("%Y-%m-%d")
    output_file = os.path.join(DATA_DIR, f"news_{timestamp}.json")
    
    # Also update 'latest.json' for the app
    latest_file = os.path.join(DATA_DIR, "latest_news.json")
    
    # Add metadata
    final_data = {
        "updated_at": datetime.now().isoformat(),
        "total_items": len(all_news),
        "sources": list(FEEDS.keys()),
        "data": all_news
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, indent=2, ensure_ascii=False)
        
    with open(latest_file, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, indent=2, ensure_ascii=False)
        
    data_size_kb = os.path.getsize(latest_file) / 1024
    elapsed = time.time() - start_time
    print(f"✅ Job Complete in {elapsed:.2f}s.")
    print(f"Saved {len(all_news)} unique items to {latest_file} ({data_size_kb:.2f} KB)")

if __name__ == "__main__":
    main()
