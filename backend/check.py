import requests
r = requests.get('http://localhost:8000/api/v1/transactions?page=1&page_size=5&sort_by=created_at&sort_dir=desc')
print(r.status_code)
print(r.json())
