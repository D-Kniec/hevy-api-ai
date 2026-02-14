# Hevy API: Full Schema Documentation (Write Operations)

Complete, nested schema definitions for POST and PUT operations. All JSON examples are fully expanded.

---

## 1. Workouts (POST)

### Schema: PostWorkoutsRequestSet

Represents a single set in a completed workout log.

```json

{
  "type": "normal",
  "weight_kg": 100,
  "reps": 10,
  "distance_meters": null,
  "duration_seconds": null,
  "custom_metric": null,
  "rpe": null
}

```

| Field | Type | Nullable | Description |
| --- | --- | --- | --- |
| type | string | No | Enum: `warmup`, `normal`, `failure`, `dropset`. |
| weight_kg | number | Yes | Weight in kg. |
| reps | integer | Yes | Number of repetitions. |
| distance_meters | integer | Yes | Distance in meters. |
| duration_seconds | integer | Yes | Duration in seconds. |
| custom_metric | number | Yes | Custom metric (steps/floors). |
| rpe | number | Yes | Rating of Perceived Exertion (1-10). |

### Schema: PostWorkoutsRequestExercise

Represents an exercise performed in a workout.

```json

{
  "exercise_template_id": "D04AC939",
  "superset_id": null,
  "notes": "Felt good today. Form was on point.",
  "sets": [
    {
      "type": "normal",
      "weight_kg": 100,
      "reps": 10,
      "distance_meters": null,
      "duration_seconds": null,
      "custom_metric": null,
      "rpe": null
    }
  ]
}

```

| Field | Type | Nullable | Description |
| --- | --- | --- | --- |
| exercise_template_id | string | No | ID of the exercise template. |
| superset_id | integer | Yes | ID of the superset. |
| notes | string | Yes | Additional notes. |
| sets | Array | No | List of `PostWorkoutsRequestSet`. |

### Schema: PostWorkoutsRequestBody

The top-level payload to create a workout.

```json

{
  "workout": {
    "title": "Friday Leg Day 🔥",
    "description": "Medium intensity leg day focusing on quads.",
    "start_time": "2024-08-14T12:00:00Z",
    "end_time": "2024-08-14T12:30:00Z",
    "is_private": false,
    "exercises": [
      {
        "exercise_template_id": "D04AC939",
        "superset_id": null,
        "notes": "Felt good today. Form was on point.",
        "sets": [
          {
            "type": "normal",
            "weight_kg": 100,
            "reps": 10,
            "distance_meters": null,
            "duration_seconds": null,
            "custom_metric": null,
            "rpe": null
          }
        ]
      }
    ]
  }
}

```

| Field | Type | Nullable | Description |
| --- | --- | --- | --- |
| title | string | No | The title of the workout. |
| description | string | Yes | A description for the workout. |
| start_time | string | No | ISO 8601 timestamp. |
| end_time | string | No | ISO 8601 timestamp. |
| is_private | boolean | No | Indicates if the workout is private. |
| exercises | Array | No | List of `PostWorkoutsRequestExercise`. |

---

## 2. Routines (POST)

### Schema: PostRoutinesRequestSet

Represents a target set in a routine template. Includes `rep_range` instead of `rpe`.

```json

{
  "type": "normal",
  "weight_kg": 100,
  "reps": 10,
  "distance_meters": null,
  "duration_seconds": null,
  "custom_metric": null,
  "rep_range": {
    "start": 8,
    "end": 12
  }
}

```

| Field | Type | Nullable | Description |
| --- | --- | --- | --- |
| type | string | No | Enum: `warmup`, `normal`, `failure`, `dropset`. |
| weight_kg | number | Yes | Target weight. |
| reps | integer | Yes | Target reps. |
| distance_meters | integer | Yes | Target distance. |
| duration_seconds | integer | Yes | Target duration. |
| custom_metric | number | Yes | Target metric. |
| rep_range | Object | Yes | Object: `{ start: number, end: number }`. |

### Schema: PostRoutinesRequestExercise

Represents a planned exercise. Includes `rest_seconds`.

```json

{
  "exercise_template_id": "D04AC939",
  "superset_id": null,
  "rest_seconds": 90,
  "notes": "Stay slow and controlled.",
  "sets": [
    {
      "type": "normal",
      "weight_kg": 100,
      "reps": 10,
      "distance_meters": null,
      "duration_seconds": null,
      "custom_metric": null,
      "rep_range": {
        "start": 8,
        "end": 12
      }
    }
  ]
}

```

| Field | Type | Nullable | Description |
| --- | --- | --- | --- |
| exercise_template_id | string | No | ID of the exercise template. |
| superset_id | integer | Yes | ID of the superset. |
| rest_seconds | integer | Yes | Rest time in seconds. |
| notes | string | Yes | Additional notes. |
| sets | Array | No | List of `PostRoutinesRequestSet`. |

### Schema: PostRoutinesRequestBody

The top-level payload to create a Routine. Includes `folder_id`.

```json

{
  "routine": {
    "title": "April Leg Day 🔥",
    "folder_id": null,
    "notes": "Focus on form over weight. Remember to stretch.",
    "exercises": [
      {
        "exercise_template_id": "D04AC939",
        "superset_id": null,
        "rest_seconds": 90,
        "notes": "Stay slow and controlled.",
        "sets": [
          {
            "type": "normal",
            "weight_kg": 100,
            "reps": 10,
            "distance_meters": null,
            "duration_seconds": null,
            "custom_metric": null,
            "rep_range": {
              "start": 8,
              "end": 12
            }
          }
        ]
      }
    ]
  }
}

```

| Field | Type | Nullable | Description |
| --- | --- | --- | --- |
| title | string | No | The title of the routine. |
| folder_id | number | Yes | Target folder ID. Pass `null` for root. |
| notes | string | Yes | Additional notes. |
| exercises | Array | No | List of `PostRoutinesRequestExercise`. |

---

## 3. Routines (PUT)

### Schema: PutRoutinesRequestSet

Identical to POST Set.

```json

{
  "type": "normal",
  "weight_kg": 100,
  "reps": 10,
  "distance_meters": null,
  "duration_seconds": null,
  "custom_metric": null,
  "rep_range": {
    "start": 8,
    "end": 12
  }
}

```

### Schema: PutRoutinesRequestExercise

Identical to POST Exercise.

```json

{
  "exercise_template_id": "D04AC939",
  "superset_id": null,
  "rest_seconds": 90,
  "notes": "Stay slow and controlled.",
  "sets": [
    {
      "type": "normal",
      "weight_kg": 100,
      "reps": 10,
      "distance_meters": null,
      "duration_seconds": null,
      "custom_metric": null,
      "rep_range": {
        "start": 8,
        "end": 12
      }
    }
  ]
}

```

### Schema: PutRoutinesRequestBody

The top-level payload to UPDATE a Routine. **Note:** `folder_id` is NOT present here.

```json

{
  "routine": {
    "title": "April Leg Day 🔥",
    "notes": "Focus on form over weight. Remember to stretch.",
    "exercises": [
      {
        "exercise_template_id": "D04AC939",
        "superset_id": null,
        "rest_seconds": 90,
        "notes": "Stay slow and controlled.",
        "sets": [
          {
            "type": "normal",
            "weight_kg": 100,
            "reps": 10,
            "distance_meters": null,
            "duration_seconds": null,
            "custom_metric": null,
            "rep_range": {
              "start": 8,
              "end": 12
            }
          }
        ]
      }
    ]
  }
}

```

| Field | Type | Nullable | Description |
| --- | --- | --- | --- |
| title | string | No | The title of the routine. |
| notes | string | Yes | Additional notes. |
| exercises | Array | No | List of `PutRoutinesRequestExercise`. |

---

## 4. Routine Folders (POST)

### Schema: PostRoutineFolderRequestBody

```json

{
  "routine_folder": {
    "title": "Push Pull 🏋️‍♂️"
  }
}

```

| Field | Type | Nullable | Description |
| --- | --- | --- | --- |
| title | string | No | The title of the routine folder. |




## 5. Silver Layer Write Operations

```mermaid
---
config:
  layout: dagre
---
erDiagram
    %% Słowniki
    ExerciseTemplate ||--o{ RoutineExercise : defines
    ExerciseTemplate ||--o{ WorkoutExercise : defines
    RoutineFolder ||--o{ Routine : contains

    %% Oś Planowania (Routines)
    Routine ||--|{ RoutineExercise : contains
    RoutineExercise ||--|{ RoutineSet : contains

    %% Oś Wykonania (Workouts)
    Workout ||--|{ WorkoutExercise : contains
    WorkoutExercise ||--|{ WorkoutSet : contains

    %% Powiązanie historyczne (opcjonalne)
    Routine ||--o{ Workout : "based on"

    ExerciseTemplate {
        string id PK
        string title
        string muscle_group
    }

    RoutineFolder {
        int id PK
        string title
    }

    Routine {
        string id PK
        string title
        int folder_id FK "Nullable"
        string notes
    }

    RoutineExercise {
        int id PK
        string routine_id FK
        string template_id FK
        int superset_id
        int rest_seconds
        int order_index
    }

    RoutineSet {
        int id PK
        int routine_exercise_id FK
        string type
        float weight_kg
        int reps_min "From rep_range"
        int reps_max "From rep_range"
    }

    Workout {
        string id PK
        string title
        datetime start_time
        datetime end_time
        string routine_id FK "Nullable"
    }

    WorkoutExercise {
        int id PK
        string workout_id FK
        string template_id FK
        int superset_id
    }

    WorkoutSet {
        int id PK
        int workout_exercise_id FK
        string type
        float weight_kg
        int reps
        float rpe
    }
        ```

---
