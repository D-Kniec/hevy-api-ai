import os
import sys
import json
import sqlite3
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Tuple

import requests
import pandas as pd
from dotenv import load_dotenv
from pydantic import ValidationError
from tqdm import tqdm

def find_project_root() -> Path:
    current_file = Path(__file__).resolve()
    for parent in [current_file] + list(current_file.parents):
        if parent.name == "src":
            return parent.parent
    return current_file.parent.parent.parent

BASE_DIR = find_project_root()
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.api.client import HevyAPIClient
from src.api.schemas import ExerciseTemplateModel, RoutineModel, WorkoutModel

ENV_PATH = BASE_DIR / ".env"
if not ENV_PATH.exists():
    ENV_PATH = BASE_DIR / "src" / ".env"
load_dotenv(ENV_PATH)

DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "bronze_layer.db"
LOG_DIR = BASE_DIR / "logs"

DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

class TqdmLoggingHandler(logging.Handler):
    def __init__(self, level: int = logging.NOTSET) -> None:
        super().__init__(level)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            log_message = self.format(record)
            tqdm.write(log_message)
            self.flush()
        except Exception:
            self.handleError(record)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "etl_bronze.log"),
        TqdmLoggingHandler()
    ]
)
logger = logging.getLogger(__name__)

def fetch_templates(api_client: HevyAPIClient) -> List[Dict[str, Any]]:
    extracted_rows = []
    page = 1

    try:
        initial_response = api_client.get("exercise_templates", {"page": 1, "pageSize": 100})
        page_count = max(1, initial_response.json().get("page_count", 1))
    except Exception as error:
        logger.error(f"Template Init Failed: {error}")
        return []

    with tqdm(total=page_count, desc="Fetching Templates") as progress_bar:
        while page <= page_count:
            try:
                response = api_client.get("exercise_templates", {"page": page, "pageSize": 100})
                templates = response.json().get("exercise_templates", [])
                
                if not templates:
                    break

                ingestion_time = datetime.now(timezone.utc).isoformat()
                for template_data in templates:
                    try:
                        model = ExerciseTemplateModel(**template_data)
                        extracted_rows.append({
                            "id": model.id,
                            "title": model.title,
                            "type": model.exercise_type,
                            "primary_muscle_group": model.primary_muscle_group,
                            "secondary_muscle_groups": json.dumps(model.secondary_muscle_groups),
                            "is_custom": model.is_custom,
                            "ingestion_timestamp": ingestion_time
                        })
                    except ValidationError:
                        pass
                
                page += 1
                progress_bar.update(1)
            except requests.exceptions.HTTPError as error:
                if error.response.status_code == 404:
                    break
                logger.error(f"Template Error Page {page}: {error}")
                break
            except Exception as error:
                logger.error(f"Template Error Page {page}: {error}")
                break
                
    return extracted_rows

def fetch_routines(api_client: HevyAPIClient) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    routines_data = []
    details_data = []
    page = 1

    try:
        initial_response = api_client.get("routines", {"page": 1, "pageSize": 10})
        page_count = max(1, initial_response.json().get("page_count", 1))
    except Exception as error:
        logger.error(f"Routine Init Failed: {error}")
        return [], []

    with tqdm(total=page_count, desc="Fetching Routines") as progress_bar:
        while page <= page_count:
            try:
                response = api_client.get("routines", {"page": page, "pageSize": 10})
                routines = response.json().get("routines", [])
                
                if not routines:
                    break

                ingestion_time = datetime.now(timezone.utc).isoformat()
                for routine_data in routines:
                    try:
                        model = RoutineModel(**routine_data)
                        routines_data.append({
                            "routine_id": model.id,
                            "title": model.title,
                            "folder_id": model.folder_id,
                            "updated_at": model.updated_at,
                            "created_at": model.created_at,
                            "ingestion_timestamp": ingestion_time
                        })
                        for exercise in model.exercises:
                            for exercise_set in exercise.sets:
                                rep_start = exercise_set.rep_range.start if exercise_set.rep_range else None
                                rep_end = exercise_set.rep_range.end if exercise_set.rep_range else None
                                details_data.append({
                                    "routine_id": model.id,
                                    "exercise_index": exercise.index,
                                    "exercise_title": exercise.title,
                                    "exercise_notes": exercise.notes,
                                    "rest_seconds": exercise.rest_seconds,
                                    "exercise_template_id": exercise.exercise_template_id,
                                    "superset_id": exercise.superset_id,
                                    "set_index": exercise_set.index,
                                    "set_type": exercise_set.set_type,
                                    "weight_kg": exercise_set.weight_kg,
                                    "reps": exercise_set.reps,
                                    "rep_range_start": rep_start,
                                    "rep_range_end": rep_end,
                                    "distance_meters": exercise_set.distance_meters,
                                    "duration_seconds": exercise_set.duration_seconds,
                                    "rpe": exercise_set.rpe,
                                    "custom_metric": exercise_set.custom_metric,
                                    "ingestion_timestamp": ingestion_time
                                })
                    except ValidationError:
                        pass
                page += 1
                progress_bar.update(1)
            except requests.exceptions.HTTPError as error:
                if error.response.status_code == 404:
                    break
                logger.error(f"Routine Error Page {page}: {error}")
                break
            except Exception as error:
                logger.error(f"Routine Error Page {page}: {error}")
                break

    return routines_data, details_data

def fetch_workouts(api_client: HevyAPIClient) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    workouts_data = []
    exercises_data = []
    sets_data = []
    page = 1

    try:
        initial_response = api_client.get("workouts", {"page": 1, "pageSize": 10})
        page_count = max(1, initial_response.json().get("page_count", 1))
    except Exception as error:
        logger.error(f"Workout Init Failed: {error}")
        return [], [], []

    with tqdm(total=page_count, desc="Fetching Workouts") as progress_bar:
        while page <= page_count:
            try:
                response = api_client.get("workouts", {"page": page, "pageSize": 10})
                workouts = response.json().get("workouts", [])
                
                if not workouts:
                    break

                ingestion_time = datetime.now(timezone.utc).isoformat()
                for workout_data in workouts:
                    try:
                        model = WorkoutModel(**workout_data)
                        workouts_data.append({
                            "workout_id": model.id,
                            "title": model.title,
                            "description": model.description,
                            "start_time": model.start_time,
                            "end_time": model.end_time,
                            "updated_at": model.updated_at,
                            "created_at": model.created_at,
                            "routine_id": model.routine_id,
                            "ingestion_timestamp": ingestion_time
                        })
                        for exercise in model.exercises:
                            exercises_data.append({
                                "workout_id": model.id,
                                "exercise_index": exercise.index,
                                "title": exercise.title,
                                "notes": exercise.notes,
                                "exercise_template_id": exercise.exercise_template_id,
                                "superset_id": exercise.superset_id,
                                "ingestion_timestamp": ingestion_time
                            })
                            for exercise_set in exercise.sets:
                                sets_data.append({
                                    "workout_id": model.id,
                                    "exercise_index": exercise.index,
                                    "set_index": exercise_set.index,
                                    "set_type": exercise_set.set_type,
                                    "weight_kg": exercise_set.weight_kg,
                                    "reps": exercise_set.reps,
                                    "distance_meters": exercise_set.distance_meters,
                                    "duration_seconds": exercise_set.duration_seconds,
                                    "rpe": exercise_set.rpe,
                                    "custom_metric": exercise_set.custom_metric,
                                    "ingestion_timestamp": ingestion_time
                                })
                    except ValidationError:
                        pass
                page += 1
                progress_bar.update(1)
            except requests.exceptions.HTTPError as error:
                if error.response.status_code == 404:
                    break
                logger.error(f"Workout Error Page {page}: {error}")
                break
            except Exception as error:
                logger.error(f"Workout Error Page {page}: {error}")
                break

    return workouts_data, exercises_data, sets_data

def save_to_database(data_map: Dict[str, List[Dict[str, Any]]], database_path: Path) -> None:
    if not any(data_map.values()):
        logger.warning("No data extracted.")
        return

    try:
        with sqlite3.connect(database_path) as connection:
            for table_name, rows in data_map.items():
                if rows:
                    dataframe = pd.DataFrame(rows)
                    dataframe.to_sql(table_name, connection, if_exists="replace", index=False)
                    logger.info(f"SUCCESS: Saved {len(dataframe)} rows to '{table_name}'")
    except sqlite3.Error as error:
        logger.error(f"Database Error: {error}")

def execute_bronze_etl() -> None:
    try:
        api_client = HevyAPIClient()
    except ValueError as error:
        logger.critical(str(error))
        sys.exit(1)

    templates = fetch_templates(api_client)
    routines, routine_details = fetch_routines(api_client)
    workouts, workouts_exercises, workouts_sets = fetch_workouts(api_client)

    tables_to_save = {
        "bronze_exercise_templates": templates,
        "bronze_routines": routines,
        "bronze_routine_details": routine_details,
        "bronze_workouts": workouts,
        "bronze_workout_exercises": workouts_exercises,
        "bronze_workout_sets": workouts_sets
    }

    save_to_database(tables_to_save, DB_PATH)

if __name__ == "__main__":
    execute_bronze_etl()
