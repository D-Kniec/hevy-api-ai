def round_to_step(value, step=2.5):
    return round(value / step) * step

def calculate_warmup_sets(target_weight_kg):
    if not target_weight_kg or target_weight_kg < 20:
        return []

    warmups = []
    seen_weights = set()

    def add_warmup(weight, reps):
        w = round_to_step(weight)
        if w >= 20 and w < target_weight_kg and w not in seen_weights:
            warmups.append({'weight_kg': w, 'reps': reps})
            seen_weights.add(w)

    if target_weight_kg < 40:
        add_warmup(target_weight_kg * 0.5, 10)
        
    elif target_weight_kg < 80:
        add_warmup(20, 12) 
        add_warmup(target_weight_kg * 0.6, 6)
        add_warmup(target_weight_kg * 0.8, 2)

    else:
        add_warmup(20, 15)
        add_warmup(target_weight_kg * 0.4, 8)
        add_warmup(target_weight_kg * 0.6, 4)
        add_warmup(target_weight_kg * 0.8, 2)
        add_warmup(target_weight_kg * 0.9, 1)

    return sorted(warmups, key=lambda x: x['weight_kg'])