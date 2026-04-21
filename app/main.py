import os
import argparse
import sys
import pandas as pd
from datetime import timedelta

# Ensure 'app' is in path if running from root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.loader import DataLoader
from app.cleaner import DataCleaner
from app.matcher import DepositMatcher
from app.reporter import ReconReporter

def main():
    """
    Main execution pipeline for Deposit Reconciliation System.
    """
    # 1. Initialize components
    loader = DataLoader(input_dir='data/input')
    cleaner = DataCleaner()
    matcher = DepositMatcher()
    reporter = ReconReporter(output_dir='data/output')

    # 2. Load MIS Data
    print("Loading MIS...")
    try:
        # User requested /data/input/mis.xlsx specifically
        mis_df = loader.load_mis_excel("mis.xlsx")
        
        # Analyze MIS for date range for smart filtering
        mis_cols = {c.lower().replace(' ', ''): c for c in mis_df.columns}
        m_date_col = mis_cols.get('date') or mis_df.columns[0]
        mis_dates = mis_df[m_date_col].apply(cleaner.clean_date).dropna()
        
        if mis_dates.empty:
            print("Error: No valid dates found in MIS file.")
            return
            
        start_date = mis_dates.min() - timedelta(days=2)
        end_date = mis_dates.max() + timedelta(days=2)

        # 3. Load Bank Statements
        print(f"Reading PDFs (filtering for range: {start_date.date()} to {end_date.date()})...")
        # Update loader to look in bank_pdf/ as per requirement
        bank_df = loader.load_bank_statements(subdir='bank_pdf', start_date=start_date, end_date=end_date)
        
    except Exception as e:
        print(f"Error during data loading: {e}")
        return

    if bank_df.empty:
        print("No bank statement data found. Check your PDF files in data/input/bank_pdf/")
        return

    # 4. Clean and Filter
    mis_df, bank_df = cleaner.prepare_dataframes(mis_df, bank_df)
    bank_df = bank_df[(bank_df['clean_date'] >= start_date) & (bank_df['clean_date'] <= end_date)]

    # 5. Matching Logic
    print("Matching...")
    result_df, bank_result_df = matcher.match(mis_df, bank_df)

    # 6. Generate Report
    reporter.generate_report(result_df, bank_result_df, filename='final_report.xlsx')
    print("Report Generated: data/output/final_report.xlsx")

if __name__ == "__main__":
    main()
