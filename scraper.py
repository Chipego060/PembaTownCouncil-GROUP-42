import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import pdfplumber
import pandas as pd
import urllib3

# Suppress SSL certificate warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 1. Setup Directories
PDF_DIR = "downloaded_pdfs"
OUTPUT_DIR = "outputs"
os.makedirs(PDF_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

BASE_URL = "https://www.pembacouncil.gov.zm/"
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

print("=== STARTING PEMBA TOWN COUNCIL DATA SCRAPING ===")

# 2. Target pages to check for downloadable documents/PDFs
target_urls = [
    BASE_URL,
    urljoin(BASE_URL, "?page_id=195"),   # Publications
    urljoin(BASE_URL, "?page_id=2407")   # Finance Department
]

pdf_links = set()

for target in target_urls:
    try:
        response = requests.get(target, headers=HEADERS, timeout=15, verify=False)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            for a in soup.find_all('a', href=True):
                href = a['href']
                if href.lower().endswith('.pdf'):
                    full_url = urljoin(target, href)
                    pdf_links.add(full_url)
    except Exception as e:
        print(f"Error checking {target}: {e}")

print(f"Discovered {len(pdf_links)} PDF documents.")

# 3. Download PDFs Locally
downloaded_files = []
for link in pdf_links:
    filename = os.path.basename(link.split("?")[0])
    filepath = os.path.join(PDF_DIR, filename)
    try:
        print(f"Downloading: {filename}...")
        r = requests.get(link, headers=HEADERS, timeout=30, verify=False)
        with open(filepath, 'wb') as f:
            f.write(r.content)
        downloaded_files.append(filepath)
    except Exception as e:
        print(f"Failed to download {filename}: {e}")

# 4. Extract Tabular Data from Downloaded PDFs
print("\n=== EXTRACTING TABULAR DATA FROM PDF REPORTS ===")
all_extracted_rows = []

for pdf_path in downloaded_files:
    filename = os.path.basename(pdf_path)
    print(f"Parsing tables from: {filename}")
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        clean_row = [
                            str(cell).replace('\n', ' ').strip() if cell is not None else "" 
                            for cell in row
                        ]
                        if any(clean_row):
                            clean_row.append(filename)
                            clean_row.append(page_num + 1)
                            all_extracted_rows.append(clean_row)
    except Exception as e:
        print(f"Could not extract tables from {filename}: {e}")

# 5. Save Raw Extracted Tables
if all_extracted_rows:
    df_raw = pd.DataFrame(all_extracted_rows)
    raw_output_path = os.path.join(OUTPUT_DIR, "pemba_raw_extracted_pdf_data.csv")
    df_raw.to_csv(raw_output_path, sep='|', index=False)
    print(f"\nRaw extracted data saved to: {raw_output_path}")
else:
    print("\nNo structured PDF tables extracted automatically.")