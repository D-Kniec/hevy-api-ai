import os
import json
import sqlite3
import datetime
import requests
import logging
import time
from pathlib import Path
from google import genai
from google.genai import types
from dotenv import load_dotenv

from prompt_progression import SYSTEM_PROMPT, create_bulk_user_prompt
from warmup import calculate_warmup_sets
from analytics import analyze_exercise_history
from periodization import get_periodization_phase

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "hevy.db"
ENV_PATH = BASE_DIR / '.env'
load_dotenv(ENV_PATH)

HEVY_API_URL = "https://api.hevyapp.com/v1"
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
HEVY_API_KEY = os.getenv("HEVY_API_KEY")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logging.getLogger("google.genai").setLevel(logging.CRITICAL)

if not HEVY_API_KEY or not GOOGLE_API_KEY:
    logger.critical("Missing API Keys in .env")
    exit(1)

client = genai.Client(api_key=GOOGLE_API_KEY)

def get_headers():
    return {
        "api-key": HEVY_API_KEY,
        "Content-Type": "application/json"
    }

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def select_routine_from_db():
    try:
        with get_db_connection() as conn:
            routines = conn.execute("SELECT id, title FROM silver_routines ORDER BY title").fetchall()
        
        if not routines:
            logger.error("No routines found in DB.")
            return None

        print("\n--- Available Routines ---")
        for idx, r in enumerate(routines):
            print(f"{idx + 1}. {r['title']}")
        
        while True:
            try:
                choice = int(input("\nSelect Routine # to Update: "))
                if 1 <= choice <= len(routines):
                    return dict(routines[choice - 1])
                print("Invalid number.")
            except ValueError:
                print("Please enter a number.")
    except Exception as e:
        logger.error(f"Error: {e}")
        return None

def get_history_for_exercise(conn, template_id, limit=5):
    query = """
        SELECT w.start_time, ws.weight_kg, ws.reps, ws.rpe
        FROM silver_workout_sets ws
        JOIN silver_workout_exercises we ON ws.workout_exercise_id = we.id
        JOIN silver_workouts w ON we.workout_id = w.id
        WHERE we.exercise_template_id = ? AND ws.set_type = 'normal'
        ORDER BY w.start_time DESC
        LIMIT 20
    """
    rows = [dict(r) for r in conn.execute(query, (template_id,)).fetchall()]
    
    sessions = {}
    for r in rows:
        d = r['start_time'][:10]
        if d not in sessions: sessions[d] = []
        sessions[d].append(r)
    
    history = []
    for d, sets in sessions.items():
        best = max(sets, key=lambda x: (x['weight_kg'] or 0, x['reps'] or 0))
        history.append({
            "date": d,
            "weight": best['weight_kg'],
            "reps": best['reps'],
            "rpe": best['rpe']
        })
    return history[:limit]

def get_full_routine_data(routine_id):
    with get_db_connection() as conn:
        routine = conn.execute("SELECT * FROM silver_routines WHERE id = ?", (routine_id,)).fetchone()
        if not routine: return None
        
        routine_data = dict(routine)
        
        exercises = conn.execute("""
            SELECT 
                re.id, re.exercise_template_id, re.notes, re.order_index, re.rest_seconds, re.superset_id,
                et.title, et.base_increment
            FROM silver_routine_exercises re
            LEFT JOIN silver_exercise_templates et ON re.exercise_template_id = et.id
            WHERE re.routine_id = ?
            ORDER BY re.order_index
        """, (routine_id,)).fetchall()
        
        routine_data['exercises'] = []
        for ex in exercises:
            ex_dict = dict(ex)
            sets = conn.execute("SELECT * FROM silver_routine_sets WHERE routine_exercise_id = ?", (ex['id'],)).fetchall()
            ex_dict['sets'] = [dict(s) for s in sets]
            ex_dict['history'] = get_history_for_exercise(conn, ex['exercise_template_id'])
            routine_data['exercises'].append(ex_dict)
            
        return routine_data

def generate_bulk_plan(routine_data):
    phase = get_periodization_phase()
    logger.info(f"Periodization Phase: {phase['name']} (Week {phase['week']}/4)")

    exercises_context = []
    for ex in routine_data['exercises']:
        clean_history = []
        for h in ex['history']:
            clean_history.append({
                "date": h['date'],
                "weight": h['weight'],
                "reps": h['reps'],
                "rpe": h.get('rpe', 'N/A')
            })

        analytics = analyze_exercise_history(clean_history)

        exercises_context.append({
            "id": ex['exercise_template_id'],
            "name": ex['title'],
            "base_increment": ex['base_increment'] or 2.5,
            "analytics": analytics,
            "history_summary": clean_history[:3]
        })
    
    formatted_system_prompt = SYSTEM_PROMPT.format(
        phase_name=phase['name'],
        phase_week=phase['week'],
        phase_goal=phase['goal'],
        phase_rpe=phase['rpe_target'],
        phase_instruction=phase['instruction']
    )

    user_prompt_content = create_bulk_user_prompt(exercises_context)
    full_prompt = f"{formatted_system_prompt}\n\n{user_prompt_content}"
    
    candidate_models = ["gemini-3-flash-preview", "gemini-2.0-flash"]
    
    logger.info(f"Sending BULK request for {len(exercises_context)} exercises...")
    
    for model in candidate_models:
        try:
            response = client.models.generate_content(
                model=model,
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1
                )
            )
            return json.loads(response.text)
            
        except Exception as e:
            logger.warning(f"Model {model} failed: {e}")
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                time.sleep(1)
            else:
                continue

    return None

def main():
    selected = select_routine_from_db()
    if not selected: return

    logger.info(f"Loading data for {selected['title']}...")
    routine_data = get_full_routine_data(selected['id'])
    
    ai_response = generate_bulk_plan(routine_data)
    
    if not ai_response or 'recommendations' not in ai_response:
        logger.error("Failed to generate plan.")
        return

    recommendations = ai_response['recommendations']

    print("\n--- AI PLAN ---")
    for tid, rec in recommendations.items():
        name = next((e['title'] for e in routine_data['exercises'] if e['exercise_template_id'] == tid), "Unknown")
        print(f"{name}: {rec.get('weight_kg')}kg x {rec.get('reps')} ({rec.get('strategy')})")

    if input("\nUpdate Hevy? (y/n): ").lower() != 'y':
        return

    updated_routine = {
        "title": routine_data['title'],
        "notes": f"AI Plan: {datetime.datetime.now().strftime('%Y-%m-%d')}",
        "exercises": []
    }
    
    for ex in routine_data['exercises']:
        tid = ex['exercise_template_id']
        rec = recommendations.get(tid)
        
        new_ex = {
            "exercise_template_id": tid,
            "superset_id": ex['superset_id'],
            "rest_seconds": ex['rest_seconds'],
            "notes": ex['notes'] or "",
            "sets": []
        }
        
        if rec:
            rpe_note = f" RPE {rec.get('rpe_target')}" if rec.get('rpe_target') else ""
            new_ex['notes'] = f"[AI: {rec['reasoning']}{rpe_note}] " + new_ex['notes']

            target_weight = rec['weight_kg']
            target_reps = rec['reps']

            if target_weight > 0:
                warmups = calculate_warmup_sets(target_weight)
                for w in warmups:
                    new_ex['sets'].append({
                        "type": "warmup",
                        "weight_kg": w['weight_kg'],
                        "reps": w['reps'],
                        "distance_meters": None,
                        "duration_seconds": None
                    })

            original_working_sets = [s for s in ex['sets'] if s['set_type'] == 'normal']
            num_working_sets = len(original_working_sets) if original_working_sets else 3
            
            for _ in range(num_working_sets):
                new_ex['sets'].append({
                    "type": "normal",
                    "weight_kg": target_weight,
                    "reps": target_reps,
                    "distance_meters": None,
                    "duration_seconds": None
                })
        
        else:
            for s in ex['sets']:
                new_ex['sets'].append({
                    "type": s['set_type'],
                    "weight_kg": s['weight_kg'],
                    "reps": s['reps'],
                    "distance_meters": s['distance_meters'],
                    "duration_seconds": s['duration_seconds']
                })
        
        updated_routine['exercises'].append(new_ex)

    try:
        url = f"{HEVY_API_URL}/routines/{routine_data['id']}"
        resp = requests.put(url, headers=get_headers(), json={"routine": updated_routine})
        resp.raise_for_status()
        print("Success! Routine updated.")
    except Exception as e:
        logger.error(f"API Update Failed: {e}")

if __name__ == "__main__":
    main()