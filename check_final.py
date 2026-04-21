import pandas as pd
df = pd.read_excel('data/output/final_report.xlsx')
counts = df['Match Status'].value_counts()
print(counts)
matched_labels = [l for l in counts.index if 'MATCHED' in l and 'UNMATCHED' not in l]
total_matched = counts[matched_labels].sum()
print(f"\nCorrect Total Matched: {total_matched}")
