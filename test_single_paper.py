#!/usr/bin/env python3
from alexify.search import fetch_all_candidates_for_entry
from alexify.core import compute_overall_score

# Test the problematic paper
title = "Proving Test Set Contamination in Black-Box Language Models"
author = "oren"
year = "2024"

print(f"Searching for: {title}")
print(f"Author: {author}, Year: {year}\n")

# Try without caching to see fresh results
from alexify import search
search._SEARCH_CACHE.clear()

candidates = fetch_all_candidates_for_entry(title, author, year)
print(f"Found {len(candidates)} candidates\n")

# Check the scores for top candidates
if candidates:
    test_entry = {
        'title': title,
        'author': 'Oren, Yonatan and Meister, Nicole and Chatterji, Niladri S. and Ladhak, Faisal and Hashimoto, Tatsunori',
        'year': year
    }
    
    scored = []
    for candidate in candidates[:10]:
        score = compute_overall_score(test_entry, candidate)
        scored.append((score, candidate))
    
    scored.sort(key=lambda x: x[0], reverse=True)
    
    for i, (score, candidate) in enumerate(scored[:5]):
        print(f"Candidate {i+1} (score: {score:.1f}):")
        print(f"  Title: {candidate.get('title')}")
        print(f"  Year: {candidate.get('publication_year')}")
        print(f"  Authors: {[a.get('author', {}).get('display_name') for a in candidate.get('authorships', [])[:3]]}")
        print()