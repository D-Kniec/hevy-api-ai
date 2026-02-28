from typing import Optional, List, Union
from pydantic import BaseModel, Field, ConfigDict

class RepRangeModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    start: Optional[float] = None
    end: Optional[float] = None

class RepRangeTarget(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    start: int
    end: int

class SetModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    index: int
    set_type: str = Field(alias="type")
    weight_kg: Optional[float] = None
    reps: Optional[int] = None
    rep_range: Optional[RepRangeModel] = None
    distance_meters: Optional[float] = None
    duration_seconds: Optional[float] = None
    rpe: Optional[float] = None
    custom_metric: Optional[float] = None

class ExerciseModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    index: int
    title: str
    notes: Optional[str] = None
    rest_seconds: Optional[int] = None
    exercise_template_id: str
    superset_id: Optional[int] = None
    sets: List[SetModel] = Field(default_factory=list)

class RoutineSetTarget(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    set_type: str = Field(alias="type")
    weight_kg: Optional[float] = None
    reps: Optional[int] = None
    distance_meters: Optional[float] = None
    duration_seconds: Optional[float] = None
    custom_metric: Optional[float] = None
    rep_range: Optional[RepRangeTarget] = None

class RoutineExerciseTarget(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    exercise_template_id: str
    superset_id: Optional[int] = None
    rest_seconds: Optional[int] = None
    notes: Optional[str] = None
    sets: List[RoutineSetTarget]
