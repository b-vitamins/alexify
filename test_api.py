import httpx

# Test with email parameter
params = {
    'search': 'Deep Learning',
    'per_page': 5,
    'mailto': 'test@example.com'
}

url = 'https://api.openalex.org/works'

print("Testing OpenAlex API...")
with httpx.Client() as client:
    resp = client.get(url, params=params)
    print(f'Status: {resp.status_code}')
    print(f'URL: {resp.url}')
    if resp.status_code != 200:
        print(f'Error: {resp.text[:500]}')
    else:
        data = resp.json()
        print(f'Success! Found {len(data.get("results", []))} results')
        
# Now test with a problematic query
print("\nTesting with problematic query...")
params2 = {
    'search': 'Proving Test Set Contamination in Black-Box Language Models oren 2024',
    'per_page': 50,
    'mailto': 'test@example.com'
}

with httpx.Client() as client:
    resp = client.get(url, params=params2)
    print(f'Status: {resp.status_code}')
    print(f'URL: {resp.url}')
    if resp.status_code != 200:
        print(f'Error response: {resp.text[:500]}')