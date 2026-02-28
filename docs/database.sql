-- ==========================================
-- BRONZE LAYER (Raw Ingested API Data)
-- ==========================================

CREATE TABLE bronze_exercise_templates (
    id TEXT PRIMARY KEY,
    title TEXT,
    type TEXT,
    primary_muscle_group TEXT,
    secondary_muscle_groups TEXT, -- JSON Array
    is_custom INTEGER,            -- Boolean 1/0
    ingestion_timestamp TEXT
);

CREATE TABLE bronze_routines (
    routine_id TEXT PRIMARY KEY,
    title TEXT,
    folder_id TEXT,
    updated_at TEXT,
    created_at TEXT,
    ingestion_timestamp TEXT
);

CREATE TABLE bronze_routine_details (
    routine_id TEXT,
    exercise_index INTEGER,
    exercise_title TEXT,
    exercise_notes TEXT,
    rest_seconds INTEGER,
    exercise_template_id TEXT,
    superset_id INTEGER,
    set_index INTEGER,
    set_type TEXT,
    weight_kg REAL,
    reps INTEGER,
    rep_range_start INTEGER,
    rep_range_end INTEGER,
    distance_meters REAL,
    duration_seconds REAL,
    rpe REAL,
    custom_metric REAL,
    ingestion_timestamp TEXT
);

CREATE TABLE bronze_workouts (
    workout_id TEXT PRIMARY KEY,
    title TEXT,
    description TEXT,
    start_time TEXT,
    end_time TEXT,
    updated_at TEXT,
    created_at TEXT,
    routine_id TEXT,
    ingestion_timestamp TEXT
);

CREATE TABLE bronze_workout_exercises (
    workout_id TEXT,
    exercise_index INTEGER,
    title TEXT,
    notes TEXT,
    exercise_template_id TEXT,
    superset_id INTEGER,
    ingestion_timestamp TEXT
);

CREATE TABLE bronze_workout_sets (
    workout_id TEXT,
    exercise_index INTEGER,
    set_index INTEGER,
    set_type TEXT,
    weight_kg REAL,
    reps INTEGER,
    distance_meters REAL,
    duration_seconds REAL,
    rpe REAL,
    custom_metric REAL,
    ingestion_timestamp TEXT
);

CREATE TABLE bronze_RoutineSCD2 (
    routine_id TEXT,
    title TEXT,
    folder_id TEXT,
    updated_at TEXT,
    created_at TEXT,
    exercise_index INTEGER,
    exercise_title TEXT,
    exercise_notes TEXT,
    rest_seconds INTEGER,
    exercise_template_id TEXT,
    superset_id INTEGER,
    set_index INTEGER,
    set_type TEXT,
    weight_kg REAL,
    reps INTEGER,
    rep_range_start REAL,
    rep_range_end REAL,
    distance_meters REAL,
    duration_seconds REAL,
    rpe REAL,
    custom_metric REAL,
    scd_valid_from TEXT,
    scd_valid_to TEXT,
    scd_is_current INTEGER, -- Boolean 1/0
    scd_hash TEXT
);

-- ==========================================
-- SILVER LAYER (Cleaned & Dimensional Data)
-- ==========================================

CREATE TABLE silver_dim_exercise (
    exercise_template_id TEXT PRIMARY KEY,
    exercise_name TEXT,
    exercise_type TEXT,
    equipment_category TEXT,
    primary_muscle_group TEXT,
    is_custom_exercise TEXT,
    exercise_hierarchy_name TEXT,
    progression_step_kg REAL
);

CREATE TABLE silver_dim_routine (
    routine_id TEXT PRIMARY KEY,
    routine_name TEXT,
    folder_id TEXT,
    created_at TEXT,
    last_updated_at TEXT,
    unique_exercises_count INTEGER,
    total_exercises_count INTEGER,
    total_sets_count INTEGER
);

CREATE TABLE silver_fact_workout_history (
    workout_id TEXT,
    routine_id TEXT,
    exercise_template_id TEXT,
    folder_id TEXT,
    cycle_number INTEGER,
    set_type TEXT,
    set_index INTEGER,
    execution_status TEXT,
    diff_weight_kg REAL,
    diff_reps INTEGER,
    diff_duration_seconds REAL,
    diff_custom_metric REAL,
    weight_kg REAL,
    reps INTEGER,
    distance_meters REAL,
    duration_seconds REAL,
    rpe REAL,
    custom_metric REAL,
    planned_weight_kg REAL,
    planned_reps INTEGER,
    planned_distance_meters REAL,
    planned_duration_seconds REAL,
    planned_custom_metric REAL,
    planned_rest INTEGER,
    start_time TEXT,
    updated_at TEXT
);

-- ==========================================
-- GOLD LAYER (Business / AI Prompt View)
-- ==========================================

CREATE TABLE gold_prompt (
    routine_id TEXT,
    routine_name TEXT,
    cycle_number INTEGER,
    exercise_index INTEGER,
    exercise_template_id TEXT,
    exercise_name TEXT,
    primary_muscle_group TEXT,
    progression_step_kg REAL,
    set_index INTEGER,
    set_type TEXT,
    actual_weight_kg REAL,
    actual_reps INTEGER,
    rpe REAL,
    planned_weight_kg REAL,
    planned_reps INTEGER,
    planned_rest INTEGER,
    execution_status TEXT,
    diff_weight_kg REAL,
    diff_reps INTEGER
);
