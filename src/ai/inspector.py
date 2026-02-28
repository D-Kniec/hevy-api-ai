import sqlite3
import logging
from pathlib import Path
from typing import Optional, Dict, Any

def find_project_root() -> Path:
    current_file = Path(__file__).resolve()
    for parent in [current_file] + list(current_file.parents):
        if parent.name == "src":
            return parent.parent
    return current_file.parent.parent.parent

BASE_DIR = find_project_root()
DB_PATH = BASE_DIR / "data" / "bronze_layer.db"

logger = logging.getLogger(__name__)

def get_db_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection

def select_routine_from_database() -> Optional[Dict[str, Any]]:
    try:
        with get_db_connection() as connection:
            routines = connection.execute("""
                SELECT DISTINCT routine_id AS id, routine_name AS title 
                FROM gold_prompt 
                ORDER BY title
            """).fetchall()

        if not routines:
            logger.error("No routines found in gold_prompt.")
            return None

        print("\n--- Available Routines ---")
        for index, routine in enumerate(routines):
            print(f"{index + 1}. {routine['title']}")

        while True:
            try:
                choice = int(input("\nSelect Routine # to Update: "))
                if 1 <= choice <= len(routines):
                    return dict(routines[choice - 1])
                print("Invalid number.")
            except ValueError:
                print("Please enter a valid number.")
    except Exception as error:
        logger.error(f"Database error during routine selection: {error}")
        return None

def get_full_routine_data(routine_id: str) -> Optional[Dict[str, Any]]:
    with get_db_connection() as connection:
        records = connection.execute("""
            SELECT * FROM gold_prompt 
            WHERE routine_id = ? 
            ORDER BY cycle_number ASC, exercise_index ASC, exercise_template_id, set_index
        """, (routine_id,)).fetchall()

        if not records:
            return None

        routine_data = {
            "id": routine_id,
            "title": records[0]["routine_name"],
            "exercises": {}
        }

        for row in records:
            exercise_id = row["exercise_template_id"]
            if exercise_id not in routine_data["exercises"]:
                routine_data["exercises"][exercise_id] = {
                    "exercise_template_id": exercise_id,
                    "exercise_index": row["exercise_index"],
                    "superset_id": row["superset_id"],
                    "title": row["exercise_name"],
                    "primary_muscle_group": row["primary_muscle_group"],
                    "progression_step_kg": row["progression_step_kg"],
                    "rest_seconds": row["planned_rest"],
                    "history": {}
                }

            cycle = row["cycle_number"]
            if cycle not in routine_data["exercises"][exercise_id]["history"]:
                routine_data["exercises"][exercise_id]["history"][cycle] = []

            routine_data["exercises"][exercise_id]["history"][cycle].append({
                "set_index": row["set_index"],
                "set_type": row["set_type"],
                "actual_weight_kg": row["actual_weight_kg"],
                "actual_reps": row["actual_reps"],
                "rpe": row["rpe"],
                "planned_weight_kg": row["planned_weight_kg"],
                "planned_reps": row["planned_reps"],
                "execution_status": row["execution_status"],
                "diff_weight_kg": row["diff_weight_kg"],
                "diff_reps": row["diff_reps"]
            })

        formatted_exercises = []
        for exercise_id, exercise_data in routine_data["exercises"].items():
            formatted_history = []
            for cycle in sorted(exercise_data["history"].keys()):
                formatted_history.append({
                    "cycle": cycle,
                    "sets": exercise_data["history"][cycle]
                })
            exercise_data["history"] = formatted_history
            formatted_exercises.append(exercise_data)

        formatted_exercises.sort(
            key=lambda x: x["exercise_index"] if x.get("exercise_index") is not None else float("inf")
        )
        routine_data["exercises"] = formatted_exercises
        return routine_data
