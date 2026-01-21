import json
import os
import re
from datetime import datetime

# Sumy Imports
try:
    import nltk
    from sumy.parsers.plaintext import PlaintextParser
    from sumy.nlp.tokenizers import Tokenizer
    from sumy.summarizers.lex_rank import LexRankSummarizer
    SUMY_AVAILABLE = True
    
    # Ensure NLTK data is present (silent download)
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        nltk.download('punkt', quiet=True)
        # nltk.download('punkt_tab', quiet=True) # Newer NLTK might need this
except ImportError:
    SUMY_AVAILABLE = False
    print("⚠️ Sumy not found. Falling back to simple truncation.")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
INPUT_FILE = os.path.join(DATA_DIR, 'latest_news.json')
OUTPUT_JSON = os.path.join(DATA_DIR, 'ai_clean.json')
OUTPUT_MD = os.path.join(DATA_DIR, 'ai_digest.md')

# Common Tickers to Scan (Simplified for now, can be expanded or loaded entirely)
WATCHLIST = {"AAPL", "MSFT", "GOOG", "GOOGL", "AMZN", "NVDA", "TSLA", "META", "AMD", "INTC", "SPY", "QQQ", "IWM", "VIX"}

def clean_text(text):
    if not text:
        return ""
    # Remove HTML entities and tags
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&quot;', '"')
    # Remove common RSS boilerplate
    text = re.sub(r'Read more...', '', text)
    text = re.sub(r'Continue reading', '', text)
    return " ".join(text.split())

def extract_tickers(text):
    """Simple heuristic to find tickers in text"""
    found = set()
    # Check for $TICKER format
    matches = re.findall(r'\$([A-Z]{2,5})', text)
    found.update(matches)
    
    # Check for known watchlist words (Case sensitive, whole word)
    words = set(re.findall(r'\b[A-Z]{2,5}\b', text))
    found.update(words.intersection(WATCHLIST))
    
    return list(found)

def summarize_with_sumy(text, sentences_count=2):
    if not SUMY_AVAILABLE or len(text) < 200:
        return text
        
    try:
        parser = PlaintextParser.from_string(text, Tokenizer("english"))
        summarizer = LexRankSummarizer()
        summary = summarizer(parser.document, sentences_count)
        return " ".join([str(sentence) for sentence in summary])
    except Exception as e:
        # Fallback if Sumy fails (e.g. text too short or weird chars)
        return text

def main():
    print(f"Reading from {INPUT_FILE}...")
    
    if not os.path.exists(INPUT_FILE):
        print("No input file found. Run main.py first.")
        return

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        raw = json.load(f)
        
    items = raw.get("data", [])
    print(f"Processing {len(items)} raw items...")
    
    cleaned_items = []
    
    for item in items:
        # 1. Clean Text
        title = clean_text(item.get("title", ""))
        summary = clean_text(item.get("summary", ""))
        
        # 2. Filter Low Quality (Too short)
        full_text = f"{title} {summary}"
        if len(full_text) < 20: 
            continue
            
        # 3. Enhance Data
        tickers = extract_tickers(full_text)
        
        # 4. Generate High Quality Summary
        # Use title + summary as source for sumy to pick best sentences from
        if SUMY_AVAILABLE and len(summary) > 150:
            smart_summary = summarize_with_sumy(summary, 2)
        else:
            smart_summary = summary

        cleaned_items.append({
            "title": title,
            "summary": smart_summary,
            "source": item.get("source"),
            "published": item.get("published"),
            "link": item.get("link"),
            "tickers": tickers,
            "text_len": len(full_text)
        })
    
    # 4. Generate JSON Output
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(cleaned_items, f, indent=2, ensure_ascii=False)
        
    # 5. Generate Markdown Digest (Token Efficient for AI)
    # Format:
    # ## Source
    # - [Ticker] Title (Summary)
    
    md_lines = [f"# Market News Digest ({datetime.now().strftime('%Y-%m-%d')})", ""]
    
    # Group by Source for readability
    by_source = {}
    for item in cleaned_items:
        s = item['source']
        if s not in by_source: by_source[s] = []
        by_source[s].append(item)
        
    for source, news_list in by_source.items():
        md_lines.append(f"## {source}")
        for news in news_list[:10]: # Limit to top 10 per source
            ticker_str = f" **[{', '.join(news['tickers'])}]**" if news['tickers'] else ""
            
            # Use the smart summary directly, possibly truncating if STILL too long
            final_summary = news['summary']
            if len(final_summary) > 300: # Safety truncation even after Sumy
                 final_summary = final_summary[:297] + "..."
                
            md_lines.append(f"-{ticker_str} {news['title']}")
            if final_summary and final_summary != news['title']:
                md_lines.append(f"  > {final_summary}")
        md_lines.append("")
        
    with open(OUTPUT_MD, 'w', encoding='utf-8') as f:
        f.write("\n".join(md_lines))
        
    print(f"✅ Cleaning Complete.")
    print(f"JSON: {OUTPUT_JSON} ({len(cleaned_items)} items)")
    print(f"Markdown Digest: {OUTPUT_MD} (Sumy Optimized)")

