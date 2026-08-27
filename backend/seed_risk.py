import requests

page = 1
all_txns = []
while True:
    r = requests.get(f'http://localhost:8000/api/v1/transactions?page={page}&page_size=50&sort_by=created_at&sort_dir=desc')
    data = r.json()
    items = data.get('items', [])
    all_txns.extend(items)
    if len(all_txns) >= data.get('total', 0):
        break
    page += 1

print(f'Transactions found: {len(all_txns)}')

success = 0
for txn in all_txns:
    try:
        resp = requests.post(f"http://localhost:8000/api/v1/risk/predict/{txn['transaction_id']}")
        if resp.status_code == 200:
            success += 1
    except:
        pass

print(f'Risk predictions created: {success}/{len(all_txns)}')
