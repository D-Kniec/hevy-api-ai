import os
import requests
import sqlite3
import pandas as pd
from dotenv import load_dotenv

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(os.path.dirname(current_dir))
env_path = os.path.join(root_dir, '.env')
load_dotenv(env_path)

HEVY_API_KEY = os.getenv("HEVY_API_KEY")
BASE_URL = "https://api.hevyapp.com/v1"
DB_PATH = os.path.join(root_dir, "data", "hevy.db")

def run_deleted_etl():
    if not HEVY_API_KEY:
        print(f"ERROR: Missing HEVY_API_KEY in: {env_path}")
        return

    print(f"Connecting to Hevy API ({BASE_URL}/workout_events)...")
    
    headers = {"api-key": HEVY_API_KEY}
    deleted_rows = []
    
    page = 1
    page_count = 1

    while page <= page_count:
        try:
            response = requests.get(
                f"{BASE_URL}/workout_events", 
                headers=headers, 
                params={"page": page, "pageSize": 10}
            )
            
            if response.status_code != 200:
                print(f"API Error (Page {page}): {response.status_code}")
                print(f"Error body: {response.text}")
                break

            data = response.json()
            
            page_count = data.get('page_count', 1)
            events = data.get('events', [])

            print(f"Fetching page {page}/{page_count} (Found: {len(events)} events)...")

            for event in events:
                if event.get('type') == 'deleted':
                    row = {
                        "type": event.get('type'),
                        "id": event.get('id'),
                        "deleted_at": event.get('deleted_at')
                    }
                    deleted_rows.append(row)

            page += 1

        except Exception as e:
            print(f"Critical Exception: {e}")
            break

    if not deleted_rows:
        print("No deleted workouts found.")
        return

    print(f"\nSaving {len(deleted_rows)} deleted records to database...")
    
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    df = pd.DataFrame(deleted_rows)
    
    df.to_sql('DeletedWorkout', conn, if_exists='replace', index=False)
    
    print(f"Success! Database: {DB_PATH}")

    print("\n" + "="*60)
    print("TABLE PREVIEW: DeletedWorkout")
    print("="*60)
    
    print(df.head(10).to_string(index=False))
    print(f"\nTotal deleted records in database: {len(df)}")
    conn.close()

if __name__ == "__main__":
    run_deleted_etl()