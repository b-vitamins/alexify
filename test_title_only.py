#!/usr/bin/env python3
from alexify.search import fetch_openalex_works
from alexify.core import compute_overall_score

# Clear cache
from alexify import search
search._SEARCH_CACHE.clear()

# Search with just the title
title = "Proving Test Set Contamination in Black-Box Language Models"
print(f"Searching for title only: {title}\n")

results = fetch_openalex_works(title)
print(f"Found {len(results)} results\n")

# Check scores
test_entry = {
    'title': title,
    'author': 'Oren, Yonatan and Meister, Nicole and Chatterji, Niladri S. and Ladhak, Faisal and Hashimoto, Tatsunori',
    'year': '2024'
}

for i, candidate in enumerate(results[:3]):
    score = compute_overall_score(test_entry, candidate)
    print(f"Result {i+1} (score: {score:.1f}):")
    print(f"  Title: {candidate.get('title')}")
    print(f"  Year: {candidate.get('publication_year')}")
    print(f"  Authors: {[a.get('author', {}).get('display_name') for a in candidate.get('authorships', [])[:3]]}")
    print(f"  ID: {candidate.get('id')}")
    print()