import datetime

def get_periodization_phase(date_obj=None):
    if date_obj is None:
        date_obj = datetime.date.today()
    
    iso_week = date_obj.isocalendar()[1]
    cycle_week = ((iso_week - 1) % 4) + 1
    
    if cycle_week == 1:
        return {
            "name": "ACCUMULATION",
            "week": 1,
            "goal": "Hypertrophy and Work Capacity",
            "rpe_target": "7.0 - 7.5",
            "rep_modifier": "INCREASE_REPS",
            "load_modifier": "MODERATE_LOAD",
            "instruction": "Prioritize volume. Keep 2-3 reps in reserve (RIR). If in doubt, choose higher reps over heavier weight."
        }
    
    elif cycle_week == 2:
        return {
            "name": "INTENSIFICATION",
            "week": 2,
            "goal": "Strength Endurance and Load Acclimatization",
            "rpe_target": "8.0",
            "rep_modifier": "MAINTAIN_REPS",
            "load_modifier": "INCREASE_LOAD",
            "instruction": "Standard progressive overload. Increase weight from Week 1 while maintaining good form. RPE 8 is the sweet spot."
        }
    
    elif cycle_week == 3:
        return {
            "name": "REALIZATION",
            "week": 3,
            "goal": "Peak Strength and PR Attempts",
            "rpe_target": "9.0 - 9.5",
            "rep_modifier": "DECREASE_REPS",
            "load_modifier": "PEAK_LOAD",
            "instruction": "Heavy week. Push near failure safely. Drop reps if needed to handle maximum load. This is the test week."
        }
    
    else:
        return {
            "name": "DELOAD",
            "week": 4,
            "goal": "Systemic Recovery and Fatigue dissipation",
            "rpe_target": "5.0 - 6.0",
            "rep_modifier": "REDUCE_VOLUME",
            "load_modifier": "REDUCE_LOAD_40_PERCENT",
            "instruction": "Mandatory recovery. Reduce weights by 40-50% OR cut number of sets in half. Do not push hard. Leave gym feeling fresh."
        }