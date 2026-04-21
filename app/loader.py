import os
import pandas as pd
from .pdf_extractor import BankPDFExtractor

class DataLoader:
    """
    Loads MIS (Excel) and Bank (PDF) data from specified folders.
    """
    
    def __init__(self, input_dir='data/input'):
        self.input_dir = input_dir
        self.pdf_extractor = BankPDFExtractor()

    def load_mis_excel(self, filename):
        """
        Loads the main MIS Excel file, merging only the primary sheets to avoid duplicates.
        """
        path = os.path.join(self.input_dir, filename)
        if not os.path.exists(path):
            raise FileNotFoundError(f"MIS Excel not found at {path}")
        
        xl = pd.ExcelFile(path)
        sheet_names = xl.sheet_names
        
        # Heuristic: If there is a master sheet containing 'MIS' and 'DEPOSIT', use only that.
        # Otherwise, if Sheet1/Sheet2 are parts, merge them. 
        # But never merge both the parts AND the master sheet.
        master_sheets = [s for s in sheet_names if 'MIS' in s.upper() and 'DEPOSIT' in s.upper()]
        
        if master_sheets:
            print(f"Loading master MIS sheet: {master_sheets[0]}")
            df = pd.read_excel(path, sheet_name=master_sheets[0])
            df['_Sheet_Name'] = master_sheets[0]
            return df
            
        all_sheets = []
        for sheet_name in sheet_names:
            df = pd.read_excel(path, sheet_name=sheet_name)
            if not df.empty:
                df['_Sheet_Name'] = sheet_name
                all_sheets.append(df)
        
        if not all_sheets:
            return pd.DataFrame()
            
        return pd.concat(all_sheets, ignore_index=True, sort=False)

    def load_bank_statements(self, subdir=None, start_date=None, end_date=None):
        """
        Loads all PDF statements from input directory (or subdirectory) and merges them.
        """
        search_dir = os.path.join(self.input_dir, subdir) if subdir else self.input_dir
        if not os.path.exists(search_dir):
            print(f"Warning: Directory {search_dir} does not exist.")
            return pd.DataFrame(columns=['Date', 'Description', 'Amount', 'Source_Bank'])

        all_dfs = []
        for file in os.listdir(search_dir):
            if file.lower().endswith('.pdf'):
                path = os.path.join(search_dir, file)
                # print(f"Extracting: {file}") # Reduced noise for clean logs
                df = self.pdf_extractor.extract_from_pdf(path, start_date=start_date, end_date=end_date)
                if not df.empty:
                    df['Source_Bank'] = file # Track which bank statement it came from
                    all_dfs.append(df)
        
        if not all_dfs:
            return pd.DataFrame(columns=['Date', 'Description', 'Amount', 'Source_Bank'])
            
        return pd.concat(all_dfs, ignore_index=True)
