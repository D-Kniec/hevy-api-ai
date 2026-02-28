import sqlite3
import pandas as pd
import json
import logging
import os
import sys
from pathlib import Path
from tqdm import tqdm
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR / "data"))

try:
    from proggresion import PROGRESSION
except ImportError:
    PROGRESSION = {}

load_dotenv(BASE_DIR / '.env')
PRIORITY_COUNT = int(os.getenv("PRIORITY_WORKOUT_COUNT", 4))

DB_PATH = BASE_DIR / "data" / "hevy.db"

if not os.path.exists(DB_PATH.parent):
    os.makedirs(DB_PATH.parent)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def create_silver_tables(conn):
    cursor = conn.cursor()
    cursor.executescript("""
        DROP TABLE IF EXISTS silver_workout_sets;
        DROP TABLE IF EXISTS silver_workout_exercises;
        DROP TABLE IF EXISTS silver_workouts;
        DROP TABLE IF EXISTS silver_routine_sets;
        DROP TABLE IF EXISTS silver_routine_exercises;
        DROP TABLE IF EXISTS silver_routines;
        DROP TABLE IF EXISTS silver_exercise_secondary_muscles;
        DROP TABLE IF EXISTS silver_exercise_templates;
        DROP TABLE IF EXISTS silver_routine_folders;
        DROP TABLE IF EXISTS silver_exercise_progression;
        DROP TABLE IF EXISTS silver_enums_muscle_group;
        DROP TABLE IF EXISTS silver_enums_equipment;
        DROP TABLE IF EXISTS silver_enums_exercise_type;

        CREATE TABLE silver_enums_muscle_group (name TEXT PRIMARY KEY);
        CREATE TABLE silver_enums_equipment (name TEXT PRIMARY KEY);
        CREATE TABLE silver_enums_exercise_type (name TEXT PRIMARY KEY);

        CREATE TABLE silver_exercise_progression (
            exercise_title TEXT PRIMARY KEY,
            base_increment REAL DEFAULT 2.5
        );

        CREATE TABLE silver_routine_folders (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            created_at TEXT,
            updated_at TEXT
        );

        CREATE TABLE silver_exercise_templates (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            type TEXT,
            primary_muscle_group TEXT,
            equipment_category TEXT,
            is_custom BOOLEAN,
            base_increment REAL DEFAULT 2.5
        );

        CREATE TABLE silver_exercise_secondary_muscles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exercise_template_id TEXT,
            muscle_group TEXT,
            FOREIGN KEY(exercise_template_id) REFERENCES silver_exercise_templates(id)
        );

        CREATE TABLE silver_routines (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            folder_id INTEGER,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY(folder_id) REFERENCES silver_routine_folders(id)
        );

        CREATE TABLE silver_routine_exercises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            routine_id TEXT NOT NULL,
            exercise_template_id TEXT,
            superset_id INTEGER,
            rest_seconds INTEGER,
            notes TEXT,
            order_index INTEGER,
            FOREIGN KEY(routine_id) REFERENCES silver_routines(id),
            FOREIGN KEY(exercise_template_id) REFERENCES silver_exercise_templates(id)
        );

        CREATE TABLE silver_routine_sets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            routine_exercise_id INTEGER NOT NULL,
            set_type TEXT,
            weight_kg REAL,
            reps INTEGER,
            rep_range_start INTEGER,
            rep_range_end INTEGER,
            distance_meters REAL,
            duration_seconds REAL,
            rpe REAL,
            FOREIGN KEY(routine_exercise_id) REFERENCES silver_routine_exercises(id) ON DELETE CASCADE
        );

        CREATE TABLE silver_workouts (
            id TEXT PRIMARY KEY,
            title TEXT,
            description TEXT,
            start_time TEXT,
            end_time TEXT,
            created_at TEXT,
            updated_at TEXT,
            routine_id TEXT,
            is_priority BOOLEAN DEFAULT 0
        );

        CREATE TABLE silver_workout_exercises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workout_id TEXT NOT NULL,
            exercise_template_id TEXT,
            superset_id INTEGER,
            notes TEXT,
            order_index INTEGER,
            FOREIGN KEY(workout_id) REFERENCES silver_workouts(id)
        );

        CREATE TABLE silver_workout_sets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workout_exercise_id INTEGER NOT NULL,
            set_type TEXT,
            weight_kg REAL,
            reps INTEGER,
            distance_meters REAL,
            duration_seconds REAL,
            rpe REAL,
            custom_metric REAL,
            FOREIGN KEY(workout_exercise_id) REFERENCES silver_workout_exercises(id) ON DELETE CASCADE
        );
    """)
    conn.commit()

def etl_process():
    conn = get_db_connection()
    try:
        logger.info("Initializing Silver Schema...")
        create_silver_tables(conn)

        with tqdm(total=6, desc="Overall Progress") as pbar:
            
            pbar.set_description("Processing Enums")
            try:
                # Try to load enums from bronze if they exist
                for enum_table, silver_table in [
                    ('bronze.MuscleGroup', 'silver_enums_muscle_group'),
                    ('bronze.EquipmentCategory', 'silver_enums_equipment'),
                    ('bronze.CustomExerciseType', 'silver_enums_exercise_type')
                ]:
                    try:
                        df_enum = pd.read_sql(f"SELECT name FROM '{enum_table}'", conn)
                        if not df_enum.empty:
                            df_enum.to_sql(silver_table, conn, if_exists='append', index=False)
                    except Exception:
                        pass 
            except Exception as e:
                logger.error(f"Enum Processing Error: {e}")
            pbar.update(1)

            pbar.set_description("Processing Progression Data")
            try:
                if PROGRESSION:
                    prog_data = [{'exercise_title': k, 'base_increment': v} for k, v in PROGRESSION.items()]
                    df_prog = pd.DataFrame(prog_data)
                    df_prog.to_sql('silver_exercise_progression', conn, if_exists='append', index=False)
            except Exception as e:
                logger.error(f"Progression Data Error: {e}")
            pbar.update(1)

            pbar.set_description("Processing Folders & Templates")
            try:
                df_folders = pd.read_sql("SELECT DISTINCT id, title, created_at, updated_at FROM 'bronze.RoutineFolder'", conn)
                if not df_folders.empty:
                    df_folders.to_sql('silver_routine_folders', conn, if_exists='append', index=False)
            except Exception:
                pass

            try:
                # IMPORTANT FIX: Removed 'equipment_category' from SELECT query
                # It does not exist in bronze.ExerciseTemplate
                df_templates = pd.read_sql("""
                    SELECT id, title, type, primary_muscle_group, is_custom, secondary_muscle_groups 
                    FROM 'bronze.ExerciseTemplate'
                """, conn)
                
                if not df_templates.empty:
                    df_main_templates = df_templates[['id', 'title', 'type', 'primary_muscle_group', 'is_custom']].drop_duplicates()
                    
                    # Manually add empty equipment_category column to match schema
                    df_main_templates['equipment_category'] = None
                    
                    # Map base_increment
                    df_main_templates['base_increment'] = df_main_templates['title'].map(PROGRESSION).fillna(2.5)

                    df_main_templates.to_sql('silver_exercise_templates', conn, if_exists='append', index=False)

                    secondary_rows = []
                    for _, row in df_templates.iterrows():
                        try:
                            if row['secondary_muscle_groups']:
                                muscles = json.loads(row['secondary_muscle_groups'])
                                if isinstance(muscles, list):
                                    for muscle in muscles:
                                        secondary_rows.append({
                                            'exercise_template_id': row['id'],
                                            'muscle_group': muscle
                                        })
                        except (json.JSONDecodeError, TypeError):
                            continue
                    
                    if secondary_rows:
                        pd.DataFrame(secondary_rows).to_sql('silver_exercise_secondary_muscles', conn, if_exists='append', index=False)
            except Exception as e:
                logger.error(f"Template Error: {e}")
            
            pbar.update(1)

            pbar.set_description("Processing Routines")
            try:
                df_routines_raw = pd.read_sql("SELECT * FROM 'bronze.Routine'", conn)
                
                if not df_routines_raw.empty:
                    routines_cols = ['routine_id', 'title', 'folder_id', 'created_at', 'updated_at']
                    df_routines = df_routines_raw[routines_cols].rename(columns={'routine_id': 'id'}).drop_duplicates()
                    df_routines.to_sql('silver_routines', conn, if_exists='append', index=False)

                    ex_cols = ['routine_id', 'exercise_template_id', 'supersets_id', 'rest_seconds', 'exercise_notes', 'exercise_index']
                    df_r_exercises = df_routines_raw[ex_cols].rename(columns={
                        'supersets_id': 'superset_id',
                        'exercise_notes': 'notes', 
                        'exercise_index': 'order_index'
                    }).drop_duplicates()
                    df_r_exercises.to_sql('silver_routine_exercises', conn, if_exists='append', index=False)

                    df_r_ex_map = pd.read_sql("SELECT id as routine_exercise_id, routine_id, order_index FROM silver_routine_exercises", conn)
                    
                    df_sets_merged = df_routines_raw.merge(
                        df_r_ex_map, 
                        left_on=['routine_id', 'exercise_index'], 
                        right_on=['routine_id', 'order_index']
                    )

                    sets_cols_map = {
                        'set_type': 'set_type',
                        'weight_kg': 'weight_kg',
                        'reps': 'reps',
                        'rep_range_start': 'rep_range_start',
                        'rep_range_end': 'rep_range_end',
                        'distance_meters': 'distance_meters',
                        'duration_seconds': 'duration_seconds',
                        'rpe': 'rpe'
                    }
                    
                    df_final_sets = df_sets_merged[['routine_exercise_id'] + list(sets_cols_map.keys())]
                    df_final_sets.to_sql('silver_routine_sets', conn, if_exists='append', index=False)
            
            except Exception as e:
                logger.error(f"Routine Error: {e}")
            
            pbar.update(1)

            pbar.set_description("Processing Workouts")
            try:
                df_workouts_raw = pd.read_sql("SELECT * FROM 'bronze.Workouts'", conn)

                if not df_workouts_raw.empty:
                    w_cols = ['workout_id', 'title', 'description', 'start_time', 'end_time', 'created_at', 'updated_at', 'routine_id']
                    df_workouts = df_workouts_raw[w_cols].rename(columns={'workout_id': 'id'}).drop_duplicates()
                    
                    # Sort & Priority Logic
                    df_workouts = df_workouts.sort_values(by='start_time', ascending=False)
                    df_workouts['is_priority'] = False
                    if len(df_workouts) > 0:
                        df_workouts.iloc[:PRIORITY_COUNT, df_workouts.columns.get_loc('is_priority')] = True
                    
                    df_workouts.to_sql('silver_workouts', conn, if_exists='append', index=False)

                    w_ex_cols = ['workout_id', 'exercise_template_id', 'supersets_id', 'exercise_notes', 'exercise_index']
                    df_w_exercises = df_workouts_raw[w_ex_cols].rename(columns={
                        'supersets_id': 'superset_id',
                        'exercise_notes': 'notes',
                        'exercise_index': 'order_index'
                    }).drop_duplicates()
                    df_w_exercises.to_sql('silver_workout_exercises', conn, if_exists='append', index=False)

                    df_w_ex_map = pd.read_sql("SELECT id as workout_exercise_id, workout_id, order_index FROM silver_workout_exercises", conn)
                    
                    df_w_sets_merged = df_workouts_raw.merge(
                        df_w_ex_map,
                        left_on=['workout_id', 'exercise_index'],
                        right_on=['workout_id', 'order_index']
                    )

                    w_sets_cols = ['set_type', 'weight_kg', 'reps', 'distance_meters', 'duration_seconds', 'rpe', 'custom_metric']
                    df_final_w_sets = df_w_sets_merged[['workout_exercise_id'] + w_sets_cols]
                    df_final_w_sets.to_sql('silver_workout_sets', conn, if_exists='append', index=False)

            except Exception as e:
                logger.error(f"Workout Error: {e}")
            
            pbar.update(2)
            logger.info("ETL Complete.")

    except Exception as e:
        logger.critical(f"Fatal ETL Error: {e}", exc_info=True)
    finally:
        conn.close()

if __name__ == "__main__":
    etl_process()
