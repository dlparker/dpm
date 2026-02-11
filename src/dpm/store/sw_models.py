from typing import Optional, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Session, create_engine, select, Relationship
if TYPE_CHECKING:
    from dpm.store.models import ModelDB, PMDBDomain, Project


class Epic(SQLModel, table=True):
    __table_args__ = {'sqlite_autoincrement': True}
    id: Optional[int] = Field(default=None, primary_key=True)

    # Foreign key + NOT NULL + UNIQUE → enforces exactly one Epic per Project
    project_id: int = Field(foreign_key="project.id", unique=True, nullable=False)

    # Back-reference to the owning Project (single object)
    project: "Project" = Relationship(back_populates="epic")


