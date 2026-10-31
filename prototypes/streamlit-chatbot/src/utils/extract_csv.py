import csv
from collections import defaultdict

input_csv = '/Users/dev/Desktop/odds_data.csv'
output_txt = '/Users/dev/Desktop/market_mapping.txt'


mapping = defaultdict(set)

with open(input_csv, newline='', encoding='utf-8') as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        mid = row['market_id'].strip() # Remove any leading/trailing whitespace
        mname = row['market_name'].strip()
        if mid:
            mapping[mid].add(mname)


with open(output_txt, 'w', encoding='utf-8') as outfile:
    for mid, mnames in mapping.items():
    # If there are multiple names for a single id, they will be comma separated
        names_list = ", ".join(sorted(mnames))
        outfile.write(f"{mid}: {names_list}\n")

print(f"Mapping saved to {output_txt}")