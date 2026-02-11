from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import json
import logging
from enum import StrEnum, auto

from sqlmodel import SQLModel, Field, Relationship
from dpm.store.sw_models import Vision, Subsystem, Deliverable, Epic, Story, SWTask


log = logging.getLogger(__name__)

class Blocker(SQLModel, table=True):
    __tablename__ = 'blockers'  # type: ignore  Match TaskDB table name
    __table_args__ = {'sqlite_autoincrement': True}
    id: Optional[int] = Field(default=None, primary_key=True)
    item: int = Field(index=True)
    requires: int = Field(index=True)


class Project(SQLModel, table=True):
    __table_args__ = {'sqlite_autoincrement': True}
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    name_lower: str = Field(index=True, unique=True)
    description: Optional[str] = None
    save_time: Optional[datetime] = Field(default_factory=datetime.now)
    parent_id: Optional[int] = Field(default=None, foreign_key="project.id")

    # Relationships
    phases: list["Phase"] = Relationship(back_populates="project")
    tasks: list["Task"] = Relationship(back_populates="project")

    vision: Optional[Vision] = Relationship(back_populates="project")
    subsystem: Optional[Subsystem] = Relationship(back_populates="project")
    deliverable: Optional[Deliverable] = Relationship(back_populates="project")
    epic: Optional[Epic] = Relationship(back_populates="project")
 
class Phase(SQLModel, table=True):
    __table_args__ = {'sqlite_autoincrement': True}
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    name_lower: str = Field(index=True, unique=True)
    description: Optional[str] = None
    project_id: int = Field(foreign_key="project.id")
    position: float = Field(default=1.0)
    save_time: Optional[datetime] = Field(default_factory=datetime.now)

    # Relationships
    project: Optional[Project] = Relationship(back_populates="phases")
    tasks: list["Task"] = Relationship(back_populates="phase")

    story: Optional[Story] = Relationship(back_populates="phase")

class Task(SQLModel, table=True):
    __table_args__ = {'sqlite_autoincrement': True}
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    name_lower: str = Field(index=True, unique=True)
    status: str
    description: Optional[str] = None
    project_id: Optional[int] = Field(default=None, foreign_key="project.id")
    phase_id: Optional[int] = Field(default=None, foreign_key="phase.id")
    save_time: Optional[datetime] = Field(default_factory=datetime.now)

    # Relationships
    project: Optional[Project] = Relationship(back_populates="tasks")
    phase: Optional[Phase] = Relationship(back_populates="tasks")

    sw_task: Optional[SWTask] = Relationship(back_populates="task")
    
