from typing import Optional, List, Union
from pydantic import BaseModel, Field, ConfigDict

class ExerciseTemplateModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: Union[str, int]
    title: str
    exercise_type: Optional[str] = Field(alias="type", default=None)
    primary_muscle_group: Optional[str] = None
    secondary_muscle_groups: List[str] = Field(default_factory=list)
    is_custom: Optional[bool] = False
