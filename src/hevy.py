import os
import requests
import json
from dotenv import load_dotenv
from db import get_connection

load_dotenv()
HEVY_API_KEY = os.getenv("HEVY_API_KEY")
BASE_URL = "https://api.hevyapp.com/v1"

def fetch_and_sync_exercises():
    headers = {"api-key": HEVY_API_KEY}
    response = requests.get(f"{BASE_URL}/exercise_templates", headers=headers)
    
    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        return

    data = response.json()
    # Kluczowa zmiana: Hevy API zwraca słownik, dane są w 'exercise_templates'
    exercises = data.get('exercise_templates', [])

    conn = get_connection()
    cursor = conn.cursor()

    for ex in exercises:
        cursor.execute("""
            INSERT INTO exercise_templates (id, title, type, primary_muscle_group, secondary_muscle_groups, is_custom)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title=excluded.title,
                type=excluded.type,
                primary_muscle_group=excluded.primary_muscle_group,
                secondary_muscle_groups=excluded.secondary_muscle_groups,
                is_custom=excluded.is_custom
        """, (
            ex['id'],
            ex['title'],
            ex['type'],
            ex['primary_muscle_group'],
            json.dumps(ex.get('secondary_muscle_groups', [])),
            ex.get('is_custom', False)
        ))

    conn.commit()
    conn.close()
    print_ascii_table(exercises[:10])

def print_ascii_table(exercises):
    if not exercises:
        print("No exercises found.")
        return

    header = f"| {'ID':<10} | {'Title':<30} | {'Muscle Group':<15} |"
    separator = "-" * len(header)
    
    print(separator)
    print(header)
    print(separator)
    
    for ex in exercises:
        title = (ex['title'][:27] + '..') if len(ex['title']) > 30 else ex['title']
        m_group = str(ex['primary_muscle_group']) if ex['primary_muscle_group'] else "None"
        print(f"| {ex['id']:<10} | {title:<30} | {m_group:<15} |")
    
    print(separator)

if __name__ == "__main__":
    fetch_and_sync_exercises()