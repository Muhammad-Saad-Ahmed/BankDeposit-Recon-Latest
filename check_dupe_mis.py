import pandas as pd
df = pd.read_excel('data/input/mis.xlsx')
df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
dupes = df.groupby(['Date', 'Amount']).size().reset_index(name='count')
dupes = dupes[dupes['count'] > 1]
print(f"Groups with same Date + Amount in MIS: {len(dupes)}")
print(f"Total rows in these groups: {dupes['count'].sum()}")
print(dupes.sort_values('count', ascending=False).head(10))
