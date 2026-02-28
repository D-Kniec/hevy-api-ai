import os
import sys
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any

import logging
from google import genai
from google.genai import types
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

def find_project_root() -> Path:
    current_file = Path(__file__).resolve()
    for parent in [current_file] + list(current_file.parents):
        if parent.name == "src":
            return parent.parent
    return current_file.parent.parent.parent

BASE_DIR = find_project_root()
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.ai.inspector import select_routine_from_database, get_full_routine_data
from src.ai.prompts import construct_ai_prompt
from src.api.client import HevyAPIClient
from src.api.schemas import PutRoutinesRequestBody

ENV_PATH = BASE_DIR / ".env"
if not ENV_PATH.exists():
    ENV_PATH = BASE_DIR / "src" / ".env"
load_dotenv(ENV_PATH)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
logging.getLogger("google.genai").setLevel(logging.CRITICAL)

if not GOOGLE_API_KEY:
    logger.critical("Missing GOOGLE_API_KEY in .env")
    sys.exit(1)

client = genai.Client(api_key=GOOGLE_API_KEY)

class AIRecommendation(BaseModel):
    weight_kg: float
    reps: int
    rpe_target: float
    strategy: str
    reasoning: str

class AIPlanResponse(BaseModel):
    recommendations: Dict[str, AIRecommendation]

def calculate_warmup_sets(target_weight: float) -> List[Dict[str, float]]:
    if target_weight <= 0:
        return []
    
    half_weight = round((target_weight * 0.5) / 2.5) * 2.5
    
    if half_weight < 5.0:
        return []
        
    return [{"weight_kg": half_weight, "reps": 10}]

def generate_bulk_plan(routine_data: Dict[str, Any]) -> Optional[AIPlanResponse]:
    full_prompt = construct_ai_prompt(routine_data)
    candidate_models = ["gemini-3-flash-preview", "gemini-2.0-flash", "gemini-2.5-flash"]

    logger.info(f"Sending BULK request for {len(routine_data['exercises'])} exercises based on gold_prompt...")

    for model in candidate_models:
        try:
            response = client.models.generate_content(
                model=model,
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1
                )
            )
            parsed_json = json.loads(response.text)
            return AIPlanResponse(**parsed_json)

        except ValidationError as validation_error:
            logger.error(f"LLM Schema Validation Error using {model}: {validation_error}")
            return None
        except Exception as error:
            logger.warning(f"Model {model} failed: {error}")
            if "429" in str(error) or "RESOURCE_EXHAUSTED" in str(error):
                time.sleep(1.5)
            else:
                continue

    return None

def run_agent() -> None:
    selected_routine = select_routine_from_database()
    if not selected_routine:
        return

    logger.info(f"Loading data for {selected_routine['title']}...")
    routine_data = get_full_routine_data(selected_routine["id"])
    
    if not routine_data:
        logger.error("Failed to load routine details.")
        return

    ai_response = generate_bulk_plan(routine_data)
    if not ai_response:
        logger.error("Failed to generate plan.")
        return

    recommendations = ai_response.recommendations

    print("\n--- AI PLAN ---")
    for exercise in routine_data["exercises"]:
        template_id = exercise["exercise_template_id"]
        recommendation = recommendations.get(template_id)
        if recommendation:
            print(f"{exercise['title']}: {recommendation.weight_kg}kg x {recommendation.reps} ({recommendation.strategy})")

    if input("\nUpdate Hevy? (y/n): ").strip().lower() != "y":
        return

    updated_exercises = []

    for exercise in routine_data["exercises"]:
        template_id = exercise["exercise_template_id"]
        recommendation = recommendations.get(template_id)

        new_exercise = {
            "exercise_template_id": template_id,
            "superset_id": exercise.get("superset_id"),
            "rest_seconds": exercise["rest_seconds"],
            "notes": "",
            "sets": []
        }

        if recommendation:
            rpe_note = f" RPE {recommendation.rpe_target}" if recommendation.rpe_target else ""
            new_exercise["notes"] = f"[AI: {recommendation.reasoning}{rpe_note}]"

            target_weight = recommendation.weight_kg
            target_reps = recommendation.reps

            if target_weight > 0:
                warmups = calculate_warmup_sets(target_weight)
                for warmup in warmups:
                    new_exercise["sets"].append({
                        "type": "warmup",
                        "weight_kg": warmup["weight_kg"],
                        "reps": warmup["reps"]
                    })

            last_cycle = exercise["history"][-1]["sets"]
            num_working_sets = len([exercise_set for exercise_set in last_cycle if exercise_set["set_type"] == "normal"]) if last_cycle else 3

            for _ in range(num_working_sets):
                new_exercise["sets"].append({
                    "type": "normal",
                    "weight_kg": target_weight,
                    "rep_range": {
                        "start": max(1, target_reps - 2),
                        "end": target_reps + 2
                    }
                })
        else:
            last_cycle = exercise["history"][-1]["sets"]
            for exercise_set in last_cycle:
                new_exercise["sets"].append({
                    "type": exercise_set["set_type"],
                    "weight_kg": exercise_set["planned_weight_kg"] or exercise_set["actual_weight_kg"],
                    "reps": exercise_set["planned_reps"] or exercise_set["actual_reps"]
                })

        updated_exercises.append(new_exercise)

    raw_payload = {
        "routine": {
            "title": routine_data["title"],
            "notes": f"AI Plan: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
            "exercises": updated_exercises
        }
    }

    try:
        validated_payload = PutRoutinesRequestBody(**raw_payload)
    except ValidationError as error:
        logger.error(f"Payload Validation Error: {error}")
        return

    try:
        api_client = HevyAPIClient()
        endpoint = f"routines/{routine_data['id']}"
        api_client.put(endpoint, validated_payload)
        print("Success! Routine updated.")
    except Exception as error:
        logger.error(f"API Update Failed: {error}")

if __name__ == "__main__":
    run_agent()
