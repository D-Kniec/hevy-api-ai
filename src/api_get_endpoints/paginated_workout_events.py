import os
import sqlite3
import logging
import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

import requests
import pandas as pd
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError, ConfigDict
from tqdm import tqdm

BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_PATH = BASE_DIR / '.env'
load_dotenv(ENV_PATH)

HEVY_API_KEY = os.getenv("HEVY_API_KEY")
BASE_URL = "https://api.hevyapp.com/v1"
DB_PATH = BASE_DIR / "data" / "hevy.db"

class TqdmLoggingHandler(logging.Handler):
    def __init__(self, level=logging.NOTSET):
        super().__init__(level)

    def emit(self, record):
        try:
            msg = self.format(record)
            tqdm.write(msg)
            self.flush()
        except Exception:
            self.handleError(record)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("etl_paginated_events.log"),
        TqdmLoggingHandler()
    ]
)
logger = logging.getLogger(__name__)

class SetModel(BaseModel):
    index: int
    set_type: str = Field(alias='type')
    weight_kg: Optional[float] = None
    reps: Optional[int] = None
    distance_meters: Optional[float] = None
    duration_seconds: Optional[float] = None
    rpe: Optional[float] = None
    custom_metric: Optional[float] = None
    
    model_config = ConfigDict(populate_by_name=True)

class ExerciseModel(BaseModel):
    index: int
    title: str
    notes: Optional[str] = None
    exercise_template_id: str
    supersets_id: Optional[int] = None
    sets: List[SetModel] = []
    
    model_config = ConfigDict(populate_by_name=True)

class WorkoutModel(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    created_at: Optional[str] = None
    routine_id: Optional[str] = None
    exercises: List[ExerciseModel] = []
    
    model_config = ConfigDict(populate_by_name=True)

def fetch_and_flatten_pipeline() -> List[Dict[str, Any]]:
    if not HEVY_API_KEY:
        logger.critical("Missing HEVY_API_KEY")
        raise ValueError("API Key not found")

    headers = {"api-key": HEVY_API_KEY}
    all_flat_rows = []
    page = 1
    page_count = 1
    
    with requests.Session() as session:
        session.headers.update(headers)
        
        try:
            init_resp = session.get(f"{BASE_URL}/workouts", params={"page": 1, "pageSize": 10})
            init_resp.raise_for_status()
            data = init_resp.json()
            page_count = data.get('page_count', 1)
            logger.info(f"Total pages to fetch: {page_count}")
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            return []

        pbar = tqdm(total=page_count, desc="Fetching Workouts")
        
        while page <= page_count:
            try:
                response = session.get(
                    f"{BASE_URL}/workouts", 
                    params={"page": page, "pageSize": 10},
                    timeout=15
                )
                
                if response.status_code == 404:
                    logger.warning(f"Page {page} not found. Stopping.")
                    break

                response.raise_for_status()
                data = response.json()
                
                page_count = data.get('page_count', page_count)
                workouts = data.get('workouts', [])

                if not workouts:
                    logger.info(f"No workouts on page {page}. Stopping.")
                    break

                for w in workouts:
                    try:
                        workout = WorkoutModel(**w)
                        
                        workout_meta = {
                            "workout_id": workout.id,
                            "workout_title": workout.title,
                            "description": workout.description,
                            "start_time": workout.start_time,
                            "end_time": workout.end_time,
                            "created_at": workout.created_at,
                            "routine_id": workout.routine_id,
                            "ingestion_timestamp": datetime.datetime.now().isoformat()
                        }

                        if not workout.exercises:
                            all_flat_rows.append(workout_meta)
                            continue

                        for ex in workout.exercises:
                            exercise_meta = workout_meta.copy()
                            exercise_meta.update({
                                "exercise_title": ex.title,
                                "exercise_template_id": ex.exercise_template_id,
                                "superset_id": ex.supersets_id,
                                "exercise_notes": ex.notes,
                                "exercise_index": ex.index
                            })

                            if not ex.sets:
                                all_flat_rows.append(exercise_meta)
                                continue

                            for s in ex.sets:
                                row = exercise_meta.copy()
                                row.update({
                                    "set_index": s.index,
                                    "set_type": s.set_type,
                                    "weight_kg": s.weight_kg,
                                    "reps": s.reps,
                                    "rpe": s.rpe,
                                    "distance_meters": s.distance_meters,
                                    "duration_seconds": s.duration_seconds,
                                    "custom_metric": s.custom_metric
                                })
                                all_flat_rows.append(row)

                    except ValidationError as ve:
                        logger.warning(f"Validation Error in workout {w.get('id')}: {ve}")

                pbar.update(1)
                page += 1

            except requests.RequestException as e:
                logger.error(f"Network Error on page {page}: {e}")
                break
        
        pbar.close()

    return all_flat_rows

def save_to_db(rows: List[Dict[str, Any]], db_path: Path):
    if not rows:
        logger.warning("No data to save.")
        return

    db_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    
    try:
        with sqlite3.connect(db_path) as conn:
            df.to_sql('bronze.PaginatedWorkoutEvents', conn, if_exists='replace', index=False)
            
        logger.info(f"SUCCESS: Saved {len(df)} records to 'bronze.PaginatedWorkoutEvents' in {db_path.name}")
    except Exception as e:
        logger.error(f"Database Save Error: {e}")

if __name__ == "__main__":
    data = fetch_and_flatten_pipeline()
    save_to_db(data, DB_PATH)