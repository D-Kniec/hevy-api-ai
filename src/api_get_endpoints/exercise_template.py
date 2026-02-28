import os
import sqlite3
import logging
import datetime
import json
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
        logging.FileHandler("etl_exercise_templates.log"),
        TqdmLoggingHandler()
    ]
)
logger = logging.getLogger(__name__)

class ExerciseTemplateModel(BaseModel):
    id: Union[str, int]
    title: str
    exercise_type: Optional[str] = Field(alias='type', default=None)
    primary_muscle_group: Optional[str] = None
    secondary_muscle_groups: List[str] = []
    is_custom: Optional[bool] = False
    
    model_config = ConfigDict(populate_by_name=True)

def fetch_and_validate_templates() -> List[Dict[str, Any]]:
    if not HEVY_API_KEY:
        logger.critical("Missing HEVY_API_KEY")
        raise ValueError("API Key not found")

    headers = {"api-key": HEVY_API_KEY}
    rows = []
    page = 1
    page_count = 1
    
    with requests.Session() as session:
        session.headers.update(headers)
        
        try:
            init_resp = session.get(f"{BASE_URL}/exercise_templates", params={"page": 1, "pageSize": 100})
            init_resp.raise_for_status()
            data = init_resp.json()
            page_count = max(1, data.get('page_count', 1))
            logger.info(f"Total pages to fetch: {page_count}")
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            return []

        pbar = tqdm(total=page_count, desc="Fetching Templates")
        
        while page <= page_count:
            try:
                response = session.get(
                    f"{BASE_URL}/exercise_templates", 
                    params={"page": page, "pageSize": 100},
                    timeout=15
                )
                
                if response.status_code == 404:
                    break

                response.raise_for_status()
                data = response.json()
                
                templates = data.get('exercise_templates', [])

                if not templates:
                    break

                for t in templates:
                    try:
                        model = ExerciseTemplateModel(**t)
                        row = {
                            "id": model.id,
                            "title": model.title,
                            "type": model.exercise_type,
                            "primary_muscle_group": model.primary_muscle_group,
                            "secondary_muscle_groups": json.dumps(model.secondary_muscle_groups),
                            "is_custom": model.is_custom,
                            "ingestion_timestamp": datetime.datetime.now().isoformat()
                        }
                        rows.append(row)
                    except ValidationError as ve:
                        logger.warning(f"Validation Error ID {t.get('id')}: {ve}")

                page += 1
                pbar.update(1)

            except requests.RequestException as e:
                logger.error(f"Network Error on page {page}: {e}")
                break
        
        pbar.close()

    return rows

def save_to_db(rows: List[Dict[str, Any]], db_path: Path):
    if not rows:
        logger.warning("No exercise templates to save.")
        return

    db_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    
    try:
        with sqlite3.connect(db_path) as conn:
            df.to_sql('bronze.ExerciseTemplate', conn, if_exists='replace', index=False)
            
        logger.info(f"SUCCESS: Saved {len(df)} records to 'bronze.ExerciseTemplate' in {db_path.name}")
    except Exception as e:
        logger.error(f"Database Save Error: {e}")

if __name__ == "__main__":
    data = fetch_and_validate_templates()
    save_to_db(data, DB_PATH)