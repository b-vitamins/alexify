#!/usr/bin/env python3
import logging
from alexify.search import fetch_all_candidates_for_entry
from alexify.core import compute_overall_score
from alexify.matching import parse_bibtex_authors, split_name_components

# Set up logging to see what's happening
logging.basicConfig(level=logging.INFO)

# Test entry from 2024.bib
test_entry = {
    'author': 'Oren, Yonatan and Meister, Nicole and Chatterji, Niladri S. and Ladhak, Faisal and Hashimoto, Tatsunori',
    'booktitle': 'The Twelfth International Conference on Learning Representations, {ICLR} 2024, Vienna, Austria, May 7-11, 2024',
    'publisher': 'OpenReview.net',
    'title': 'Proving Test Set Contamination in Black-Box Language Models',
    'url': 'https://openreview.net/forum?id=KS8mIvetg2',
    'year': '2024'
}

# Extract first author info
authors = parse_bibtex_authors(test_entry.get("author", ""))
first_author_ln = ""
if authors:
    _, _, last = split_name_components(authors[0])
    first_author_ln = last

print(f"Title: {test_entry['title']}")
print(f"First author last name: {first_author_ln}")
print(f"Year: {test_entry['year']}")
print()

# Try fetching candidates
print("Fetching candidates...")
candidates = fetch_all_candidates_for_entry(test_entry['title'], first_author_ln, test_entry['year'])
print(f"Found {len(candidates)} candidates")
print()

# Show the candidates
for i, candidate in enumerate(candidates[:5]):
    print(f"Candidate {i+1}:")
    print(f"  Title: {candidate.get('title')}")
    print(f"  Year: {candidate.get('publication_year')}")
    print(f"  ID: {candidate.get('id')}")
    
    # Compute score
    score = compute_overall_score(test_entry, candidate)
    print(f"  Score: {score:.2f}")
    print()

# Now test without year
print("\n" + "="*50)
print("Testing without year in query...")
candidates_no_year = fetch_all_candidates_for_entry(test_entry['title'], first_author_ln, "")
print(f"Found {len(candidates_no_year)} candidates without year")

if candidates_no_year:
    best_candidate = candidates_no_year[0]
    print(f"\nBest candidate:")
    print(f"  Title: {best_candidate.get('title')}")
    print(f"  Year: {best_candidate.get('publication_year')}")
    print(f"  ID: {best_candidate.get('id')}")
    
    score = compute_overall_score(test_entry, best_candidate)
    print(f"  Score: {score:.2f}")