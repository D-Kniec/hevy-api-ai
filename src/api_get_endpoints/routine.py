import os
import sqlite3
import logging
import datetime
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional, Union

import requests
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError, ConfigDict
from tqdm import tqdm

BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_PATH = BASE_DIR / '.env'
load_dotenv(ENV_PATH)

HEVY_API_KEY = os.getenv("HEVY_API_KEY")
BASE_URL = "https://api.hevyapp.com/v1"
DB_PATH = BASE_DIR / "data" / "bronze_layer.db"
TABLE_NAME = "bronze_Routine_SCD2"

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

def generate_row_hash(df: pd.DataFrame, exclude_cols: List[str]) -> pd.Series:
    df_copy = df.drop(columns=exclude_cols, errors='ignore').copy()
    
    for col in df_copy.columns:
        df_copy[col] = df_copy[col].astype(str).fillna('')
    
    row_strings = df_copy.apply(lambda x: ''.join(x.values), axis=1)
    return row_strings.apply(lambda x: hashlib.md5(x.encode('utf-8')).hexdigest())

def initialize_db_if_not_exists(conn, table_name):
    cursor = conn.cursor()
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            routine_id TEXT,
            title TEXT,
            folder_id TEXT,
            updated_at TEXT,
            created_at TEXT,
            exercise_index INTEGER,
            exercise_title TEXT,
            exercise_notes TEXT,
            rest_seconds INTEGER,
            exercise_template_id TEXT,
            supersets_id INTEGER,
            set_index INTEGER,
            set_type TEXT,
            weight_kg REAL,
            reps INTEGER,
            rep_range_start REAL,
            rep_range_end REAL,
            distance_meters REAL,
            duration_seconds REAL,
            rpe REAL,
            custom_metric REAL,
            scd_valid_from TEXT,
            scd_valid_to TEXT,
            scd_is_current INTEGER,
            scd_hash TEXT
        )
    """)
    conn.commit()

def process_scd2(rows: List[Dict[str, Any]], db_path: Path):
    if not rows:
        logger.warning("No data fetched from API.")
        return

    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    current_time = datetime.datetime.now().isoformat()
    business_keys = ['routine_id', 'exercise_index', 'set_index']
    
    df_staging = pd.DataFrame(rows)
    df_staging = df_staging.where(pd.notnull(df_staging), None)
    
    df_staging['scd_hash'] = generate_row_hash(df_staging, exclude_cols=[])

    with sqlite3.connect(db_path) as conn:
        initialize_db_if_not_exists(conn, TABLE_NAME)
        
        try:
            df_current = pd.read_sql(
                f"SELECT * FROM {TABLE_NAME} WHERE scd_is_current = 1", 
                conn
            )
        except Exception:
            df_current = pd.DataFrame()

    if df_current.empty:
        logger.info("Target table empty or no active records. performing full load.")
        df_staging['scd_valid_from'] = current_time
        df_staging['scd_valid_to'] = None
        df_staging['scd_is_current'] = 1
        
        with sqlite3.connect(db_path) as conn:
            df_staging.to_sql(TABLE_NAME, conn, if_exists='append', index=False)
        return

    df_merged = pd.merge(
        df_staging,
        df_current[business_keys + ['scd_hash']],
        on=business_keys,
        how='outer',
        suffixes=('_new', '_cur'),
        indicator=True
    )

    new_records = df_merged[df_merged['_merge'] == 'left_only'].copy()
    
    changed_records = df_merged[
        (df_merged['_merge'] == 'both') & 
        (df_merged['scd_hash_new'] != df_merged['scd_hash_cur'])
    ].copy()
    
    deleted_records = df_merged[df_merged['_merge'] == 'right_only'].copy()

    unchanged_count = len(df_merged[
        (df_merged['_merge'] == 'both') & 
        (df_merged['scd_hash_new'] == df_merged['scd_hash_cur'])
    ])

    records_to_insert = []
    keys_to_expire = []

    if not new_records.empty:
        cols = [c for c in new_records.columns if c.endswith('_new')]
        mapping = {c: c.replace('_new', '') for c in cols}
        df_new = new_records[cols].rename(columns=mapping)
        df_new['scd_valid_from'] = current_time
        df_new['scd_valid_to'] = None
        df_new['scd_is_current'] = 1
        records_to_insert.append(df_new)

    if not changed_records.empty:
        keys_to_expire.extend(changed_records[business_keys].to_dict('records'))
        
        cols = [c for c in changed_records.columns if c.endswith('_new')]
        mapping = {c: c.replace('_new', '') for c in cols}
        df_changed = changed_records[cols].rename(columns=mapping)
        df_changed['scd_valid_from'] = current_time
        df_changed['scd_valid_to'] = None
        df_changed['scd_is_current'] = 1
        records_to_insert.append(df_changed)

    if not deleted_records.empty:
        keys_to_expire.extend(deleted_records[business_keys].to_dict('records'))

    logger.info(f"SCD2 Stats - New: {len(new_records)}, Changed: {len(changed_records)}, Deleted: {len(deleted_records)}, Unchanged: {unchanged_count}")

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        if keys_to_expire:
            cursor.executemany(f"""
                UPDATE {TABLE_NAME}
                SET scd_valid_to = ?, scd_is_current = 0
                WHERE routine_id = ? AND exercise_index = ? AND set_index = ? AND scd_is_current = 1
            """, [(current_time, k['routine_id'], k['exercise_index'], k['set_index']) for k in keys_to_expire])
            
        if records_to_insert:
            df_final_insert = pd.concat(records_to_insert, ignore_index=True)
            df_final_insert.to_sql(TABLE_NAME, conn, if_exists='append', index=False)
            
        conn.commit()

if __name__ == "__main__":
    data = fetch_and_flatten_routines()
    process_scd2(data, DB_PATH)