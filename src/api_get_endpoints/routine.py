import os
import sqlite3
import logging
import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Union

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
        logging.FileHandler("etl_routines.log"),
        TqdmLoggingHandler()
    ]
)
logger = logging.getLogger(__name__)

class RepRangeModel(BaseModel):
    start: Optional[float] = None
    end: Optional[float] = None
    
    model_config = ConfigDict(populate_by_name=True)

class SetModel(BaseModel):
    index: int
    set_type: str = Field(alias='type')
    weight_kg: Optional[float] = None
    reps: Optional[int] = None
    rep_range: Optional[RepRangeModel] = None
    distance_meters: Optional[float] = None
    duration_seconds: Optional[float] = None
    rpe: Optional[float] = None
    custom_metric: Optional[float] = None
    
    model_config = ConfigDict(populate_by_name=True)

class ExerciseModel(BaseModel):
    index: int
    title: str
    notes: Optional[str] = None
    rest_seconds: Optional[int] = None
    exercise_template_id: str
    supersets_id: Optional[int] = None
    sets: List[SetModel] = []
    
    model_config = ConfigDict(populate_by_name=True)

class RoutineModel(BaseModel):
    id: str
    title: str
    folder_id: Optional[Union[int, str]] = None
    updated_at: Optional[str] = None
    created_at: Optional[str] = None
    exercises: List[ExerciseModel] = []
    
    model_config = ConfigDict(populate_by_name=True)

def fetch_and_flatten_routines() -> List[Dict[str, Any]]:
    if not HEVY_API_KEY:
        logger.critical("Missing HEVY_API_KEY")
        raise ValueError("API Key not found")

    headers = {"api-key": HEVY_API_KEY}
    flattened_rows = []
    page = 1
    page_count = 1
    
    with requests.Session() as session:
        session.headers.update(headers)
        
        try:
            init_resp = session.get(f"{BASE_URL}/routines", params={"page": 1, "pageSize": 10})
            init_resp.raise_for_status()
            data = init_resp.json()
            page_count = max(1, data.get('page_count', 1))
            logger.info(f"Total pages to fetch: {page_count}")
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            return []

        pbar = tqdm(total=page_count, desc="Fetching Routines")
        
        while page <= page_count:
            try:
                response = session.get(
                    f"{BASE_URL}/routines", 
                    params={"page": page, "pageSize": 10},
                    timeout=15
                )
                
                if response.status_code == 404:
                    break

                response.raise_for_status()
                data = response.json()
                
                routines = data.get('routines', [])

                if not routines:
                    break

                for r in routines:
                    try:
                        routine = RoutineModel(**r)
                        
                        base_row = {
                            "routine_id": routine.id,
                            "title": routine.title,
                            "folder_id": routine.folder_id,
                            "updated_at": routine.updated_at,
                            "created_at": routine.created_at,
                            "ingestion_timestamp": datetime.datetime.now().isoformat()
                        }

                        if not routine.exercises:
                            flattened_rows.append(base_row)
                            continue

                        for ex in routine.exercises:
                            ex_row = base_row.copy()
                            ex_row.update({
                                "exercise_index": ex.index,
                                "exercise_title": ex.title,
                                "exercise_notes": ex.notes,
                                "rest_seconds": ex.rest_seconds,
                                "exercise_template_id": ex.exercise_template_id,
                                "supersets_id": ex.supersets_id
                            })

                            if not ex.sets:
                                flattened_rows.append(ex_row)
                                continue

                            for s in ex.sets:
                                final_row = ex_row.copy()
                                
                                rep_start = s.rep_range.start if s.rep_range else None
                                rep_end = s.rep_range.end if s.rep_range else None

                                final_row.update({
                                    "set_index": s.index,
                                    "set_type": s.set_type,
                                    "weight_kg": s.weight_kg,
                                    "reps": s.reps,
                                    "rep_range_start": rep_start,
                                    "rep_range_end": rep_end,
                                    "distance_meters": s.distance_meters,
                                    "duration_seconds": s.duration_seconds,
                                    "rpe": s.rpe,
                                    "custom_metric": s.custom_metric
                                })
                                flattened_rows.append(final_row)

                    except ValidationError as ve:
                        logger.warning(f"Validation Error in routine {r.get('id')}: {ve}")

                page += 1
                pbar.update(1)

            except requests.RequestException as e:
                logger.error(f"Network Error on page {page}: {e}")
                break
        
        pbar.close()

    return flattened_rows

def save_to_db(rows: List[Dict[str, Any]], db_path: Path):
    if not rows:
        logger.warning("No data to save.")
        return

    db_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    
    try:
        with sqlite3.connect(db_path) as conn:
            df.to_sql('bronze.Routine', conn, if_exists='replace', index=False)
            
        logger.info(f"SUCCESS: Saved {len(df)} records to 'bronze.Routine' in {db_path.name}")
    except Exception as e:
        logger.error(f"Database Save Error: {e}")

if __name__ == "__main__":
    data = fetch_and_flatten_routines()
    save_to_db(data, DB_PATH)