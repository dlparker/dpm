from enum import StrEnum, auto
from typing import Optional, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship
if TYPE_CHECKING:
    from dpm.store.models import Project, Phase, Task

class GuardrailType(StrEnum):
    PRODUCTION = auto()
    MVP = auto()
    PROTOTYPE = auto()
    POC = auto()
    STUDY = auto()
    RESEARCH = auto()

class Vision(SQLModel, table=True):
    __table_args__ = {'sqlite_autoincrement': True}
    id: Optional[int] = Field(default=None, primary_key=True)

    project_id: int = Field(foreign_key="project.id", unique=True, nullable=False)
    project: "Project" = Relationship(back_populates="vision")

class Subsystem(SQLModel, table=True):
    __table_args__ = {'sqlite_autoincrement': True}
    id: Optional[int] = Field(default=None, primary_key=True)

    project_id: int = Field(foreign_key="project.id", unique=True, nullable=False)
    project: "Project" = Relationship(back_populates="subsystem")
    
class Deliverable(SQLModel, table=True):
    __table_args__ = {'sqlite_autoincrement': True}
    id: Optional[int] = Field(default=None, primary_key=True)

    project_id: int = Field(foreign_key="project.id", unique=True, nullable=False)
    project: "Project" = Relationship(back_populates="deliverable")
    
class Epic(SQLModel, table=True):
    __table_args__ = {'sqlite_autoincrement': True}
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", unique=True, nullable=False)
    guardrail_type: GuardrailType =  Field(default=GuardrailType.PRODUCTION)

    project: "Project" = Relationship(back_populates="epic")

class Story(SQLModel, table=True):
    __table_args__ = {'sqlite_autoincrement': True}
    id: Optional[int] = Field(default=None, primary_key=True)
    phase_id: int = Field(foreign_key="phase.id", unique=True, nullable=False)
    guardrail_type: GuardrailType =  Field(default=GuardrailType.PRODUCTION)

    phase: "Phase" = Relationship(back_populates="story")


class SWTask(SQLModel, table=True):
    __table_args__ = {'sqlite_autoincrement': True}
    id: Optional[int] = Field(default=None, primary_key=True)
    task_id: int = Field(foreign_key="task.id", unique=True, nullable=False)
    guardrail_type: GuardrailType =  Field(default=GuardrailType.PRODUCTION)

    task: "Task" = Relationship(back_populates="sw_task")
    

