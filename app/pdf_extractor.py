import pdfplumber
import pandas as pd
import re
from datetime import datetime
import os

class BankPDFExtractor:
    """
    Highly specialized extractor for HBL/BAHL/Meezan PDFs.
    Handles 'ghost' characters and multi-column amount structures.
    """
    
    def __init__(self):
        # Specific patterns for HBL/BAHL date formats
        self.date_pattern = re.compile(r'(\d{1,2}[A-Z]{3}\d{2,4}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{1,2}[-/][A-Z]{3}[-/]\d{2,4}|\d{1,2}-[A-Z][a-z]{2}-\d{4})')
        
    def extract_from_pdf(self, pdf_path, start_date=None, end_date=None):
        """
        Main extraction logic using aggressive text-line parsing.
        """
        all_data = []
        file_name = os.path.basename(pdf_path).upper()
        is_bahl = "BAHL" in file_name or "HABIB" in file_name
        is_meezan = "MEEZAN" in file_name
        is_hbl = "HBL" in file_name
        
        # Buffer dates for safety
        buffer_start = start_date - pd.Timedelta(days=5) if start_date else None
        buffer_end = end_date + pd.Timedelta(days=5) if end_date else None

        try:
            with pdfplumber.open(pdf_path) as pdf:
                total_pages = len(pdf.pages)
                print(f"  - {file_name}: {total_pages} pages")
                
                consecutive_out_of_range = 0
                processed_pages = 0
                
                for page_num, page in enumerate(pdf.pages, 1):
                    text = page.extract_text()
                    if not text: continue
                    
                    # Optimization: Check if page is within date range
                    if buffer_start and buffer_end:
                        page_dates = self.date_pattern.findall(text)
                        if page_dates:
                            # Parse dates found on page to see if any are in range
                            parsed_dates = []
                            for d in page_dates:
                                try:
                                    # Use a simple parser or just check if it matches a known format
                                    # Since we don't have DataCleaner here, we'll do a quick parse
                                    p_date = pd.to_datetime(d, errors='coerce', dayfirst=True)
                                    if pd.notna(p_date):
                                        parsed_dates.append(p_date)
                                except: pass
                            
                            if parsed_dates:
                                page_min = min(parsed_dates)
                                page_max = max(parsed_dates)
                                
                                # If all dates on page are after buffer_end, and we assume ascending order
                                # (Standard for most banks), we might stop if we see several such pages.
                                if page_min > buffer_end:
                                    consecutive_out_of_range += 1
                                    if consecutive_out_of_range > 3: # Stop after 3 pages out of range
                                        print(f"    - Stopping at page {page_num}: dates {page_min.date()} > {buffer_end.date()}")
                                        break
                                    continue
                                
                                # If all dates on page are before buffer_start
                                if page_max < buffer_start:
                                    # Don't stop (could be ascending), just skip this page
                                    continue
                                
                                # If we are here, at least some dates are in range or it's mixed
                                consecutive_out_of_range = 0
                        else:
                            # No dates found on page, could be a middle page of a long txn list
                            # or a header/footer page. We'll process it if we recently saw valid dates.
                            if consecutive_out_of_range > 2:
                                continue

                    if page_num % 50 == 0:
                        print(f"    - Page {page_num}/{total_pages}...")
                    
                    processed_pages += 1
                    lines = text.split('\n')
                    current_txn = None
                    
                    for line in lines:
                        line = self._clean_ghost_chars(line)
                        clean_line = line.replace('|', ' ').strip()
                        
                        # Date match (POST DATE or VALUE DATE)
                        date_match = self.date_pattern.search(clean_line)
                        
                        # Flexible amount detection: numbers with at least one comma or decimal
                        amt_matches = re.findall(r'(\d[\d,]*\.\d{1,2})', clean_line)
                        
                        if date_match:
                            if current_txn:
                                all_data.append(current_txn)
                            
                            date_str = date_match.group(1)
                            amt = 0.0
                            
                            if is_bahl:
                                # BAHL Format: Withdrawal(0) Deposit(1) Balance(2)
                                if len(amt_matches) >= 2:
                                    try:
                                        # If first amount is 0.00, second is deposit
                                        if self._to_float(amt_matches[0]) == 0:
                                            amt = self._to_float(amt_matches[1])
                                        else:
                                            # It's a withdrawal, skip
                                            amt = 0.0
                                    except: amt = 0.0
                            elif is_hbl or is_meezan:
                                # HBL/Meezan Format
                                if len(amt_matches) >= 2:
                                    # Second to last is txn amount, last is balance
                                    amt = self._to_float(amt_matches[-2])
                                elif len(amt_matches) == 1:
                                    # If only one amount, check for 'CR' or just take it as txn
                                    if 'CR' in clean_line.upper() or 'DEP' in clean_line.upper() or 'RECD' in clean_line.upper():
                                        amt = self._to_float(amt_matches[0])
                                    else:
                                        # Likely just a balance line or withdrawal (need more context)
                                        # We'll take it for now and filter later if zero
                                        amt = self._to_float(amt_matches[0])

                            desc = clean_line.replace(date_str, '').strip()
                            for a in amt_matches:
                                desc = desc.replace(a, '').strip()
                            
                            current_txn = {
                                'Date': date_str,
                                'Description': desc,
                                'Amount': amt
                            }
                        elif current_txn:
                            # Continuation: Check if it's not a header/footer
                            if not any(kw in clean_line.upper() for kw in ['BALANCE', 'BROUGHT', 'TOTAL', 'CONTINUE', 'PAGE']):
                                line_amts = re.findall(r'(\d[\d,]*\.\d{1,2})', clean_line)
                                if not line_amts:
                                    current_txn['Description'] += " " + clean_line

                    if current_txn:
                        all_data.append(current_txn)
                        current_txn = None
                        
        except Exception as e:
            print(f"Error processing {pdf_path}: {e}")
            
        df = pd.DataFrame(all_data)
        if not df.empty:
            df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce').fillna(0.0)
            df = df[(df['Amount'] > 0) & (df['Description'].str.len() > 2)]
            print(f"    - Extracted {len(df)} deposits.")
        else:
            df = pd.DataFrame(columns=['Date', 'Description', 'Amount'])
            print(f"    - No deposits found.")
            
        return df

    def _to_float(self, val):
        if not val: return 0.0
        try:
            return float(str(val).replace(',', '').strip())
        except:
            return 0.0

    def _clean_ghost_chars(self, text):
        if not text: return ""
        if len(text) < 5: return text
        repeats = sum(1 for i in range(len(text)-1) if text[i] == text[i+1])
        if repeats > len(text) * 0.4:
            res = ""
            i = 0
            while i < len(text):
                res += text[i]
                if i < len(text)-1 and text[i] == text[i+1]:
                    i += 2
                else:
                    i += 1
            return res
        return text
