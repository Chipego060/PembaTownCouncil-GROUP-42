#!/usr/bin/env python3
"""
Phase 1: Crawl pembacouncil.gov.zm to inventory all pages, PDFs, and data sources.
Group 42 — Pemba Town Council — CSC 4792 Mini Project
"""

import requests
import warnings
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import json
import re

warnings.filterwarnings("ignore")

BASE_URL = "https://www.pembacouncil.gov.zm"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

def fetch_page(url):
    """Fetch a page and return BeautifulSoup object."""
    try:
        resp = requests.get(url, headers=HEADERS, verify=False, timeout=15)
        resp.encoding = resp.apparent_encoding or "utf-8"
        print(f"  [OK] {url} ({resp.status_code}, {len(resp.content)} bytes)")
        return BeautifulSoup(resp.text, "lxml")
    except Exception as e:
        print(f"  [FAIL] {url} — {e}")
        return None

def find_all_links(soup, base_url):
    """Extract all internal links from a page."""
    links = set()
    if not soup:
        return links
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        full = urljoin(base_url, href)
        parsed = urlparse(full)
        # Keep only same-domain links
        if parsed.netloc == urlparse(base_url).netloc:
            links.add(full.split("#")[0].split("?")[0])
    return links

def find_pdfs(soup, base_url):
    """Extract all PDF links from a page."""
    pdfs = set()
    if not soup:
        return pdfs
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        full = urljoin(base_url, href)
        if full.lower().endswith(".pdf"):
            label = a_tag.get_text(strip=True) or "[no label]"
            pdfs.add((full, label))
    return pdfs

def find_downloads(soup, base_url):
    """Extract download links (PDFs, documents, etc.)."""
    downloads = set()
    if not soup:
        return downloads
    extensions = (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".zip")
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        full = urljoin(base_url, href)
        if any(full.lower().endswith(ext) for ext in extensions):
            label = a_tag.get_text(strip=True) or "[no label]"
            downloads.add((full, label))
    return downloads

def extract_page_content(soup):
    """Extract main text content from a page."""
    if not soup:
        return ""
    # Try to find main content area
    main = soup.find("main") or soup.find("article") or soup.find("div", class_=re.compile("content|entry|post"))
    if not main:
        main = soup.find("body")
    if main:
        return main.get_text(separator="\n", strip=True)[:2000]
    return ""

def extract_news_posts(soup, base_url):
    """Extract news post entries from a page."""
    posts = []
    if not soup:
        return posts
    # Look for article/post entries
    for article in soup.find_all(["article", "div"], class_=re.compile("post|entry|news|item")):
        title_tag = article.find(["h1", "h2", "h3", "h4", "a"])
        title = title_tag.get_text(strip=True) if title_tag else "Untitled"
        
        date_tag = article.find(["time", "span", "div"], class_=re.compile("date|time|meta"))
        date = date_tag.get_text(strip=True) if date_tag else ""
        
        link = ""
        if title_tag and title_tag.name == "a":
            link = urljoin(base_url, title_tag.get("href", ""))
        elif title_tag:
            parent_a = title_tag.find_parent("a")
            if parent_a:
                link = urljoin(base_url, parent_a.get("href", ""))
        
        content = article.get_text(separator=" ", strip=True)[:500]
        posts.append({"title": title, "date": date, "link": link, "content": content})
    return posts

def extract_civic_leaders(soup):
    """Extract civic leader information."""
    leaders = []
    if not soup:
        return leaders
    for item in soup.find_all(["div", "li", "tr", "td"]):
        text = item.get_text(separator=" ", strip=True)
        # Look for titles/designations
        if any(title in text.lower() for title in ["mayor", "councilor", "chairperson", "secretary", "director"]):
            if len(text) < 300:
                leaders.append(text)
    return leaders

def main():
    print("=" * 70)
    print("PEMBA TOWN COUNCIL — WEBSITE CRAWLER")
    print("=" * 70)
    
    all_pdfs = set()
    all_downloads = set()
    all_pages = {}
    news_posts = []
    civic_leaders = []
    
    # Known pages to crawl
    known_pages = {
        "home": BASE_URL,
        "publications": f"{BASE_URL}/?page_id=195",
        "news_updates": f"{BASE_URL}/?page_id=793",
        "civic_leaders": f"{BASE_URL}/?page_id=1945",
        "zdsp": f"{BASE_URL}/?page_id=2709",
    }
    
    # Step 1: Fetch known pages
    print("\n[STEP 1] Fetching known pages...")
    for name, url in known_pages.items():
        print(f"\n  --- {name.upper()} ---")
        soup = fetch_page(url)
        if soup:
            all_pages[name] = {
                "url": url,
                "title": soup.title.string if soup.title else name,
                "text_preview": extract_page_content(soup)[:500]
            }
            
            # Find PDFs and downloads
            page_pdfs = find_pdfs(soup, url)
            page_downloads = find_downloads(soup, url)
            all_pdfs.update(page_pdfs)
            all_downloads.update(page_downloads)
            
            # Extract specific content
            if name == "news_updates":
                news_posts = extract_news_posts(soup, url)
            elif name == "civic_leaders":
                civic_leaders = extract_civic_leaders(soup)
            
            # Find internal links for further crawling
            links = find_all_links(soup, url)
            print(f"  Found {len(links)} internal links, {len(page_pdfs)} PDFs, {len(page_downloads)} downloads")
    
    # Step 2: Discover additional pages from homepage links
    print("\n[STEP 2] Discovering additional pages...")
    discovered = set()
    soup = fetch_page(BASE_URL)
    if soup:
        links = find_all_links(soup, BASE_URL)
        known_urls = set(known_pages.values())
        for link in links:
            if link not in known_urls and link not in discovered:
                discovered.add(link)
    
    print(f"  Found {len(discovered)} new pages to check")
    
    # Check a sample of discovered pages
    for i, link in enumerate(list(discovered)[:15]):
        print(f"\n  --- Checking page {i+1}/{min(15, len(discovered))} ---")
        soup = fetch_page(link)
        if soup:
            page_pdfs = find_pdfs(soup, link)
            page_downloads = find_downloads(soup, link)
            all_pdfs.update(page_pdfs)
            all_downloads.update(page_downloads)
    
    # Step 3: Try to find more PDFs by searching common WordPress paths
    print("\n[STEP 3] Searching for additional documents...")
    search_urls = [
        f"{BASE_URL}/wp-content/uploads/",
        f"{BASE_URL}/wp-content/uploads/2024/",
        f"{BASE_URL}/wp-content/uploads/2025/",
        f"{BASE_URL}/wp-content/uploads/2026/",
    ]
    for url in search_urls:
        soup = fetch_page(url)
        if soup:
            page_pdfs = find_pdfs(soup, url)
            all_pdfs.update(page_pdfs)
    
    # Step 4: Compile results
    print("\n" + "=" * 70)
    print("CRAWL RESULTS SUMMARY")
    print("=" * 70)
    
    print(f"\nPages crawled: {len(known_pages) + len(discovered)}")
    print(f"PDFs found: {len(all_pdfs)}")
    print(f"Downloads found: {len(all_downloads)}")
    print(f"News posts: {len(news_posts)}")
    print(f"Civic leaders found: {len(civic_leaders)}")
    
    print("\n--- PDF Documents ---")
    for pdf_url, label in sorted(all_pdfs):
        print(f"  [{label}] {pdf_url}")
    
    print("\n--- News Posts ---")
    for post in news_posts[:20]:
        print(f"  [{post['date']}] {post['title']}")
        if post['link']:
            print(f"    URL: {post['link']}")
    
    print("\n--- Civic Leaders ---")
    for leader in civic_leaders[:10]:
        print(f"  {leader}")
    
    print("\n--- Page Content Previews ---")
    for name, info in all_pages.items():
        print(f"\n  [{name.upper()}] {info['title']}")
        preview = info['text_preview'][:200].replace('\n', ' ')
        print(f"    {preview}...")
    
    # Save results to JSON
    results = {
        "base_url": BASE_URL,
        "pages": all_pages,
        "pdfs": [{"url": u, "label": l} for u, l in sorted(all_pdfs)],
        "downloads": [{"url": u, "label": l} for u, l in sorted(all_downloads)],
        "news_posts": news_posts,
        "civic_leaders": civic_leaders,
        "discovered_urls": list(discovered)[:30]
    }
    
    with open("crawl_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\nResults saved to crawl_results.json")

if __name__ == "__main__":
    main()
