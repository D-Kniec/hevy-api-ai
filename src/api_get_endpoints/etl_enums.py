import sqlite3
import logging
import os
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Literal, get_args

MuscleGroup = Literal[
    'abdominals', 'shoulders', 'biceps', 'triceps', 'forearms', 'quadriceps', 
    'hamstrings', 'calves', 'glutes', 'abductors', 'adductors', 'lats', 
    'upper_back', 'traps', 'lower_back', 'chest', 'cardio', 'neck', 'full_body', 'other'
]

EquipmentCategory = Literal[
    'none', 'barbell', 'dumbbell', 'kettlebell', 'machine', 'plate', 
    'resistance_band', 'suspension', 'other'
]

CustomExerciseType = Literal[
    'weight_reps', 'reps_only', 'bodyweight_reps', 'bodyweight_assisted_reps', 
    'duration', 'weight_duration', 'distance_duration', 'short_distance_weight'
]

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "hevy.db"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def extract_enums() -> Dict[str, List[Dict[str, Any]]]:
    data = {}
    
    muscles = [{"name": m} for m in get_args(MuscleGroup)]
    data['bronze.MuscleGroup'] = muscles
    
    equipment = [{"name": e} for e in get_args(EquipmentCategory)]
    data['bronze.EquipmentCategory'] = equipment
    
    types = [{"name": t} for t in get_args(CustomExerciseType)]
    data['bronze.CustomExerciseType'] = types
    
    return data

def save_enums_to_db(data: Dict[str, List[Dict[str, Any]]], db_path: Path):
    if not os.path.exists(db_path.parent):
        os.makedirs(db_path.parent)

    try:
        with sqlite3.connect(db_path) as conn:
            for table_name, rows in data.items():
                if not rows:
                    continue
                
                df = pd.DataFrame(rows)
                df.to_sql(table_name, conn, if_exists='replace', index=False)
                logger.info(f"SUCCESS: Saved {len(df)} records to '{table_name}'")
                
    except Exception as e:
        logger.error(f"Database Save Error: {e}")

if __name__ == "__main__":
    enums_data = extract_enums()
    save_enums_to_db(enums_data, DB_PATH)
