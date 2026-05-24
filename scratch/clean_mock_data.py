import csv

def clean_csv(file_path):
    with open(file_path, mode='r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = list(reader)
    
    cleaned_rows = []
    removed_count = 0
    
    for row in rows:
        if not row:
            continue
        # Check order_id (the last column, index 9)
        order_id = row[9] if len(row) > 9 else ""
        symbol = row[1] if len(row) > 1 else ""
        
        # If it has "MOCK" or "ROT" in the order ID, it is mock data
        is_mock = "MOCK" in order_id.upper() or "ROT" in order_id.upper() or "MOCK" in symbol.upper()
        
        if is_mock:
            removed_count += 1
        else:
            cleaned_rows.append(row)
            
    with open(file_path, mode='w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(cleaned_rows)
        
    print(f"Cleaned {file_path}: Removed {removed_count} mock rows, {len(cleaned_rows)} rows remaining.")

if __name__ == "__main__":
    clean_csv("data/trade_history.csv")
