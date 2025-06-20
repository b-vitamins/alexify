#!/usr/bin/env python3
import logging
from alexify.search import fetch_all_candidates_for_entry

# Enable debug logging to see query attempts
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')

# Test with the problematic entry
title = "Proving Test Set Contamination in Black-Box Language Models"
author = "oren"
year = "2024"

print(f"Testing fetch_all_candidates_for_entry with:")
print(f"  Title: {title}")
print(f"  Author: {author}")
print(f"  Year: {year}")
print()

candidates = fetch_all_candidates_for_entry(title, author, year)
print(f"\nTotal candidates found: {len(candidates)}")

if candidates:
    print("\nFirst candidate:")
    print(f"  Title: {candidates[0].get('title')}")
    print(f"  Year: {candidates[0].get('publication_year')}")
    print(f"  ID: {candidates[0].get('id')}")