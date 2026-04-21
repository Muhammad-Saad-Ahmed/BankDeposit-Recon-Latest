import pandas as pd
df = pd.read_excel('data/input/mis.xlsx')
print(f"Total MIS Rows: {len(df)}")
print(f"Unique Slip No: {df['Slip No.'].nunique()}")
print(f"Duplicate Slip No: {df['Slip No.'].duplicated().sum()}")
print(f"Unique Amounts in MIS: {df['Amount'].nunique()}")
