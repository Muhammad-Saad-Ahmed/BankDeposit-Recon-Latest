import pandas as pd
import re
from datetime import datetime, date

class DataCleaner:
    """
    Cleans MIS and Bank data for robust matching.
    Focuses on Date standardization, Amount formatting, and Text cleaning.
    """

    @staticmethod
    def clean_amount(val):
        """
        Standardizes amount to numeric.
        """
        if pd.isna(val) or str(val).strip() == '':
            return 0.0
        try:
            s = str(val).replace(',', '').replace('CR', '').replace('DR', '').strip()
            # Handle negatives in parentheses
            if s.startswith('(') and s.endswith(')'):
                s = '-' + s[1:-1]
            return float(s)
        except:
            return 0.0

    @staticmethod
    def clean_date(val):
        """
        Standardizes date strings/objects into datetime objects.
        Handles: 2025-12-01, 01DEC25, 01-DEC-2025, 01/12/2025, etc.
        """
        if pd.isna(val) or str(val).strip() == '':
            return pd.NaT
        
        if isinstance(val, pd.Timestamp):
            return val
        
        if isinstance(val, (datetime, date)):
            return pd.to_datetime(val)
            
        s = str(val).strip()
        
        # Common formats to try
        formats = [
            '%Y-%m-%d', '%d%b%y', '%d-%b-%Y', '%d-%b-%y', 
            '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y', '%d.%m.%Y',
            '%Y/%m/%d', '%b %d, %Y', '%d %b %Y'
        ]
        
        for fmt in formats:
            try:
                # We use pd.to_datetime which is generally more robust
                return pd.to_datetime(s, format=fmt)
            except:
                continue
        
        # Fallback to general parser (which is quite good in pandas)
        try:
            return pd.to_datetime(s, dayfirst=True) # dayfirst=True is common in PK/UK
        except:
            try:
                return pd.to_datetime(s)
            except:
                return pd.NaT

    @staticmethod
    def clean_text(val):
        """
        Cleans and normalizes text for partial matching.
        """
        if pd.isna(val):
            return ""
        s = str(val).lower().strip()
        s = re.sub(r'[^a-z0-9\s]', ' ', s)
        return " ".join(s.split())

    @staticmethod
    def clean_slip(val):
        """
        Standardizes slip numbers by removing non-alphanumeric chars and leading zeros.
        """
        if pd.isna(val) or str(val).strip() == '':
            return ""
        s = str(val).strip().split('.')[0] # Remove decimal if any (e.g. from float conversion)
        s = re.sub(r'[^a-zA-Z0-9]', '', s)
        return s.lstrip('0')

    def prepare_dataframes(self, mis_df, bank_df):
        """
        Applies cleaning to both DataFrames.
        """
        # --- Clean MIS Data ---
        # Find columns (robust to case/spaces)
        mis_cols = {c.lower().replace(' ', '').replace('.', ''): c for c in mis_df.columns}
        
        m_amt = mis_cols.get('amount') or mis_cols.get('total') or mis_df.columns[-1]
        m_date = mis_cols.get('date') or mis_df.columns[0]
        m_name = mis_cols.get('dsrname') or mis_cols.get('name') or mis_cols.get('customername') or mis_df.columns[1]
        m_slip = mis_cols.get('slipno') or mis_cols.get('instrumentno') or mis_cols.get('refno')

        mis_df['clean_amount'] = mis_df[m_amt].apply(self.clean_amount)
        mis_df['clean_date'] = mis_df[m_date].apply(self.clean_date)
        mis_df['clean_name'] = mis_df[m_name].apply(self.clean_text)
        
        if m_slip:
            mis_df['clean_slip'] = mis_df[m_slip].apply(self.clean_slip)
        else:
            mis_df['clean_slip'] = ""

        # --- Clean Bank Data ---
        bank_df['clean_amount'] = bank_df['Amount'].apply(self.clean_amount)
        bank_df['clean_date'] = bank_df['Date'].apply(self.clean_date)
        bank_df['clean_description'] = bank_df['Description'].apply(self.clean_text)
        # Extract all numbers from description as potential slip numbers
        bank_df['all_nums'] = bank_df['Description'].apply(lambda x: re.findall(r'\d+', str(x)))
        # Also a flat version for easy string searching
        bank_df['flat_desc'] = bank_df['Description'].apply(lambda x: re.sub(r'[^a-zA-Z0-9]', '', str(x)).upper())

        return mis_df, bank_df
