-- ============================================================
-- src/etl/queries.sql
-- Hevy_API_AI: ETL Query Reference
-- All queries target the SQLite file at data/bronze_layer.db
-- Tables follow dot-notation namespacing:
--   bronze.*   -> raw ingested data
--   silver.*   -> cleaned, typed, SCD2-tracked dimensions
--   gold.*     -> prompt-ready aggregation views
-- ============================================================


-- ============================================================
-- SECTION 1: SILVER LAYER - DIMENSIONS
-- ============================================================


-- ------------------------------------------------------------
-- silver.dim_exercise
-- Joins exercise templates with progression steps from
-- data/progression.py. Progression steps are loaded into a
-- temporary table by 02_silver.py before this query runs.
-- ------------------------------------------------------------
SELECT
    id                                          AS exercise_template_id,
    title                                       AS exercise_name,
    COALESCE(type, 'Other')                     AS exercise_type,
    'Unknown'                                   AS equipment_category,
    COALESCE(primary_muscle_group, 'Other')     AS primary_muscle_group,
    CASE
        WHEN is_custom = 1 THEN 'Yes'
        ELSE 'No'
    END                                         AS is_custom_exercise,
    COALESCE(primary_muscle_group, 'Other') || ' - ' || title AS exercise_hierarchy_name
FROM bronze_exercise_templates;


-- ------------------------------------------------------------
-- silver.dim_routine
-- Aggregates routine metadata. Counts unique exercises and
-- sets to give a structural overview of each routine.
-- ------------------------------------------------------------
SELECT
    routine_id,
    MAX(title)                              AS routine_name,
    MAX(folder_id)                          AS folder_id,
    MIN(created_at)                         AS created_at,
    MAX(updated_at)                         AS last_updated_at,
    COUNT(DISTINCT exercise_template_id)    AS unique_exercises_count,
    COUNT(DISTINCT exercise_index)          AS total_exercises_count,
    COUNT(DISTINCT set_index)               AS total_sets_count
FROM bronze_routine_details
GROUP BY routine_id;


-- ============================================================
-- SECTION 2: SILVER LAYER - FACT TABLE
-- ============================================================


-- ------------------------------------------------------------
-- silver.fact_workout_history
-- Core transformation. Performs a FULL OUTER JOIN between:
--   actual    -> sets performed in logged workouts
--   planned   -> sets defined in the routine at the time of
--                the workout (retrieved via SCD2 from
--                bronze_RoutineSCD2 using temporal ranges)
--
-- Computes:
--   - cycle_number:     How many times this exercise in this
--                       routine has been performed (DENSE_RANK)
--   - execution_status: Granular comparison of actual vs planned
--                       weight, reps, duration, and distance.
--   - diff_*:           Delta between actual and planned values.
-- ------------------------------------------------------------
WITH actual AS (
    SELECT
        workout_id,
        routine_id,
        start_time,
        end_time,
        updated_at,
        exercise_template_id,
        exercise_index,
        set_index,
        set_type,
        weight_kg,
        reps,
        distance_meters,
        duration_seconds,
        COALESCE(rpe, 7)    AS rpe,
        custom_metric,
        workout_id || '-' || routine_id || '-' || exercise_template_id
            || '-' || exercise_index || '-' || set_type || '-' || set_index AS join_key
    FROM bronze_workouts
    WHERE routine_id IS NOT NULL
),

workout_headers AS (
    SELECT DISTINCT workout_id, routine_id, start_time
    FROM actual
),

applicable_plan AS (
    SELECT
        wh.workout_id,
        wh.start_time           AS workout_start_time,
        p.updated_at,
        p.routine_id,
        p.folder_id,
        p.rest_seconds          AS planned_rest,
        p.exercise_template_id,
        p.exercise_index,
        p.set_index,
        p.set_type,
        p.weight_kg             AS planned_weight_kg,
        p.reps                  AS planned_reps,
        p.distance_meters       AS planned_distance_meters,
        p.duration_seconds      AS planned_duration_seconds,
        p.custom_metric         AS planned_custom_metric,
        wh.workout_id || '-' || p.routine_id || '-' || p.exercise_template_id
            || '-' || p.exercise_index || '-' || p.set_type || '-' || p.set_index AS join_key
    FROM workout_headers wh
    INNER JOIN bronze_RoutineSCD2 p
        ON  wh.routine_id = p.routine_id
        AND wh.start_time >= p.scd_valid_from
        AND (wh.start_time < p.scd_valid_to OR p.scd_valid_to IS NULL)
)

SELECT
    COALESCE(a.workout_id,      p.workout_id)               AS workout_id,
    COALESCE(a.routine_id,      p.routine_id)               AS routine_id,
    COALESCE(a.exercise_template_id, p.exercise_template_id) AS exercise_template_id,
    p.folder_id,

    DENSE_RANK() OVER (
        PARTITION BY COALESCE(a.exercise_template_id, p.exercise_template_id),
                     COALESCE(a.routine_id, p.routine_id)
        ORDER BY COALESCE(a.start_time, p.workout_start_time)
    )                                                        AS cycle_number,

    COALESCE(a.set_type,    p.set_type)                     AS set_type,
    COALESCE(a.set_index,   p.set_index)                    AS set_index,

    CASE
        WHEN a.workout_id IS NULL
            THEN 'Skipped'
        WHEN p.join_key IS NULL
            THEN 'Unplanned'
        WHEN COALESCE(a.weight_kg, 0)       > COALESCE(p.planned_weight_kg, 0)
         AND COALESCE(a.reps, 0)            > COALESCE(p.planned_reps, 0)
            THEN 'Overperformed: Heavier & More Reps'
        WHEN COALESCE(a.weight_kg, 0)       > COALESCE(p.planned_weight_kg, 0)
         AND COALESCE(a.reps, 0)            < COALESCE(p.planned_reps, 0)
            THEN 'Mixed: Heavier but Fewer Reps'
        WHEN COALESCE(a.weight_kg, 0)       > COALESCE(p.planned_weight_kg, 0)
            THEN 'Overperformed: Heavier'
        WHEN COALESCE(a.weight_kg, 0)       < COALESCE(p.planned_weight_kg, 0)
         AND COALESCE(a.reps, 0)            > COALESCE(p.planned_reps, 0)
            THEN 'Mixed: Lighter but More Reps'
        WHEN COALESCE(a.weight_kg, 0)       < COALESCE(p.planned_weight_kg, 0)
            THEN 'Underperformed: Lighter'
        WHEN COALESCE(a.reps, 0)            > COALESCE(p.planned_reps, 0)
            THEN 'Overperformed: More Reps'
        WHEN COALESCE(a.reps, 0)            < COALESCE(p.planned_reps, 0)
            THEN 'Underperformed: Fewer Reps'
        WHEN COALESCE(a.duration_seconds, 0) > COALESCE(p.planned_duration_seconds, 0)
            THEN 'Overperformed: Longer Duration'
        WHEN COALESCE(a.duration_seconds, 0) < COALESCE(p.planned_duration_seconds, 0)
            THEN 'Underperformed: Shorter Duration'
        WHEN COALESCE(a.custom_metric, 0)   > COALESCE(p.planned_custom_metric, 0)
            THEN 'Overperformed: Higher Custom Metric'
        WHEN COALESCE(a.custom_metric, 0)   < COALESCE(p.planned_custom_metric, 0)
            THEN 'Underperformed: Lower Custom Metric'
        WHEN COALESCE(p.planned_weight_kg, 0) = 0
         AND COALESCE(p.planned_distance_meters, 0) = 0
            THEN 'Target Met: Free/Bodyweight'
        ELSE 'Target Met'
    END AS execution_status,

    a.weight_kg         - p.planned_weight_kg       AS diff_weight_kg,
    a.reps              - p.planned_reps             AS diff_reps,
    a.duration_seconds  - p.planned_duration_seconds AS diff_duration_seconds,
    a.custom_metric     - p.planned_custom_metric    AS diff_custom_metric,

    a.weight_kg,
    a.reps,
    a.distance_meters,
    a.duration_seconds,
    a.rpe,
    a.custom_metric,

    p.planned_weight_kg,
    p.planned_reps,
    p.planned_distance_meters,
    p.planned_duration_seconds,
    p.planned_custom_metric,
    p.planned_rest,

    COALESCE(a.start_time, p.workout_start_time)     AS start_time,
    COALESCE(a.updated_at, p.updated_at)             AS updated_at

FROM actual a
FULL OUTER JOIN applicable_plan p ON a.join_key = p.join_key

ORDER BY COALESCE(a.updated_at, p.updated_at) DESC;


-- ============================================================
-- SECTION 3: GOLD LAYER - PROMPT VIEW
-- ============================================================


-- ------------------------------------------------------------
-- gold.prompt
-- Final, prompt-ready aggregation used by the AI Agent.
-- Exposes the exercise index from the FIRST time the exercise
-- appeared in the routine (MIN via current_indices CTE) to
-- ensure stable ordering across cycles even if the user
-- reordered exercises later.
-- ------------------------------------------------------------
WITH current_indices AS (
    SELECT
        routine_id,
        exercise_template_id,
        MIN(exercise_index)     AS exercise_index
    FROM bronze_routine_details
    GROUP BY routine_id, exercise_template_id
)

SELECT
    f.routine_id,
    r.routine_name,
    f.cycle_number,
    idx.exercise_index,
    f.exercise_template_id,
    e.exercise_name,
    e.primary_muscle_group,
    e.progression_step_kg,
    f.set_index,
    f.set_type,
    f.weight_kg             AS actual_weight_kg,
    f.reps                  AS actual_reps,
    f.rpe,
    f.planned_weight_kg,
    f.planned_reps,
    f.planned_rest,
    f.execution_status,
    f.diff_weight_kg,
    f.diff_reps
FROM silver_fact_workout_history f
LEFT JOIN silver_dim_exercise e
    ON  f.exercise_template_id = e.exercise_template_id
LEFT JOIN silver_dim_routine r
    ON  f.routine_id = r.routine_id
LEFT JOIN current_indices idx
    ON  f.routine_id = idx.routine_id
    AND f.exercise_template_id = idx.exercise_template_id
WHERE
    f.execution_status != 'Unplanned'
    AND f.workout_id IS NOT NULL
ORDER BY
    f.routine_id,
    f.cycle_number          ASC,
    idx.exercise_index      ASC,
    f.exercise_template_id,
    f.set_index;
