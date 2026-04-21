import os
import pandas as pd

class ReconReporter:
    """
    Handles generation of final reconciliation reports with dual sheets:
    1. MIS Summary (Matched/Unmatched)
    2. Bank Summary (Matched/Unmatched per file)
    """
    
    def __init__(self, output_dir='data/output'):
        self.output_dir = output_dir

    def generate_report(self, mis_df, bank_df, filename='final_report.xlsx'):
        """
        Creates an Excel file with two sheets: 'MIS Recon' and 'Bank Recon'.
        """
        # --- 1. Process MIS Sheet ---
        m_df = mis_df.copy()
        def get_mis_status(row):
            if row.get('slip_matched'):
                return "MATCHED (Slip #)"
            if row.get('amount_matched') and row.get('date_matched'):
                if row.get('name_matched'):
                    return "MATCHED (Amt + Date + Name)"
                return "MATCHED (Amt + Date)"
            if row.get('amount_matched'):
                return "UNMATCHED (Amount Only)"
            return "UNMATCHED"
            
        m_df['Match Status'] = m_df.apply(get_mis_status, axis=1)
        m_cols_to_drop = ['clean_amount', 'clean_date', 'clean_name', 'clean_slip', '_Sheet_Name']
        m_final = m_df.drop(columns=[c for c in m_cols_to_drop if c in m_df.columns])

        # --- 2. Process Bank Sheet ---
        b_df = bank_df.copy()
        b_df['Match Status'] = b_df['bank_matched'].apply(lambda x: "MATCHED" if x else "UNMATCHED")
        b_cols_to_drop = ['clean_amount', 'clean_date', 'clean_description', 'flat_desc', 'all_nums', 'bank_matched']
        b_final = b_df.drop(columns=[c for c in b_cols_to_drop if c in b_df.columns])

        # --- 3. Save to Excel ---
        output_path = os.path.join(self.output_dir, filename)
        summary_df = self._create_summary_df(m_df, b_df)
        
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
            m_final.to_excel(writer, sheet_name='MIS Recon', index=False)
            b_final.to_excel(writer, sheet_name='Bank Recon', index=False)

        # --- 4. Print Summaries to Console ---
        self._print_mis_summary(m_df)
        self._print_bank_summary(b_df)
        
        return output_path

    def _create_summary_df(self, mis_df, bank_df):
        """
        Creates a high-level Executive Summary for CEO/Business Head.
        Safe for all Excel versions.
        """
        summary_rows = []
        
        # --- PART 1: EXECUTIVE MIS OVERVIEW ---
        total_mis = len(mis_df)
        verified_matches = len(mis_df[mis_df['date_matched']])
        unreconciled_amt = len(mis_df[mis_df['amount_matched'] & ~mis_df['date_matched']])
        completely_unmatched = total_mis - verified_matches - unreconciled_amt
        success_rate = (verified_matches / total_mis * 100) if total_mis > 0 else 0
        
        summary_rows.append({"Category": "SECTION: EXECUTIVE MIS OVERVIEW", "Metric": ""})
        summary_rows.append({"Category": "Total Deposit Records (MIS)", "Metric": total_mis})
        summary_rows.append({"Category": "Successfully Reconciled (1-to-1)", "Metric": verified_matches})
        summary_rows.append({"Category": "Reconciliation Success Rate", "Metric": f"{success_rate:.2f}%"})
        summary_rows.append({"Category": "", "Metric": ""})
        
        summary_rows.append({"Category": "SECTION: AUDIT EXCEPTIONS", "Metric": "COUNT"})
        summary_rows.append({"Category": "Amount Match Found (Potential Error)", "Metric": unreconciled_amt})
        summary_rows.append({"Category": "Zero Match Found (Missing in Bank)", "Metric": completely_unmatched})
        summary_rows.append({"Category": "", "Metric": ""})

        # --- PART 2: OPERATIONAL BANK ANALYSIS ---
        total_bank = len(bank_df)
        total_matched_bank = len(bank_df[bank_df['bank_matched']])
        bank_efficiency = (total_matched_bank / total_bank * 100) if total_bank > 0 else 0

        summary_rows.append({"Category": "SECTION: OPERATIONAL BANK ANALYSIS", "Metric": "MATCHED / TOTAL"})
        
        bank_files = bank_df['Source_Bank'].unique()
        for b_file in bank_files:
            file_data = bank_df[bank_df['Source_Bank'] == b_file]
            t = len(file_data)
            m = len(file_data[file_data['bank_matched']])
            p = (m/t*100) if t > 0 else 0
            summary_rows.append({"Category": f"Source: {b_file}", "Metric": f"{m} / {t} ({p:.1f}%)"})
            
        summary_rows.append({"Category": "", "Metric": ""})
        summary_rows.append({"Category": "Grand Total Bank Records", "Metric": total_bank})
        summary_rows.append({"Category": "Total Bank Records Reconciled", "Metric": total_matched_bank})
        summary_rows.append({"Category": "Overall Bank Match Efficiency", "Metric": f"{bank_efficiency:.2f}%"})

        return pd.DataFrame(summary_rows)

    def _print_mis_summary(self, mis_df):
        print("\n" + "="*45)
        print("📊 MIS DEPOSIT RECONCILIATION SUMMARY")
        print("="*45)
        
        total_mis = len(mis_df)
        # 1-to-1 Matches (Pass 1, 2, or 3)
        verified_matches = len(mis_df[mis_df['date_matched']])
        
        # Unreconciled (Amount exists but no 1-to-1 link found)
        unreconciled_amt = len(mis_df[mis_df['amount_matched'] & ~mis_df['date_matched']])
        
        # No Match at all
        completely_unmatched = total_mis - verified_matches - unreconciled_amt
        
        print(f"Total MIS Records:           {total_mis}")
        print(f"Verified 1-to-1 Matches:     {verified_matches}  <-- (Limited by Bank total)")
        print(f"Unresolved (Amount in Bank): {unreconciled_amt}  <-- (Possible duplicates/date errors)")
        print(f"Completely Unmatched:        {completely_unmatched}")
        print("-" * 45)

    def _print_bank_summary(self, bank_df):
        print("\n" + "="*45)
        print("🏦 BANK STATEMENT RECONCILIATION SUMMARY")
        print("="*45)
        
        bank_files = bank_df['Source_Bank'].unique()
        for b_file in bank_files:
            file_data = bank_df[bank_df['Source_Bank'] == b_file]
            total_b = len(file_data)
            matched_b = len(file_data[file_data['bank_matched']])
            unmatched_b = total_b - matched_b
            
            print(f"File: {b_file}")
            print(f"  Total Transactions:  {total_b}")
            print(f"  Matched to MIS:      {matched_b}")
            print(f"  Unmatched in Bank:   {unmatched_b}")
            print("-" * 25)
        
        # Grand Total Bank
        total_bank = len(bank_df)
        total_matched_bank = len(bank_df[bank_df['bank_matched']])
        print(f"GRAND TOTAL BANK RECORDS:  {total_bank}")
        print(f"GRAND TOTAL MATCHED:       {total_matched_bank}")
        print("="*45 + "\n")
