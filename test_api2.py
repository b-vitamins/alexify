import httpx

# Test without email first
print("Testing without email...")
params = {
    'search': 'Deep Learning',
    'per_page': 5
}

url = 'https://api.openalex.org/works'

with httpx.Client() as client:
    resp = client.get(url, params=params)
    print(f'Status: {resp.status_code}')
    print(f'URL: {resp.url}')
    if resp.status_code == 200:
        data = resp.json()
        print(f'Success! Found {len(data.get("results", []))} results')
    else:
        print(f'Error: {resp.text[:200]}')

# Test with email
print("\nTesting with email...")
params['mailto'] = 'test@example.com'

with httpx.Client() as client:
    resp = client.get(url, params=params)
    print(f'Status: {resp.status_code}')
    print(f'URL: {resp.url}')
    if resp.status_code == 200:
        print('Success with email!')
    else:
        print(f'Error: {resp.text[:200]}')