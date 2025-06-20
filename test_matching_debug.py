#!/usr/bin/env python3
import logging
from alexify.search import fetch_openalex_works

# Set up detailed logging
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')

# Test different query combinations
queries = [
    "Proving Test Set Contamination in Black-Box Language Models oren 2024",
    "Proving Test Set Contamination in Black-Box Language Models oren",
    "Proving Test Set Contamination in Black-Box Language Models",
    "Test Set Contamination Black-Box Language Models"
]

for query in queries:
    print(f"\n{'='*60}")
    print(f"Query: {query}")
    results = fetch_openalex_works(query)
    print(f"Found {len(results)} results")
    
    if results:
        # Show first 3 results
        for i, work in enumerate(results[:3]):
            print(f"\nResult {i+1}:")
            print(f"  Title: {work.get('title')}")
            print(f"  Year: {work.get('publication_year')}")
            print(f"  Authors: {[a.get('author', {}).get('display_name') for a in work.get('authorships', [])[:3]]}")
            print(f"  ID: {work.get('id')}")