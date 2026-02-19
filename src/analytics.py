import statistics
from datetime import datetime

def calculate_e1rm(weight, reps):
    if reps == 1:
        return weight
    return weight * (1 + reps / 30.0)

def analyze_exercise_history(history):
    if not history or len(history) < 2:
        return {
            "stall_streak": 0,
            "e1rm_current": 0.0,
            "e1rm_trend_percent": 0.0,
            "avg_rpe_last_3": 0.0,
            "status": "NEW",
            "recommended_action": "LINEAR_LOAD"
        }

    processed_sessions = []
    for h in history:
        try:
            w = float(h['weight'])
            r = int(h['reps'])
            rpe = float(h['rpe']) if h.get('rpe') and h['rpe'] != 'N/A' else None
            date_obj = datetime.strptime(h['date'], "%Y-%m-%d")
            
            processed_sessions.append({
                "weight": w,
                "reps": r,
                "rpe": rpe,
                "e1rm": calculate_e1rm(w, r),
                "date": date_obj
            })
        except (ValueError, TypeError):
            continue

    if not processed_sessions:
        return {"status": "ERROR", "recommended_action": "MAINTAIN"}

    latest = processed_sessions[0]
    
    last_3_rpes = [s['rpe'] for s in processed_sessions[:3] if s['rpe'] is not None]
    avg_rpe = statistics.mean(last_3_rpes) if last_3_rpes else 0.0
    
    reference_index = min(len(processed_sessions)-1, 3)
    current_e1rm = latest['e1rm']
    past_e1rm = processed_sessions[reference_index]['e1rm']
    
    e1rm_diff_percent = ((current_e1rm - past_e1rm) / past_e1rm) * 100 if past_e1rm > 0 else 0

    stall_streak = 0
    for i in range(len(processed_sessions) - 1):
        curr = processed_sessions[i]
        prev = processed_sessions[i+1]
        
        is_stalled = curr['e1rm'] <= prev['e1rm'] * 1.01
        is_hard = (curr['rpe'] or 0) >= 8.5
        
        if is_stalled and is_hard:
            stall_streak += 1
        else:
            break

    status = "PROGRESS"
    action = "LINEAR_LOAD"

    if e1rm_diff_percent < -5.0:
        status = "REGRESSION"
        action = "RESET"
    elif stall_streak >= 2 and avg_rpe >= 9.0:
        status = "GRINDING"
        action = "DELOAD"
    elif stall_streak >= 2 and avg_rpe < 7.0:
        status = "SANDBAGGING"
        action = "PUSH_HARDER"
    elif stall_streak >= 3:
        status = "STAGNATION"
        action = "CHANGE_REP_RANGE"
    elif e1rm_diff_percent > 5.0:
        status = "FAST_GAINS"
        action = "AGGRESSIVE_LOAD"

    return {
        "stall_streak": stall_streak,
        "e1rm_current": round(current_e1rm, 1),
        "e1rm_trend_percent": round(e1rm_diff_percent, 1),
        "avg_rpe_last_3": round(avg_rpe, 1),
        "status": status,
        "recommended_action": action
    }