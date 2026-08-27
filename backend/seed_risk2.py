import requests

r = requests.get('http://localhost:8000/api/v1/transactions?page=1&page_size=300&sort_by=created_at&sort_dir=desc')
items = r.json().get('items', [])
print(f'Total: {len(items)}')

success = 0
fail = 0
for i, txn in enumerate(items):
    try:
        resp = requests.post(f"http://localhost:8000/api/v1/risk/predict/{txn['transaction_id']}", timeout=5)
        if resp.status_code in [200, 409]:
            success += 1
        else:
            fail += 1
    except:
        fail += 1
    if i % 20 == 0:
        print(f'Progress: {i+1}/{len(items)}')

print(f'Done! Success: {success}, Failed: {fail}')
