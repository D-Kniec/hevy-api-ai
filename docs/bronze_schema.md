# Hevy Database Documentation (Bronze Layer)

**Schema:** Bronze (Raw Data)

**Database Engine:** SQLite

This document provides a complete schema reference for the raw data ingested from the Hevy API. All timestamps are in ISO 8601 format.

---

## 1. Enums & Type Definitions

Standardized values used across the database to ensure data consistency.

#### A. CustomExerciseType

Defines how an exercise set is measured.

```python
Literal[
    'weight_reps', 'reps_only', 'bodyweight_reps', 'bodyweight_assisted_reps',
    'duration', 'weight_duration', 'distance_duration', 'short_distance_weight'
]
```

#### B. EquipmentCategory

Classifies the equipment used.

```python
Literal[
    'none', 'barbell', 'dumbbell', 'kettlebell', 'machine', 'plate',
    'resistance_band', 'suspension', 'other'
]
```

#### C. MuscleGroup

Anatomical targets for exercises.

```python
Literal[
    'abdominals', 'shoulders', 'biceps', 'triceps', 'forearms', 'quadriceps',
    'hamstrings', 'calves', 'glutes', 'abductors', 'adductors', 'lats',
    'upper_back', 'traps', 'lower_back', 'chest', 'cardio', 'neck', 'full_body', 'other'
]
```

---

## 2. Table Definitions

### A. bronze.exercise_templates

Contains definitions for exercises available in the app (Legacy/Alternate Schema).

| Column | Description |
| --- | --- |
| `id` | Unique Template ID |
| `title` | Exercise Name |
| `exercise_type` | See CustomExerciseType Enum |
| `equipment_category` | See EquipmentCategory Enum |
| `muscle_group` | Primary Muscle Group |
| `is_custom` | Boolean (1/0) |
| `other_muscles_json` | JSON Array of secondary muscles |
| `ingestion_timestamp` | ETL Timestamp |

### B. bronze.ExerciseTemplate

Contains definitions for exercises (Current Schema).

| Column | Description |
| --- | --- |
| `id` | Unique Template ID |
| `title` | Exercise Name |
| `type` | See CustomExerciseType Enum |
| `primary_muscle_group` | Primary Muscle Group |
| `secondary_muscle_groups` | JSON Array |
| `is_custom` | Boolean (1/0) |
| `ingestion_timestamp` | ETL Timestamp |

### C. bronze.ExerciseHistoryEntry

Flattened historical view focusing on performance metrics per set.

| Column | Description |
| --- | --- |
| `workout_id` | Reference to Workout |
| `workout_title` | Name of the workout session |
| `workout_start_time` | Session start ISO timestamp |
| `workout_end_time` | Session end ISO timestamp |
| `exercise_template_id` | Reference to Exercise Template |
| `weight_kg` | Load in Kilograms |
| `reps` | Repetitions performed |
| `distance_meters` | Distance (if applicable) |
| `duration_seconds` | Duration (if applicable) |
| `rpe` | Rate of Perceived Exertion (1-10) |
| `custom_metric` | User defined metric |
| `set_type` | e.g., normal, warmup, failure |
| `ingestion_timestamp` | ETL Timestamp |

### D. bronze.PaginatedWorkoutEvents

Log of API events including workout creation, updates, and deletions.

| Column | Description |
| --- | --- |
| `workout_id` | Unique Workout ID |
| `workout_title` | Title |
| `description` | User notes/description |
| `start_time` | Start Timestamp |
| `end_time` | End Timestamp |
| `created_at` | Creation Timestamp |
| `routine_id` | Reference to source Routine |
| `ingestion_timestamp` | ETL Timestamp |
| `exercise_title` | Exercise Name |
| `exercise_template_id` | Template ID |
| `superset_id` | Grouping ID for supersets |
| `exercise_notes` | Specific exercise notes |
| `exercise_index` | Order in workout |
| `set_index` | Order of set |
| `set_type` | Set classification |
| `weight_kg` | Load |
| `reps` | Repetitions |
| `rpe` | Exertion Rating |
| `distance_meters` | Distance |
| `duration_seconds` | Duration |
| `custom_metric` | Custom Value |

### E. bronze.Routine

User-defined workout plans (Templates for future workouts).

| Column | Description |
| --- | --- |
| `routine_id` | Unique Routine ID |
| `title` | Routine Name |
| `folder_id` | Reference to Folder |
| `updated_at` | Last Update Timestamp |
| `created_at` | Creation Timestamp |
| `ingestion_timestamp` | ETL Timestamp |
| `exercise_index` | Order of exercise |
| `exercise_title` | Exercise Name |
| `exercise_notes` | Instructions |
| `rest_seconds` | Planned rest time |
| `exercise_template_id` | Template ID |
| `supersets_id` | Superset grouping |
| `set_index` | Set order |
| `set_type` | Set type |
| `weight_kg` | Planned Weight |
| `reps` | Planned Reps |
| `rep_range_start` | Min Reps |
| `rep_range_end` | Max Reps |
| `distance_meters` | Planned Distance |
| `duration_seconds` | Planned Duration |
| `rpe` | Target RPE |
| `custom_metric` | Target Custom Metric |

### F. bronze.RoutineFolder

Organizational structure for Routines.

| Column | Description |
| --- | --- |
| `id` | Folder ID |
| `index` | Sort Order |
| `title` | Folder Name |
| `updated_at` | Last Update |
| `created_at` | Creation Date |
| `ingestion_timestamp` | ETL Timestamp |

### G. bronze.Set

A granular list of all sets extracted from workouts.

| Column | Description |
| --- | --- |
| `workout_id` | Reference to Workout |
| `exercise_template_id` | Reference to Exercise |
| `index` | Set Order |
| `set_type` | Type (warmup, normal, etc) |
| `weight_kg` | Load |
| `reps` | Repetitions |
| `distance_meters` | Distance |
| `duration_seconds` | Duration |
| `rpe` | Exertion |
| `custom_metric` | Custom |
| `ingestion_timestamp` | ETL Timestamp |

### H. bronze.Workouts

The master table for executed workouts, fully denormalized.

| Column | Description |
| --- | --- |
| `workout_id` | Unique ID |
| `title` | Workout Name |
| `routine_id` | Source Routine ID |
| `description` | Notes |
| `start_time` | Start |
| `end_time` | End |
| `updated_at` | Last Update |
| `created_at` | Creation Date |
| `ingestion_timestamp` | ETL Timestamp |
| `exercise_index` | Exercise Order |
| `exercise_title` | Exercise Name |
| `exercise_notes` | Notes |
| `exercise_template_id` | Template ID |
| `supersets_id` | Superset Group |
| `set_index` | Set Order |
| `set_type` | Type |
| `weight_kg` | Load |
| `reps` | Repetitions |
| `distance_meters` | Distance |
| `duration_seconds` | Duration |
| `rpe` | RPE |
| `custom_metric` | Custom |

---
