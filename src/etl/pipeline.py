import sys
import logging
import importlib
from pathlib import Path

def find_project_root() -> Path:
    current_file = Path(__file__).resolve()
    for parent in [current_file] + list(current_file.parents):
        if parent.name == "src":
            return parent.parent
    return current_file.parent.parent.parent

BASE_DIR = find_project_root()
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def run_full_pipeline() -> None:
    database_path = BASE_DIR / "data" / "bronze_layer.db"
    
    try:
        logger.info("Executing Bronze Layer ETL")
        bronze_module = importlib.import_module("src.etl.01_bronze")
        bronze_module.execute_bronze_etl()
        
        logger.info("Executing Silver Layer ETL")
        silver_module = importlib.import_module("src.etl.02_silver")
        silver_module.execute_silver_etl(database_path)
        
        logger.info("Executing Gold Layer ETL")
        gold_module = importlib.import_module("src.etl.03_gold")
        gold_module.execute_gold_etl(database_path)
        
        logger.info("Pipeline completed successfully")
    except Exception as error:
        logger.critical(f"Pipeline execution failed: {error}")
        sys.exit(1)

if __name__ == "__main__":
    run_full_pipeline()
