import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Set

import requests
from dotenv import load_dotenv

def find_project_root() -> Path:
    current_file = Path(__file__).resolve()
    for parent in [current_file] + list(current_file.parents):
        if parent.name == "src":
            return parent.parent
    return current_file.parent.parent.parent

BASE_DIR = find_project_root()
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

ENV_PATH = BASE_DIR / ".env"
if not ENV_PATH.exists():
    ENV_PATH = BASE_DIR / "src" / ".env"
load_dotenv(ENV_PATH)

HEVY_API_KEY = os.getenv("HEVY_API_KEY")
BASE_URL = "https://api.hevyapp.com/v1"

def scan_endpoint_for_supersets(session: requests.Session, endpoint: str, item_key: str) -> None:
    print(f"Scanning /{endpoint} for superset keys...")
    found_keys: Set[str] = set()
    non_null_examples: List[Dict[str, Any]] = []

    try:
        initial_response = session.get(f"{BASE_URL}/{endpoint}", params={"page": 1, "pageSize": 10})
        initial_response.raise_for_status()
        page_count = max(1, initial_response.json().get("page_count", 1))
    except Exception as error:
        print(f"Failed to initialize {endpoint}: {error}")
        return

    for page in range(1, page_count + 1):
        try:
            response = session.get(f"{BASE_URL}/{endpoint}", params={"page": page, "pageSize": 10})
            if response.status_code == 404:
                break
            response.raise_for_status()

            items = response.json().get(item_key, [])
            for item in items:
                for exercise in item.get("exercises", []):
                    for key, value in exercise.items():
                        if "superset" in key.lower():
                            found_keys.add(key)
                            if value is not None and len(non_null_examples) < 10:
                                non_null_examples.append({
                                    "parent_id": item.get("id"),
                                    "exercise_title": exercise.get("title"),
                                    "key_found": key,
                                    "value": value
                                })
        except Exception as error:
            print(f"Error fetching page {page} for {endpoint}: {error}")
            break

    print(f"--- Results for /{endpoint} ---")
    print(f"Discovered keys matching 'superset': {found_keys}")
    print(f"Found {len(non_null_examples)} examples of NON-NULL values:")
    for example in non_null_examples:
        print(example)
    print("\n")

def check_raw_api_for_supersets() -> None:
    if not HEVY_API_KEY:
        print("Missing HEVY_API_KEY")
        sys.exit(1)

    headers = {"api-key": HEVY_API_KEY}
    
    with requests.Session() as session:
        session.headers.update(headers)
        scan_endpoint_for_supersets(session, "routines", "routines")
        scan_endpoint_for_supersets(session, "workouts", "workouts")

if __name__ == "__main__":
    check_raw_api_for_supersets()
