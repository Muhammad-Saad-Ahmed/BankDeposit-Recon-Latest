import pandas as pd
import numpy as np
import re

class DepositMatcher:
    """
    Optimized Priority-based matching engine:
    1. Slip Number (Reverse Index Lookup)
    2. Smart Match (Amt + Date ±2 + Name/Branch)
    3. Greedy Match (Amt Fallback)
    """

    def match(self, mis_df, bank_df):
        print(f"Starting match for {len(mis_df)} MIS records and {len(bank_df)} bank records...")
        mis_df = mis_df.copy()
        bank_df = bank_df.copy()
        
        # Initialize result columns
        mis_df['amount_matched'] = False
        mis_df['date_matched'] = False
        mis_df['slip_matched'] = False
        mis_df['name_matched'] = False
        mis_df['matched_bank_file'] = ""
        bank_df['bank_matched'] = False
        
        if mis_df.empty or bank_df.empty:
            print("Empty dataframe(s), returning early.")
            return mis_df, bank_df

        used_bank_indices = set()
        
        # Pre-process bank data for fast lookup
        amt_to_bank_idx = {}
        slip_to_bank_idx = {} # Word/Number -> list of bank indices
        
        print("Indexing bank data for fast matching...")
        for b_idx, b_row in bank_df.iterrows():
            # Amount Index
            amt = b_row['clean_amount']
            if amt not in amt_to_bank_idx: amt_to_bank_idx[amt] = []
            amt_to_bank_idx[amt].append(b_idx)
            
            # Slip Index (extract numbers from description)
            all_nums = str(b_row.get('all_nums', ''))
            for num in re.findall(r'\d{4,}', all_nums): # Only index numbers >= 4 digits
                if num not in slip_to_bank_idx: slip_to_bank_idx[num] = []
                slip_to_bank_idx[num].append(b_idx)

        print(f"Index built: {len(amt_to_bank_idx)} unique amounts, {len(slip_to_bank_idx)} unique slip patterns.")

        # Set initial amount_matched flag
        for idx, m_row in mis_df.iterrows():
            if m_row['clean_amount'] in amt_to_bank_idx:
                mis_df.at[idx, 'amount_matched'] = True

        # PASS 1: SLIP NUMBER MATCHING (Optimized)
        print("Pass 1: Slip Matching...")
        slip_matches = 0
        for idx, m_row in mis_df.iterrows():
            m_slip = str(m_row.get('clean_slip', ''))
            if not m_slip or len(m_slip) <= 3: continue
            
            potential_b_indices = slip_to_bank_idx.get(m_slip, [])
            for b_idx in potential_b_indices:
                if b_idx in used_bank_indices: continue
                
                b_row = bank_df.loc[b_idx]
                if m_row['clean_amount'] == b_row['clean_amount']:
                    mis_df.at[idx, 'amount_matched'] = True
                    mis_df.at[idx, 'slip_matched'] = True
                    mis_df.at[idx, 'date_matched'] = True
                    mis_df.at[idx, 'matched_bank_file'] = b_row['Source_Bank']
                    used_bank_indices.add(b_idx)
                    slip_matches += 1
                    break
        print(f"Pass 1 complete. Found {slip_matches} slip matches.")
        
        # PASS 2: SMART MATCH (Amt + Date ±2 + Context)
        print("Pass 2: Smart Matching (±2 days)...")
        branch_map = {
            'ORANGI': ['FOOD', 'CORP'],
            'NORTH KARACHI': ['SOL', 'SOLUTION'],
            'JOHAR': ['ENT', 'ENTERPRISE', 'BAHL'],
            'NAZIMABAD': ['ENT', 'ENTERPRISE', 'BAHL'],
            'SITE': ['FCPL', 'MEEZAN']
        }
        smart_matches = 0
        for idx, m_row in mis_df.iterrows():
            if mis_df.at[idx, 'slip_matched']: continue
            
            amt = m_row['clean_amount']
            m_date = m_row['clean_date']
            if pd.isna(m_date) or amt not in amt_to_bank_idx: continue
            
            b_indices = [b_idx for b_idx in amt_to_bank_idx[amt] if b_idx not in used_bank_indices]
            if not b_indices: continue

            m_branch = str(m_row.get('Branch', '')).upper()
            keywords = branch_map.get(m_branch, [])
            m_name = m_row.get('clean_name', '')
            
            best_match_idx = None
            min_date_diff = 999
            
            for b_idx in b_indices:
                b_row = bank_df.loc[b_idx]
                diff = abs((b_row['clean_date'] - m_date).days)
                
                if diff <= 2.0:
                    branch_match = any(kw in b_row['Source_Bank'].upper() for kw in keywords) if keywords else False
                    name_match = m_name and m_name in b_row.get('clean_description', '')
                    
                    if name_match or branch_match:
                        best_match_idx = b_idx
                        mis_df.at[idx, 'name_matched'] = True
                        break
                    
                    if diff < min_date_diff:
                        min_date_diff = diff
                        best_match_idx = b_idx

            if best_match_idx is not None:
                mis_df.at[idx, 'amount_matched'] = True
                mis_df.at[idx, 'date_matched'] = True
                mis_df.at[idx, 'matched_bank_file'] = bank_df.loc[best_match_idx, 'Source_Bank']
                used_bank_indices.add(best_match_idx)
                smart_matches += 1
        print(f"Pass 2 complete. Found {smart_matches} smart matches.")

        # PASS 3: GREEDY MATCH (Distant Dates)
        print("Pass 3: Greedy Matching (fallback)...")
        greedy_matches = 0
        for idx, m_row in mis_df.iterrows():
            if mis_df.at[idx, 'date_matched'] or mis_df.at[idx, 'slip_matched']: continue
            
            amt = m_row['clean_amount']
            if amt not in amt_to_bank_idx: continue
            
            b_indices = [b_idx for b_idx in amt_to_bank_idx[amt] if b_idx not in used_bank_indices]
            if not b_indices: continue
            
            m_date = m_row['clean_date']
            best_fallback_idx = min(b_indices, key=lambda i: abs((bank_df.loc[i, 'clean_date'] - m_date).days))
            
            mis_df.at[idx, 'amount_matched'] = True
            mis_df.at[idx, 'date_matched'] = True
            mis_df.at[idx, 'matched_bank_file'] = bank_df.loc[best_fallback_idx, 'Source_Bank']
            used_bank_indices.add(best_fallback_idx)
            greedy_matches += 1
        print(f"Pass 3 complete. Found {greedy_matches} greedy matches.")

        # Finalize bank statuses
        for b_idx in used_bank_indices:
            bank_df.at[b_idx, 'bank_matched'] = True

        print(f"Reconciliation finished. Total bank records matched: {len(used_bank_indices)}")
        return mis_df, bank_df
