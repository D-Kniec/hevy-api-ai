from typing import Dict, Any

def construct_ai_prompt(routine_data: Dict[str, Any]) -> str:
    max_cycle = 0
    for exercise in routine_data["exercises"]:
        if exercise["history"]:
            latest_cycle = exercise["history"][-1]["cycle"]
            if latest_cycle > max_cycle:
                max_cycle = latest_cycle

    next_cycle = max_cycle + 1
    is_deload = next_cycle % 4 == 0
    phase_name = "DELOAD" if is_deload else "PROGRESSION"

    system_instructions = f"""You are an elite strength coach AI. Your task is to plan the NEXT workout session based STRICTLY on the provided execution history from the 'gold_prompt' database.

CRITICAL RULES:
1. Base your recommendations ON THE ACTUAL WEIGHT AND REPS performed in the last cycle. Focus on the heaviest set performed to determine the next target. Ignore 'planned' metrics.
2. Current Phase: {phase_name} (Cycle {next_cycle}).
   - If PROGRESSION: Increase weight by the 'Progression Step' if RPE is < 9.0 on the heaviest set. If RPE is between 9.0 and 9.5, maintain weight and push for more reps. If RPE > 9.5, slightly reduce weight or reps to manage fatigue.
   - If DELOAD: Reduce the ACTUAL weight of the last cycle by 10-15% and drop 1-2 reps to allow recovery.
3. If an exercise has 'Bodyweight' as weight but actual reps > 0, it was NOT skipped. Recommend progression by adding reps. Treat as skipped ONLY if BOTH weight and reps are 'Skipped'.
4. Note 'Superset ID' values. Exercises sharing the same Superset ID are performed back-to-back with minimal rest. Factor this cumulative fatigue into your recommendations if needed.

Respond ONLY with a JSON object matching this schema:
{{
    "recommendations": {{
        "EXERCISE_ID": {{
            "weight_kg": float,
            "reps": int,
            "rpe_target": float,
            "strategy": string,
            "reasoning": string
        }}
    }}
}}
"""

    user_context = "--- EXERCISE HISTORY (gold_prompt) ---\n"
    for exercise in routine_data["exercises"]:
        last_cycle_data = exercise["history"][-1] if exercise["history"] else None
        if not last_cycle_data:
            continue

        sets_info = []
        for exercise_set in last_cycle_data["sets"]:
            actual_weight = exercise_set["actual_weight_kg"] if exercise_set["actual_weight_kg"] is not None else "Bodyweight"
            actual_reps = exercise_set["actual_reps"] if exercise_set["actual_reps"] is not None else "Skipped"
            planned_weight = exercise_set["planned_weight_kg"] if exercise_set["planned_weight_kg"] is not None else "N/A"
            planned_reps = exercise_set["planned_reps"] if exercise_set["planned_reps"] is not None else "N/A"

            sets_info.append(
                f"  Set {exercise_set['set_index']}: Planned {planned_weight}kg x {planned_reps} | "
                f"Actual: {actual_weight}kg x {actual_reps} @ RPE {exercise_set['rpe']} | "
                f"Status: {exercise_set['execution_status']}"
            )

        superset_str = f", Superset ID: {exercise['superset_id']}" if exercise.get('superset_id') is not None else ""

        user_context += (
            f"\nExercise: {exercise['title']} (ID: {exercise['exercise_template_id']}, Index: {exercise['exercise_index']}{superset_str})\n"
            f"Progression Step: {exercise['progression_step_kg']} kg\n"
            f"Last Cycle (# {last_cycle_data['cycle']}) Results:\n" +
            "\n".join(sets_info) + "\n"
        )

    return f"{system_instructions}\n\n{user_context}"