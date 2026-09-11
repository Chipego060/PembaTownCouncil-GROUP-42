#!/usr/bin/env python3
"""
Phase 3: Scrape HTML pages and extract text from text-only PDFs.
Group 42 — Pemba Town Council — CSC 4792 Assignment
"""

import requests
import warnings
import json
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import pdfplumber

warnings.filterwarnings("ignore")

BASE_URL = "https://www.pembacouncil.gov.zm"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

def fetch(url):
    """Fetch a page."""
    try:
        resp = requests.get(url, headers=HEADERS, verify=False, timeout=15)
        resp.encoding = resp.apparent_encoding or "utf-8"
        return BeautifulSoup(resp.text, "lxml")
    except Exception as e:
        print(f"  [FAIL] {url}: {e}")
        return None

def scrape_news_page(url):
    """Scrapes all the news posts from the news updates page."""
    soup = fetch(url)
    if not soup:
        return []
    
    posts = []
    # Find all article/post containers
    for article in soup.find_all(["article", "div"], class_=re.compile("post|entry|item|blog")):
        title = ""
        date = ""
        content = ""
        link = ""
        
        # Title
        title_tag = article.find(["h1", "h2", "h3", "h4", "a"], class_=re.compile("title|entry-title"))
        if not title_tag:
            title_tag = article.find(["h1", "h2", "h3", "h4"])
        if title_tag:
            title = title_tag.get_text(strip=True)
            if title_tag.name == "a":
                link = urljoin(url, title_tag.get("href", ""))
            else:
                a = title_tag.find_parent("a")
                if a:
                    link = urljoin(url, a.get("href", ""))
        
        # Date
        date_tag = article.find(["time", "span", "div"], class_=re.compile("date|time|meta|posted"))
        if date_tag:
            date = date_tag.get_text(strip=True)
        
        # Content
        content_tag = article.find(["div", "p"], class_=re.compile("content|entry|excerpt|summary"))
        if content_tag:
            content = content_tag.get_text(separator=" ", strip=True)[:500]
        
        if title or content:
            posts.append({
                "title": title,
                "date": date,
                "link": link,
                "content": content
            })
    
    # Also look for links in the page
    all_links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True)
        if "?p=" in href and text and len(text) > 10:
            all_links.append({"text": text, "url": urljoin(url, href)})
    
    return posts, all_links

def scrape_individual_post(url):
    """Scrapes content from a single/individual news post."""
    soup = fetch(url)
    if not soup:
        return {}
    
    content = {}
    # Title
    title_tag = soup.find("h1", class_=re.compile("title|entry-title"))
    if title_tag:
        content["title"] = title_tag.get_text(strip=True)
    
    # Date
    date_tag = soup.find(["time", "span"], class_=re.compile("date|time|meta"))
    if date_tag:
        content["date"] = date_tag.get_text(strip=True)
    
    # Body
    body = soup.find(["div", "article"], class_=re.compile("content|entry|post-content"))
    if body:
        content["body"] = body.get_text(separator="\n", strip=True)[:2000]
    
    return content

def scrape_civic_leaders(url):
    """Scrapes civic leaders information."""
    soup = fetch(url)
    if not soup:
        return []
    
    leaders = []
    # Look for leader entries
    for item in soup.find_all(["div", "li", "td", "tr"]):
        text = item.get_text(separator=" ", strip=True)
        if any(kw in text.lower() for kw in ["mayor", "councilor", "councillor", "chairperson", "secretary", "director", "royal highness"]):
            if 20 < len(text) < 500:
                leaders.append(text)
    
    # Deduplicate
    seen = set()
    unique = []
    for l in leaders:
        if l not in seen:
            seen.add(l)
            unique.append(l)
    
    return unique

def extract_text_from_pdf(filepath):
    """Extracts text from a scanned/text-only PDF."""
    try:
        with pdfplumber.open(filepath) as pdf:
            text = ""
            for page in pdf.pages:
                t = page.extract_text() or ""
                text += t + "\n"
            return text
    except Exception as e:
        return f"[ERROR] {e}"

def parse_financial_statements(text):
    """Parses financial statement text into records."""
    records = []
    lines = text.split("\n")
    
    current_section = ""
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Detect sections
        if any(kw in line.upper() for kw in ["INCOME STATEMENT", "BALANCE SHEET", "CASH FLOW", "NOTES", "ASSETS", "LIABILITIES"]):
            current_section = line[:100]
        
        # Look for amounts
        amount_match = re.search(r'([\d,]+(?:\.\d{2})?)\s*$', line)
        if amount_match and current_section:
            try:
                amount = float(amount_match.group(1).replace(",", ""))
                if amount > 0:
                    description = line[:200]
                    records.append({
                        "category": "financial",
                        "subcategory": current_section[:100],
                        "title": description[:150],
                        "description": description,
                        "amount": amount,
                        "year": "2024",
                        "source_type": "financial_statement"
                    })
            except ValueError:
                pass
    
    return records

def parse_audit_report(text):
    """Parses the audit report text into records."""
    records = []
    lines = text.split("\n")
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Extract key audit information
        if any(kw in line.lower() for kw in ["opinion", "finding", "observation", "recommendation", "material", "qualified", "unqualified"]):
            if len(line) > 20:
                records.append({
                    "category": "administrative",
                    "subcategory": "audit_report_2024",
                    "title": line[:150],
                    "description": line,
                    "year": "2024",
                    "source_type": "audit_report"
                })
    
    return records

def main():
    print("=" * 70)
    print("PEMBA TOWN COUNCIL — HTML SCRAPING & TEXT PDF EXTRACTION")
    print("=" * 70)
    
    # Step 1: Scrape News Updates
    print("\n[STEP 1] Scraping News Updates...")
    posts, post_links = scrape_news_page(f"{BASE_URL}/?page_id=793")
    print(f"  Found {len(posts)} news entries, {len(post_links)} post links")
    
    for p in posts[:5]:
        print(f"    [{p['date']}] {p['title'][:80]}")
    
    # Scrape individual posts
    print("\n  Scraping individual posts...")
    individual_posts = []
    seen_urls = set()
    for link_info in post_links[:10]:
        url = link_info["url"]
        if url in seen_urls:
            continue
        seen_urls.add(url)
        post_content = scrape_individual_post(url)
        if post_content:
            post_content["source_url"] = url
            individual_posts.append(post_content)
            print(f"    Scraped: {post_content.get('title', 'untitled')[:60]}")
    
    # Step 2: Scrape Civic Leaders
    print("\n[STEP 2] Scraping Civic Leaders...")
    leaders = scrape_civic_leaders(f"{BASE_URL}/?page_id=1945")
    print(f"  Found {len(leaders)} leader entries")
    for l in leaders[:10]:
        print(f"    {l[:100]}")
    
    # Step 3: Extract text from text-only PDFs
    print("\n[STEP 3] Extracting text from scanned PDFs...")
    
    text_pdfs = {
        "financial_2024": "pdf_downloads/financial_2024.pdf",
        "audit_2024": "pdf_downloads/audit_2024.pdf",
        "budget_perf_2024": "pdf_downloads/budget_perf_2024.pdf",
        "budget_alloc_2024": "pdf_downloads/budget_alloc_2024.pdf",
        "council_meeting_2025": "pdf_downloads/council_meeting_2025.pdf",
    }
    
    text_pdf_records = []
    for name, filepath in text_pdfs.items():
        import os
        if not os.path.exists(filepath):
            print(f"  [SKIP] {name} — file not found")
            continue
        
        text = extract_text_from_pdf(filepath)
        print(f"  {name}: {len(text)} chars extracted")
        preview = text[:150].replace("\n", " ")
        print(f"    Preview: {preview}...")
        
        if "financial" in name:
            records = parse_financial_statements(text)
            text_pdf_records.extend(records)
            print(f"    Parsed {len(records)} financial records")
        elif "audit" in name:
            records = parse_audit_report(text)
            text_pdf_records.extend(records)
            print(f"    Parsed {len(records)} audit records")
    
    # Step 4: Compile results
    print("\n[STEP 4] Compiling results...")
    
    html_data = {
        "news_posts": posts,
        "post_links": post_links,
        "individual_posts": individual_posts,
        "civic_leaders": leaders
    }
    
    with open("html_scraped_data.json", "w") as f:
        json.dump(html_data, f, indent=2, default=str)
    
    with open("text_pdf_records.json", "w") as f:
        json.dump(text_pdf_records, f, indent=2, default=str)
    
    print(f"\nResults saved:")
    print(f"  html_scraped_data.json — {len(posts)} news posts, {len(individual_posts)} individual posts, {len(leaders)} leaders")
    print(f"  text_pdf_records.json — {len(text_pdf_records)} records from text PDFs")

if __name__ == "__main__":
    main()
