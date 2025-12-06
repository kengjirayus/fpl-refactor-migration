import sys
import os

# Add current directory to path so we can import modules
sys.path.append(os.getcwd())

from backend.core.data_helpers import get_entry, _fetch

entry_id = 3058167
print(f"Testing fetch for Entry ID: {entry_id}")

# Test 1: Using the helper
try:
    data = get_entry(entry_id)
    print("Result from get_entry:")
    print(data)
except Exception as e:
    print(f"get_entry failed: {e}")

# Test 2: Raw fetch to see if it's suppressed
url = f"https://fantasy.premierleague.com/api/entry/{entry_id}/"
print(f"\nTesting raw fetch: {url}")
try:
    raw = _fetch(url)
    if raw:
        print("Raw fetch success (keys only):", list(raw.keys()))
    else:
        print("Raw fetch returned None")
except Exception as e:
    print(f"Raw fetch exception: {e}")
