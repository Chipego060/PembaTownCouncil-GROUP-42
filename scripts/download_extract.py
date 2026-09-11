#!/usr/bin/env python3
"""
Phase 2 (Optimized): Download and extract key PDFs — prioritized for speed.
Group 42 — Pemba Town Council — CSC 4792 Mini Project
"""

import requests
import warnings
import os
import json
import re
import pdfplumber
import pandas as pd
from io import BytesIO

warnings.filterwarnings("ignore")

DOWNLOAD_DIR = "pdf_downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# PRIORITY documents — smaller, high-value files
PRIORITY_DOCS = {
    # CDF Community Projects (small, tabular — highest value)
    "cdf_projects_2021": "http://www.pembacouncil.gov.zm/wp-content/uploads/2024/09/LIST-OF-2021-PEMBA-COMMUNITY-PROJECTS.pdf",
    "cdf_projects_2022": "http://www.pembacouncil.gov.zm/wp-content/uploads/2024/09/LIST-OF-2022-PEMBA-COMMUNITY-PROGECTS.pdf",
    "cdf_projects_2023": "http://www.pembacouncil.gov.zm/wp-content/uploads/2024/09/LIST-OF-2023-PEMBA-COMMUNITY-PROJECTS.pdf",
    "cdf_projects_2024": "http://www.pembacouncil.gov.zm/wp-content/uploads/2025/12/2024-Approved-Projects-1.pdf",
    "cdf_projects_2025": "http://www.pembacouncil.gov.zm/wp-content/uploads/2025/12/2025-Approved-Projects-1.pdf",
    "cdf_unapproved_2024": "http://www.pembacouncil.gov.zm/wp-content/uploads/2025/12/PEMBA-TOWN-COUNCIL-2024-UNAPPROVED-CDF-PROJECTS-1.pdf",
    "cdf_unapproved_2025": "http://www.pembacouncil.gov.zm/wp-content/uploads/2025/12/PEMBA-TOWN-COUNCIL-2025-UNAPPROVED-CDF-PROJECTS-1.pdf",
    "cdf_status_2025": "http://www.pembacouncil.gov.zm/wp-content/uploads/2025/12/2025-status.pdf",
    "cdf_received_2025": "http://www.pembacouncil.gov.zm/wp-content/uploads/2025/12/ALL-RECIEVED-COMMUNITY-PROJECTS-RECOMMENDED-FOR-2025-4.pdf",
    # Budgets (medium size, critical data)
    "budget_2024": "http://www.pembacouncil.gov.zm/wp-content/uploads/2024/08/2024-Pemba-Budget.pdf",
    "budget_2025": "http://www.pembacouncil.gov.zm/wp-content/uploads/2025/12/PEMBA-BUDGET-2025..-1.pdf",
    "budget_2026": "http://www.pembacouncil.gov.zm/wp-content/uploads/2026/08/OBB-2026-Pemba-Town-Council...pdf",
    # Budget performance
    "budget_perf_2024": "http://www.pembacouncil.gov.zm/wp-content/uploads/2025/10/Annual-budget-performance-2024.pdf",
    "budget_alloc_2024": "http://www.pembacouncil.gov.zm/wp-content/uploads/2025/10/Budget-allocation-by-program-1.pdf",
    # Financial statements
    "financial_2024": "http://www.pembacouncil.gov.zm/wp-content/uploads/2025/11/2024-Pemba-Town-Council-Financial-Statement.pdf",
    # Other
    "budget_hearing_2024": "http://www.pembacouncil.gov.zm/wp-content/uploads/2025/12/The-Business-minutes-meeting-2024.pdf",
    "council_meeting_2025": "http://www.pembacouncil.gov.zm/wp-content/uploads/2025/11/2025-Council-Special-Meeting.pdf",
    "audit_2024": "http://www.pembacouncil.gov.zm/wp-content/uploads/2025/11/Audit-opinion.pdf",
}

def download_pdf(url, name, timeout=20):
    """Download a PDF and save locally."""
    filepath = os.path.join(DOWNLOAD_DIR, f"{name}.pdf")
    
    if os.path.exists(filepath) and os.path.getsize(filepath) > 500:
        size = os.path.getsize(filepath)
        print(f"  [CACHED] {name} ({size} bytes)")
        return filepath
    
    try:
        resp = requests.get(url, headers=HEADERS, verify=False, timeout=timeout)
        if resp.status_code == 200 and len(resp.content) > 500:
            with open(filepath, "wb") as f:
                f.write(resp.content)
            print(f"  [OK] {name} ({len(resp.content)} bytes)")
            return filepath
        else:
            print(f"  [SKIP] {name} — status {resp.status_code}")
            return None
    except Exception as e:
        print(f"  [FAIL] {name} — {str(e)[:60]}")
        return None

def extract_tables_and_text(filepath):
    """Extract tables and text from a PDF."""
    tables = []
    text = ""
    try:
        with pdfplumber.open(filepath) as pdf:
            for i, page in enumerate(pdf.pages):
                page_text = page.extract_text() or ""
                text += page_text + "\n"
                
                page_tables = page.extract_tables()
                for table in page_tables:
                    if table and len(table) > 1:
                        cleaned = []
                        for row in table:
                            cleaned_row = [str(cell).strip().replace("\n", " ") if cell else "" for cell in row]
                            cleaned.append(cleaned_row)
                        tables.append({
                            "page": i + 1,
                            "headers": cleaned[0] if cleaned else [],
                            "rows": cleaned[1:] if len(cleaned) > 1 else [],
                            "all_rows": cleaned
                        })
    except Exception as e:
        print(f"  [ERROR] {e}")
    
    return {"tables": tables, "text": text, "text_length": len(text)}

def parse_table_to_records(table_data, category, year, source_name):
    """Convert a table to structured records."""
    records = []
    headers = table_data.get("headers", [])
    rows = table_data.get("rows", [])
    
    for row in rows:
        if not row or all(not cell for cell in row):
            continue
        
        record = {
            "category": category,
            "year": year,
            "source_type": "pdf",
            "source_name": source_name,
            "raw_row": row
        }
        
        # Try to map columns to fields
        for i, cell in enumerate(row):
            if not cell:
                continue
            header = headers[i] if i < len(headers) else ""
            header_lower = header.lower()
            
            # Amount fields
            if any(kw in header_lower for kw in ["amount", "cost", "budget", "allocation", "total", "kwacha", "k "] or cell.startswith("K ") or cell.startswith("K" ) ):
                amount_match = re.search(r'K\s*([\d,]+(?:\.\d{2})?)', cell)
                if amount_match:
                    try:
                        record["amount"] = float(amount_match.group(1).replace(",", ""))
                    except ValueError:
                        pass
            
            # Project/description
            if any(kw in header_lower for kw in ["project", "description", "activity", "item", "name"]):
                record["title"] = cell[:200]
                record["description"] = cell
            
            # Ward
            if any(kw in header_lower for kw in ["ward", "area", "location"]):
                record["ward"] = cell
            
            # Status
            if any(kw in header_lower for kw in ["status", "state", "progress"]):
                record["status"] = cell.lower()
            
            # Number/count
            if any(kw in header_lower for kw in ["no", "number", "num", "sn", "s/n"]):
                record["item_number"] = cell
        
        # If no title found, use first non-empty cell
        if "title" not in record:
            for cell in row:
                if cell and len(cell) > 3 and not cell.startswith("K"):
                    record["title"] = cell[:200]
                    record["description"] = cell
                    break
        
        records.append(record)
    
    return records

def main():
    print("=" * 70)
    print("PEMBA TOWN COUNCIL — PDF EXTRACTION (OPTIMIZED)")
    print("=" * 70)
    
    # Download all priority documents
    print("\n[STEP 1] Downloading priority PDFs...")
    downloaded = {}
    for name, url in PRIORITY_DOCS.items():
        filepath = download_pdf(url, name)
        if filepath:
            downloaded[name] = filepath
    
    print(f"\nDownloaded {len(downloaded)}/{len(PRIORITY_DOCS)} documents")
    
    # Extract and parse each
    print("\n[STEP 2] Extracting data from PDFs...")
    all_records = []
    all_tables = {}
    extraction_summary = {}
    
    for name, filepath in downloaded.items():
        print(f"\n  --- {name} ---")
        result = extract_tables_and_text(filepath)
        
        print(f"  Tables: {len(result['tables'])}, Text: {result['text_length']} chars")
        
        # Show table previews
        for t in result["tables"][:3]:
            print(f"    Page {t['page']}: {len(t['rows'])} data rows")
            if t["headers"]:
                print(f"    Headers: {t['headers'][:5]}")
            if t["rows"]:
                print(f"    Sample:  {t['rows'][0][:3]}")
        
        # Show text preview
        preview = result["text"][:200].replace("\n", " ")
        print(f"    Text preview: {preview[:120]}...")
        
        # Determine year and category from name
        parts = name.split("_")
        year = parts[-1] if parts[-1].isdigit() else ""
        
        if "cdf" in name or "project" in name or "approved" in name or "unapproved" in name:
            category = "CDF"
        elif "budget" in name:
            category = "budget"
        elif "financial" in name:
            category = "financial"
        else:
            category = "administrative"
        
        # Parse tables into records
        for t in result["tables"]:
            records = parse_table_to_records(t, category, year, name)
            if records:
                all_records.extend(records)
                print(f"    Parsed {len(records)} records from table")
        
        # Store results
        all_tables[name] = result["tables"]
        extraction_summary[name] = {
            "tables": len(result["tables"]),
            "text_length": result["text_length"],
            "records_parsed": len([r for r in all_records if r.get("source_name") == name])
        }
    
    # Save everything
    print("\n[STEP 3] Saving results...")
    
    with open("extracted_tables.json", "w") as f:
        # Convert to serializable format
        serializable = {}
        for name, tables in all_tables.items():
            serializable[name] = [
                {"page": t["page"], "headers": t["headers"], "rows": t["rows"][:20]}
                for t in tables
            ]
        json.dump(serializable, f, indent=2, default=str)
    
    with open("all_records.json", "w") as f:
        json.dump(all_records, f, indent=2, default=str)
    
    with open("extraction_summary.json", "w") as f:
        json.dump(extraction_summary, f, indent=2, default=str)
    
    print(f"\nTotal records: {len(all_records)}")
    print(f"Files saved: extracted_tables.json, all_records.json, extraction_summary.json")
    
    # Summary by category
    categories = {}
    for r in all_records:
        cat = r.get("category", "unknown")
        categories[cat] = categories.get(cat, 0) + 1
    
    print("\nRecords by category:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}")

if __name__ == "__main__":
    main()
