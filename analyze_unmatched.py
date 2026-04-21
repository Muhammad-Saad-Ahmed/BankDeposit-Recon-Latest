import sys
import os
import pandas as pd
import numpy as np

# Add the project root to sys.path
sys.path.append(os.getcwd())

from app.loader import DataLoader
from app.cleaner import DataCleaner
from app.matcher import DepositMatcher

try:
    loader = DataLoader('data/input')
    cleaner = DataCleaner()
    matcher = DepositMatcher()

    mis_df = loader.load_mis_excel('mis.xlsx')
    bank_df = loader.load_bank_statements('bank_pdf')
    mis_df, bank_df = cleaner.prepare_dataframes(mis_df, bank_df)
    result = matcher.match(mis_df, bank_df)

    # Filter for cases where amount matches but date/slip didn't
    # In my matcher, amount_matched is True if the amount exists ANYWHERE in the filtered bank records
    amt_only = result[result['amount_matched'] & ~result['date_matched']]
    
    print(f"Amount Only matches: {len(amt_only)}")
    if not amt_only.empty:
        print("\nAnalyzing 'Amount Only' samples:")
        # For each amt_only, let's see what the closest date in the bank was
        samples = amt_only.head(10)
        for idx, row in samples.iterrows():
            amt = row['clean_amount']
            m_date = row['clean_date']
            m_slip = row['clean_slip']
            m_name = row['clean_name']
            
            # Find all bank transactions with this amount
            b_matches = bank_df[bank_df['clean_amount'] == amt]
            
            print(f"\nMIS: Date={m_date.date() if not pd.isna(m_date) else 'NaT'}, Amt={amt}, Slip={m_slip}, Name={m_name}")
            for b_idx, b_row in b_matches.iterrows():
                b_date = b_row['clean_date']
                diff = (b_date - m_date).days if not pd.isna(m_date) and not pd.isna(b_date) else "N/A"
                print(f"  BANK: Date={b_date.date()}, Diff={diff} days, Desc={b_row['Description'][:50]}...")

except Exception as e:
    print(f"Error: {e}")
