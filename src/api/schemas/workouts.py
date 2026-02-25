from typing import Optional, List, Union
from pydantic import BaseModel, Field, ConfigDict
from .common import ExerciseModel

class WorkoutModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: Union[str, int]
    title: str
    description: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    updated_at: Optional[str] = None
    created_at: Optional[str] = None
    routine_id: Optional[str] = None
    exercises: List[ExerciseModel] = Field(default_factory=list)

class PostWorkoutsRequestSet(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    type: str
    weight_kg: Optional[float] = None
    reps: Optional[int] = None
    distance_meters: Optional[float] = None
    duration_seconds: Optional[float] = None
    custom_metric: Optional[float] = None
    rpe: Optional[float] = None

class PostWorkoutsRequestExercise(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    exercise_template_id: str
    superset_id: Optional[int] = None
    notes: Optional[str] = None
    sets: List[PostWorkoutsRequestSet]

class PostWorkoutsRequestBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    title: str
    description: Optional[str] = None
    start_time: str
    end_time: str
    is_private: bool = False
    exercises: List[PostWorkoutsRequestExercise]
