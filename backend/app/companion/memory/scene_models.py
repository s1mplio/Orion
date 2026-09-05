from typing import List, Optional

from pydantic import BaseModel, Field


class HandState(BaseModel):
    hand: Optional[str] = None
    relation: Optional[str] = None
    target: Optional[str] = None


class ActivityState(BaseModel):
    type: Optional[str] = None
    description: Optional[str] = None


class PoseState(BaseModel):
    body_state: Optional[str] = None
    head_direction: Optional[str] = None

    left_hand: Optional[HandState] = None
    right_hand: Optional[HandState] = None


class PersonState(BaseModel):
    label: str = "person"

    activity: Optional[ActivityState] = None

    pose: Optional[PoseState] = None

    position: Optional[str] = None

    clothing: Optional[str] = None

    visible_accessories: List[str] = Field(
        default_factory=list
    )


class SceneObject(BaseModel):
    label: str

    position: Optional[str] = None

    state: Optional[str] = None


class StructuredScene(BaseModel):
    """
    Machine-readable representation
    of one visual observation.

    Important:
    - observation keeps a human-readable summary
    - people/activity/pose are structured for comparison
    - objects/accessories remain explicit
    """

    observation: str

    environment: Optional[str] = None

    people: List[PersonState] = Field(
        default_factory=list
    )

    objects: List[SceneObject] = Field(
        default_factory=list
    )

    visible_text: List[str] = Field(
        default_factory=list
    )

    salient_event: Optional[str] = None