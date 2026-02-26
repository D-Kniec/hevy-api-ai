import sys
import sqlite3
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

import pandas as pd
from dotenv import load_dotenv
from tqdm import tqdm
from pydantic import BaseModel, Field, ConfigDict

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

DB_PATH = BASE_DIR / "data" / "bronze_layer.db"
LOG_DIR = BASE_DIR / "logs"
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
        logging.FileHandler(LOG_DIR / "etl_gold.log"),
        TqdmLoggingHandler()
    ]
)
logger = logging.getLogger(__name__)

class RepRangeTarget(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    start: int
    end: int

class RoutineSetTarget(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    set_type: str = Field(alias="type")
    weight_kg: Optional[float] = None
    reps: Optional[int] = None
    distance_meters: Optional[float] = None
    duration_seconds: Optional[float] = None
    custom_metric: Optional[float] = None
    rep_range: Optional[RepRangeTarget] = None

class RoutineExerciseTarget(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    exercise_template_id: str
    superset_id: Optional[int] = None
    rest_seconds: Optional[int] = None
    notes: Optional[str] = None
    sets: List[RoutineSetTarget]

class RoutineUpdatePayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    title: str
    notes: Optional[str] = None
    exercises: List[RoutineExerciseTarget]

class PutRoutinesRequestBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    routine: RoutineUpdatePayload

SQL_GOLD_PROMPT = """
WITH current_indices AS (
    SELECT 
        routine_id, 
        exercise_template_id, 
        MIN(exercise_index) AS exercise_index,
        MAX(superset_id) AS superset_id
    FROM bronze_routine_details
    GROUP BY routine_id, exercise_template_id
)
SELECT 
    f.routine_id,
    r.routine_name,
    f.cycle_number,
    COALESCE(idx.exercise_index, f.exercise_index) as exercise_index,
    f.exercise_template_id,
    idx.superset_id,
    e.exercise_name,
    e.primary_muscle_group,
    e.progression_step_kg,
    f.set_index,
    f.set_type,
    f.weight_kg AS actual_weight_kg,
    f.reps AS actual_reps,
    f.rpe,
    f.planned_weight_kg,
    f.planned_reps,
    f.planned_rest,
    f.execution_status,
    f.diff_weight_kg,
    f.diff_reps
FROM silver_fact_workout_history f
LEFT JOIN silver_dim_exercise e 
    ON f.exercise_template_id = e.exercise_template_id
LEFT JOIN silver_dim_routine r 
    ON f.routine_id = r.routine_id
LEFT JOIN current_indices idx
    ON f.routine_id = idx.routine_id 
    AND f.exercise_template_id = idx.exercise_template_id
WHERE f.workout_id IS NOT NULL
ORDER BY 
    f.routine_id, 
    f.cycle_number ASC, 
    idx.exercise_index ASC, 
    f.exercise_template_id, 
    f.set_index;
"""

def drop_table_if_exists(connection: sqlite3.Connection, table_name: str) -> None:
    try:
        cursor = connection.cursor()
        cursor.execute(f'DROP TABLE IF EXISTS "{table_name}"')
        connection.commit()
    except Exception as error:
        logger.warning(f"Failed to drop table {table_name}: {error}")

def execute_gold_etl(database_path: Path) -> None:
    if not database_path.exists():
        logger.critical(f"Database NOT found at {database_path}")
        raise FileNotFoundError(f"Database not found at {database_path}")

    try:
        with sqlite3.connect(database_path) as connection:
            logger.info(f"Connected to DB at {database_path}")

            dataframe_gold = pd.read_sql_query(SQL_GOLD_PROMPT, connection)
            
            dataframe_gold['superset_id'] = pd.to_numeric(dataframe_gold['superset_id'], errors='coerce').astype('Int64')
            
            drop_table_if_exists(connection, "gold_prompt")
            dataframe_gold.to_sql("gold_prompt", connection, if_exists="replace", index=False)
            
            logger.info(f"Loaded gold_prompt: {len(dataframe_gold)} rows")

    except Exception as error:
        logger.error(f"ETL Fatal Error: {error}")
        raise

if __name__ == "__main__":
    execute_gold_etl(DB_PATH)
