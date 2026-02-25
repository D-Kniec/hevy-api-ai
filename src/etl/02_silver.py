import os
import sys
import sqlite3
import logging
import hashlib
import ast
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List

import pandas as pd
from dotenv import load_dotenv
from tqdm import tqdm

pd.set_option('future.no_silent_downcasting', True)

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
        logging.FileHandler(LOG_DIR / "etl_silver.log"),
        TqdmLoggingHandler()
    ]
)
logger = logging.getLogger(__name__)

def load_progression_dictionary() -> Dict[str, float]:
    possible_paths = [
        BASE_DIR / "data" / "proggresion.py",
        BASE_DIR / "data" / "progression.py",
        BASE_DIR / "src" / "core" / "progression.py",
        BASE_DIR / "src" / "core" / "proggresion.py"
    ]
    
    file_path = None
    for path in possible_paths:
        if path.exists():
            file_path = path
            break
            
    if not file_path:
        logger.warning("Progression file not found in any standard location.")
        return {}
    
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            tree = ast.parse(file.read())
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == 'PROGRESSION':
                        if isinstance(node.value, ast.Dict):
                            progression_dict = {}
                            for key, value in zip(node.value.keys, node.value.values):
                                if isinstance(key, ast.Constant) and isinstance(value, ast.Constant):
                                    progression_dict[key.value] = float(value.value)
                            return progression_dict
    except Exception as error:
        logger.error(f"Failed to load progression file from {file_path}: {error}")
    
    return {}

def generate_row_hash(dataframe: pd.DataFrame, exclude_cols: List[str]) -> pd.Series:
    dataframe_copy = dataframe.drop(columns=exclude_cols, errors="ignore").copy()
    for column in dataframe_copy.columns:
        dataframe_copy[column] = dataframe_copy[column].astype(str).fillna("")
    row_strings = dataframe_copy.apply(lambda row: "".join(row.values), axis=1)
    return row_strings.apply(lambda concatenated_string: hashlib.md5(concatenated_string.encode("utf-8")).hexdigest())

def initialize_scd2_table(connection: sqlite3.Connection, table_name: str) -> None:
    cursor = connection.cursor()
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
            superset_id INTEGER,
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
    connection.commit()

def process_routine_scd2(connection: sqlite3.Connection) -> None:
    cursor = connection.cursor()
    cursor.execute("PRAGMA table_info(silver_dim_routine_scd2)")
    columns_info = cursor.fetchall()
    if columns_info:
        existing_columns = [col[1] for col in columns_info]
        if "supersets_id" in existing_columns:
            logger.info("Found outdated schema in silver_dim_routine_scd2 (supersets_id). Dropping to recreate.")
            cursor.execute("DROP TABLE silver_dim_routine_scd2")
            connection.commit()

    try:
        headers_df = pd.read_sql_query("SELECT * FROM bronze_routines", connection)
        details_df = pd.read_sql_query("SELECT * FROM bronze_routine_details", connection)
    except Exception as e:
        logger.warning(f"Could not read bronze routines tables for SCD2: {e}")
        return

    if headers_df.empty or details_df.empty:
        logger.warning("No routine data found to process for SCD2.")
        return

    dataframe_staging = pd.merge(
        details_df,
        headers_df[["routine_id", "title", "folder_id", "updated_at", "created_at"]],
        on="routine_id",
        how="left"
    )

    columns_to_drop = [col for col in dataframe_staging.columns if "ingestion_timestamp" in col]
    if columns_to_drop:
        dataframe_staging.drop(columns=columns_to_drop, inplace=True)

    if "supersets_id" in dataframe_staging.columns:
        dataframe_staging.rename(columns={"supersets_id": "superset_id"}, inplace=True)

    dataframe_staging["routine_id"] = dataframe_staging["routine_id"].astype(str)
    dataframe_staging["exercise_index"] = pd.to_numeric(dataframe_staging.get("exercise_index"), errors="coerce").astype("Int64")
    dataframe_staging["set_index"] = pd.to_numeric(dataframe_staging.get("set_index"), errors="coerce").astype("Int64")
    
    if "superset_id" in dataframe_staging.columns:
        dataframe_staging["superset_id"] = pd.to_numeric(dataframe_staging["superset_id"], errors="coerce").astype("Int64")

    current_time = datetime.now(timezone.utc).isoformat()
    business_keys = ["routine_id", "exercise_index", "set_index"]
    target_table = "silver_dim_routine_scd2"

    dataframe_staging = dataframe_staging.where(pd.notnull(dataframe_staging), None)
    dataframe_staging["scd_hash"] = generate_row_hash(dataframe_staging, exclude_cols=[])

    initialize_scd2_table(connection, target_table)

    try:
        dataframe_current = pd.read_sql_query(f"SELECT * FROM {target_table} WHERE scd_is_current = 1", connection)
    except sqlite3.Error:
        dataframe_current = pd.DataFrame()

    if not dataframe_current.empty:
        dataframe_current["routine_id"] = dataframe_current["routine_id"].astype(str)
        dataframe_current["exercise_index"] = pd.to_numeric(dataframe_current.get("exercise_index"), errors="coerce").astype("Int64")
        dataframe_current["set_index"] = pd.to_numeric(dataframe_current.get("set_index"), errors="coerce").astype("Int64")
        if "superset_id" in dataframe_current.columns:
            dataframe_current["superset_id"] = pd.to_numeric(dataframe_current["superset_id"], errors="coerce").astype("Int64")

    if dataframe_current.empty:
        logger.info("Target SCD2 table empty. Performing full load.")
        dataframe_staging["scd_valid_from"] = current_time
        dataframe_staging["scd_valid_to"] = None
        dataframe_staging["scd_is_current"] = 1
        dataframe_staging.to_sql(target_table, connection, if_exists="append", index=False)
        return

    dataframe_merged = pd.merge(
        dataframe_staging,
        dataframe_current[business_keys + ["scd_hash"]],
        on=business_keys,
        how="outer",
        suffixes=("_new", "_cur"),
        indicator=True
    )

    new_records = dataframe_merged[dataframe_merged["_merge"] == "left_only"].copy()
    changed_records = dataframe_merged[
        (dataframe_merged["_merge"] == "both") &
        (dataframe_merged["scd_hash_new"] != dataframe_merged["scd_hash_cur"])
    ].copy()
    deleted_records = dataframe_merged[dataframe_merged["_merge"] == "right_only"].copy()
    unchanged_count = len(dataframe_merged[
        (dataframe_merged["_merge"] == "both") &
        (dataframe_merged["scd_hash_new"] == dataframe_merged["scd_hash_cur"])
    ])

    records_to_insert = []
    keys_to_expire = []

    def format_for_insert(dataframe: pd.DataFrame) -> pd.DataFrame:
        df_clean = dataframe.drop(columns=["scd_hash_cur", "_merge"], errors="ignore")
        if "scd_hash_new" in df_clean.columns:
            df_clean = df_clean.rename(columns={"scd_hash_new": "scd_hash"})
        df_clean["scd_valid_from"] = current_time
        df_clean["scd_valid_to"] = None
        df_clean["scd_is_current"] = 1
        return df_clean

    if not new_records.empty:
        records_to_insert.append(format_for_insert(new_records))

    if not changed_records.empty:
        keys_to_expire.extend(changed_records[business_keys].to_dict("records"))
        records_to_insert.append(format_for_insert(changed_records))

    if not deleted_records.empty:
        keys_to_expire.extend(deleted_records[business_keys].to_dict("records"))

    logger.info(f"SCD2 Stats - New: {len(new_records)}, Changed: {len(changed_records)}, Deleted: {len(deleted_records)}, Unchanged: {unchanged_count}")

    if keys_to_expire:
        cursor.executemany(f"""
            UPDATE {target_table}
            SET scd_valid_to = ?, scd_is_current = 0
            WHERE routine_id = ? AND exercise_index = ? AND set_index = ? AND scd_is_current = 1
        """, [(current_time, key["routine_id"], key["exercise_index"], key["set_index"]) for key in keys_to_expire])

    if records_to_insert:
        dataframe_final_insert = pd.concat(records_to_insert, ignore_index=True)
        dataframe_final_insert.to_sql(target_table, connection, if_exists="append", index=False)

    connection.commit()

SQL_DIM_ROUTINE = """
SELECT 
    routine_id,
    MAX(title) AS routine_name,
    MAX(folder_id) AS folder_id,
    MIN(created_at) AS created_at,
    MAX(updated_at) AS last_updated_at,
    COUNT(DISTINCT exercise_template_id) AS unique_exercises_count,
    COUNT(DISTINCT exercise_index) AS total_exercises_count,
    COUNT(DISTINCT set_index) AS total_sets_count
FROM silver_dim_routine_scd2
GROUP BY 
    routine_id;
"""

SQL_FACT_WORKOUT_HISTORY = """
WITH actual AS (
    SELECT 
        w.workout_id, 
        w.routine_id,
        w.start_time, 
        w.end_time,
        w.updated_at, 
        e.exercise_template_id, 
        s.exercise_index,
        s.set_index, 
        COALESCE(s.set_type, 'normal') AS set_type, 
        s.weight_kg,
        s.reps,
        s.distance_meters, 
        s.duration_seconds, 
        COALESCE(s.rpe, 7) AS rpe, 
        s.custom_metric
    FROM bronze_workout_sets s
    JOIN bronze_workouts w ON s.workout_id = w.workout_id
    JOIN bronze_workout_exercises e ON s.workout_id = e.workout_id AND s.exercise_index = e.exercise_index
    WHERE w.routine_id IS NOT NULL
),
workout_headers AS (
    SELECT DISTINCT 
        workout_id, 
        routine_id, 
        start_time
    FROM actual
),
applicable_plan AS (
    SELECT 
        wh.workout_id,
        wh.start_time AS workout_start_time,
        p.updated_at,
        p.routine_id,
        p.folder_id,
        p.rest_seconds AS planned_rest,
        p.exercise_template_id,
        p.exercise_index,
        p.set_index,
        COALESCE(p.set_type, 'normal') AS set_type, 
        p.weight_kg AS planned_weight_kg, 
        p.reps AS planned_reps,
        p.distance_meters AS planned_distance_meters, 
        p.duration_seconds AS planned_duration_seconds, 
        p.custom_metric AS planned_custom_metric
    FROM workout_headers wh
    INNER JOIN silver_dim_routine_scd2 p 
        ON wh.routine_id = p.routine_id
        AND wh.start_time >= p.scd_valid_from 
        AND (wh.start_time < p.scd_valid_to OR p.scd_valid_to IS NULL)
)
SELECT 
    COALESCE(a.workout_id, p.workout_id) AS workout_id,
    COALESCE(a.routine_id, p.routine_id) AS routine_id,
    COALESCE(a.exercise_template_id, p.exercise_template_id) AS exercise_template_id,
    COALESCE(a.exercise_index, p.exercise_index) AS exercise_index,
    p.folder_id,

    DENSE_RANK() OVER (PARTITION BY COALESCE(a.exercise_template_id, p.exercise_template_id) ORDER BY COALESCE(a.start_time, p.workout_start_time)) AS cycle_number,
    COALESCE(a.set_type, p.set_type) AS set_type,
    COALESCE(a.set_index, p.set_index) AS set_index,

    CASE 
        WHEN a.workout_id IS NULL THEN 'Skipped'
        WHEN p.routine_id IS NULL THEN 'Unplanned'
        WHEN COALESCE(a.weight_kg, 0) > COALESCE(p.planned_weight_kg, 0) AND COALESCE(a.reps, 0) > COALESCE(p.planned_reps, 0) THEN 'Overperformed: Heavier & More Reps'
        WHEN COALESCE(a.weight_kg, 0) > COALESCE(p.planned_weight_kg, 0) AND COALESCE(a.reps, 0) < COALESCE(p.planned_reps, 0) THEN 'Mixed: Heavier but Fewer Reps'
        WHEN COALESCE(a.weight_kg, 0) > COALESCE(p.planned_weight_kg, 0) THEN 'Overperformed: Heavier'
        WHEN COALESCE(a.weight_kg, 0) < COALESCE(p.planned_weight_kg, 0) AND COALESCE(a.reps, 0) > COALESCE(p.planned_reps, 0) THEN 'Mixed: Lighter but More Reps'
        WHEN COALESCE(a.weight_kg, 0) < COALESCE(p.planned_weight_kg, 0) THEN 'Underperformed: Lighter'
        WHEN COALESCE(a.reps, 0) > COALESCE(p.planned_reps, 0) THEN 'Overperformed: More Reps'
        WHEN COALESCE(a.reps, 0) < COALESCE(p.planned_reps, 0) THEN 'Underperformed: Fewer Reps'
        WHEN COALESCE(a.duration_seconds, 0) > COALESCE(p.planned_duration_seconds, 0) THEN 'Overperformed: Longer Duration'
        WHEN COALESCE(a.duration_seconds, 0) < COALESCE(p.planned_duration_seconds, 0) THEN 'Underperformed: Shorter Duration'
        WHEN COALESCE(a.custom_metric, 0) > COALESCE(p.planned_custom_metric, 0) THEN 'Overperformed: Higher Custom Metric'
        WHEN COALESCE(a.custom_metric, 0) < COALESCE(p.planned_custom_metric, 0) THEN 'Underperformed: Lower Custom Metric'
        WHEN COALESCE(p.planned_weight_kg, 0) = 0 AND COALESCE(p.planned_distance_meters, 0) = 0 THEN 'Target Met: Free/Bodyweight'
        ELSE 'Target Met'
    END AS execution_status,

    a.weight_kg - p.planned_weight_kg AS diff_weight_kg,
    a.reps - p.planned_reps AS diff_reps,
    a.duration_seconds - p.planned_duration_seconds AS diff_duration_seconds,
    a.custom_metric - p.planned_custom_metric AS diff_custom_metric,

    a.weight_kg,
    a.reps,
    a.distance_meters,
    a.duration_seconds,
    a.rpe,
    a.custom_metric,

    p.planned_weight_kg,
    p.planned_reps,
    p.planned_distance_meters,
    p.planned_duration_seconds,
    p.planned_custom_metric,
    p.planned_rest
FROM actual a
LEFT JOIN applicable_plan p 
    ON a.routine_id = p.routine_id 
    AND a.exercise_template_id = p.exercise_template_id 
    AND a.exercise_index = p.exercise_index 
    AND a.set_index = p.set_index 
    AND a.set_type = p.set_type
ORDER BY 
    COALESCE(a.updated_at, p.updated_at) DESC;
"""

def drop_table_if_exists(connection: sqlite3.Connection, table_name: str) -> None:
    try:
        cursor = connection.cursor()
        cursor.execute(f'DROP TABLE IF EXISTS "{table_name}"')
        connection.commit()
    except Exception as e:
        logger.warning(f"Failed to drop table {table_name}: {e}")

def execute_silver_etl(database_path: Path) -> None:
    if not database_path.exists():
        logger.critical(f"Database NOT found at {database_path}")
        raise FileNotFoundError(f"Database not found at {database_path}")

    try:
        with sqlite3.connect(database_path) as connection:
            logger.info(f"Connected to DB at {database_path}")

            process_routine_scd2(connection)

            progression_data = load_progression_dictionary()
            dataframe_progression = pd.DataFrame(list(progression_data.items()), columns=["exercise_name", "progression_step_kg"])

            sql_dim_exercise = """
            SELECT 
                id AS exercise_template_id,
                title AS exercise_name,
                COALESCE("type", 'Other') AS exercise_type,
                'Unknown' AS equipment_category,
                COALESCE(primary_muscle_group, 'Other') AS primary_muscle_group,
                CASE WHEN is_custom = 1 THEN 'Yes' ELSE 'No' END AS is_custom_exercise,
                COALESCE(primary_muscle_group, 'Other') || ' - ' || title AS exercise_hierarchy_name
            FROM bronze_exercise_templates;
            """
            
            dataframe_exercises = pd.read_sql_query(sql_dim_exercise, connection)
            if not dataframe_progression.empty:
                dataframe_exercises_merged = pd.merge(dataframe_exercises, dataframe_progression, on="exercise_name", how="left")
            else:
                dataframe_exercises_merged = dataframe_exercises
                dataframe_exercises_merged["progression_step_kg"] = 0.0
            
            dataframe_exercises_merged["progression_step_kg"] = dataframe_exercises_merged["progression_step_kg"].fillna(0.0).infer_objects(copy=False)
            
            drop_table_if_exists(connection, "silver_dim_exercise")
            dataframe_exercises_merged.to_sql("silver_dim_exercise", connection, if_exists="replace", index=False)
            logger.info(f"Loaded silver_dim_exercise: {len(dataframe_exercises_merged)} rows")

            dataframe_routines = pd.read_sql_query(SQL_DIM_ROUTINE, connection)
            drop_table_if_exists(connection, "silver_dim_routine")
            dataframe_routines.to_sql("silver_dim_routine", connection, if_exists="replace", index=False)
            logger.info(f"Loaded silver_dim_routine: {len(dataframe_routines)} rows")

            dataframe_fact_history = pd.read_sql_query(SQL_FACT_WORKOUT_HISTORY, connection)
            drop_table_if_exists(connection, "silver_fact_workout_history")
            dataframe_fact_history.to_sql("silver_fact_workout_history", connection, if_exists="replace", index=False)
            logger.info(f"Loaded silver_fact_workout_history: {len(dataframe_fact_history)} rows")

    except Exception as error:
        logger.error(f"ETL Fatal Error: {error}")
        raise

if __name__ == "__main__":
    execute_silver_etl(DB_PATH)
