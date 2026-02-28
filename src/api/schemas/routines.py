from typing import Optional, List, Union
from pydantic import BaseModel, Field, ConfigDict
from .common import ExerciseModel, RoutineExerciseTarget, RepRangeModel

class RoutineModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str
    title: str
    folder_id: Optional[Union[int, str]] = None
    updated_at: Optional[str] = None
    created_at: Optional[str] = None
    exercises: List[ExerciseModel] = Field(default_factory=list)

class PostRoutinesRequestSet(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    type: str
    weight_kg: Optional[float] = None
    reps: Optional[int] = None
    distance_meters: Optional[float] = None
    duration_seconds: Optional[float] = None
    custom_metric: Optional[float] = None
    rep_range: Optional[RepRangeModel] = None

class PostRoutinesRequestExercise(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    exercise_template_id: str
    superset_id: Optional[int] = None
    rest_seconds: Optional[int] = None
    notes: Optional[str] = None
    sets: List[PostRoutinesRequestSet]

class PostRoutinesRequestBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    title: str
    folder_id: Optional[int] = None
    notes: Optional[str] = None
    exercises: List[PostRoutinesRequestExercise]

class RoutineUpdatePayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    title: str
    notes: Optional[str] = None
    exercises: List[RoutineExerciseTarget]

class PutRoutinesRequestBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    routine: RoutineUpdatePayload

class PostRoutineFolderRequestBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    title: str
