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
        logging.FileHandler("etl_routine_folders.log"),
        TqdmLoggingHandler()
    ]
)
logger = logging.getLogger(__name__)

class RoutineFolderModel(BaseModel):
    id: Union[int, str]
    index: int
    title: str
    updated_at: Optional[str] = None
    created_at: Optional[str] = None
    
    model_config = ConfigDict(populate_by_name=True)

def fetch_and_validate_folders() -> List[Dict[str, Any]]:
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
            init_resp = session.get(f"{BASE_URL}/routine_folders", params={"page": 1, "pageSize": 10})
            init_resp.raise_for_status()
            data = init_resp.json()
            page_count = max(1, data.get('page_count', 1))
            logger.info(f"Total pages to fetch: {page_count}")
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            return []

        pbar = tqdm(total=page_count, desc="Fetching Folders")
        
        while page <= page_count:
            try:
                response = session.get(
                    f"{BASE_URL}/routine_folders", 
                    params={"page": page, "pageSize": 10},
                    timeout=15
                )
                
                if response.status_code == 404:
                    break

                response.raise_for_status()
                data = response.json()
                
                folders = data.get('routine_folders', [])

                if not folders and page == 1:
                    logger.info("No folders found on first page.")
                    break

                for f in folders:
                    try:
                        folder = RoutineFolderModel(**f)
                        row = folder.model_dump()
                        row['ingestion_timestamp'] = datetime.datetime.now().isoformat()
                        rows.append(row)
                    except ValidationError as ve:
                        logger.warning(f"Validation Error ID {f.get('id')}: {ve}")

                page += 1
                pbar.update(1)

            except requests.RequestException as e:
                logger.error(f"Network Error on page {page}: {e}")
                break
        
        pbar.close()

    return rows

def save_to_db(rows: List[Dict[str, Any]], db_path: Path):
    if not rows:
        logger.warning("No data to save.")
        return

    db_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    
    try:
        with sqlite3.connect(db_path) as conn:
            df.to_sql('bronze.RoutineFolder', conn, if_exists='replace', index=False)
            
        logger.info(f"SUCCESS: Saved {len(df)} records to 'bronze.RoutineFolder' in {db_path.name}")
    except Exception as e:
        logger.error(f"Database Save Error: {e}")

if __name__ == "__main__":
    data = fetch_and_validate_folders()
    save_to_db(data, DB_PATH)