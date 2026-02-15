import os
import sqlite3
import json
import logging
import datetime
import math
from pathlib import Path
from typing import List, Dict, Any, Optional

import requests
import pandas as pd
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError
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
        logging.FileHandler("etl_process.log"),
        TqdmLoggingHandler()
    ]
)
logger = logging.getLogger(__name__)

class ExerciseModel(BaseModel):
    id: str
    title: str
    exercise_type: Optional[str] = Field(alias='type', default=None)
    equipment_category: Optional[str] = None
    muscle_group: Optional[str] = Field(alias='primary_muscle_group', default=None)
    secondary_muscles: List[str] = Field(alias='secondary_muscle_groups', default_factory=list)
    is_custom: bool = False

    class Config:
        populate_by_name = True

def fetch_and_validate_data() -> List[Dict[str, Any]]:
    if not HEVY_API_KEY:
        logger.critical("Missing HEVY_API_KEY")
        raise ValueError("API Key not found")

    headers = {"api-key": HEVY_API_KEY}
    validated_rows = []
    page_size = 100
    
    try:
        init_resp = requests.get(f"{BASE_URL}/exercise_templates", headers=headers, params={"page": 1, "pageSize": 1})
        init_resp.raise_for_status()
        
        total_items = init_resp.json().get('page_count', 0)
        total_pages = math.ceil(total_items / page_size)
        
        logger.info(f"Total items: {total_items}. Calculated pages (batch {page_size}): {total_pages}")
    except Exception as e:
        logger.error(f"API Initialization Error: {e}")
        return []

    with requests.Session() as session:
        session.headers.update(headers)
        
        for page in tqdm(range(1, total_pages + 1), desc="Fetching Pages"):
            try:
                response = session.get(
                    f"{BASE_URL}/exercise_templates",
                    params={"page": page, "pageSize": page_size},
                    timeout=10
                )
                
                if response.status_code == 404:
                    logger.warning(f"Page {page} not found. Stopping.")
                    break
                
                response.raise_for_status()
                data = response.json()
                
                templates = data.get('exercise_templates', [])
                
                if not templates:
                    logger.info(f"No templates on page {page}. Stopping.")
                    break

                for t in templates:
                    try:
                        model = ExerciseModel(**t)
                        row = model.model_dump(exclude={'secondary_muscles'})
                        row['other_muscles_json'] = json.dumps(model.secondary_muscles)
                        row['ingestion_timestamp'] = datetime.datetime.now().isoformat()
                        validated_rows.append(row)
                    except ValidationError as ve:
                        logger.warning(f"Validation Error ID {t.get('id')}: {ve}")

            except requests.RequestException as e:
                logger.error(f"Network Error on page {page}: {e}")

    return validated_rows

def save_bronze_layer(rows: List[Dict[str, Any]], db_path: Path):
    if not rows:
        logger.warning("No data to save.")
        return

    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    df = pd.DataFrame(rows)
    
    try:
        with sqlite3.connect(db_path) as conn:
            df.to_sql('bronze.exercise_templates', conn, if_exists='replace', index=False)
            
        logger.info(f"SUCCESS: Saved {len(df)} records to table 'bronze.exercise_templates' in {db_path.name}.")
    except Exception as e:
        logger.error(f"Database Save Error: {e}")

if __name__ == "__main__":
    data = fetch_and_validate_data()
    save_bronze_layer(data, DB_PATH)