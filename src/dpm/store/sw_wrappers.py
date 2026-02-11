from typing import Optional, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Session, create_engine, select, Relationship

from dpm.store.sw_models import Epic
from dpm.store.models import Project
from dpm.store.domains import PMDBDomain
from dpm.store.wrappers import  ModelDB, ProjectRecord

class EpicRecord(ProjectRecord):

    def __init__(self, model_db: ModelDB, epic: Epic, project: Project):
        super().__init__(model_db=model_db, project=project)
        self._epic = epic

    @property
    def epic_id(self):
        return self._epic.id

class SWModelDB:

    def __init__(self, model_db: ModelDB):
        self.model_db = model_db

    def add_epic(self, domain: PMDBDomain, name: str,
                 description: Optional[str] = None,
                 parent: Optional[Project] = None):
        with Session(self.model_db.engine) as session:
            existing = session.exec(select(Project).where(Project.name_lower == name.lower())).first()
            if existing:
                raise Exception(f"Already have a project named {name}")
            pid = None
            if parent is not None:
                pid = parent.id
            if pid:
                p_proj = session.exec(select(Project).where(Project.id == pid)).first()
                if not p_proj:
                    raise Exception(f"Invalid parent id supplied")
            project = Project(
                name=name,
                name_lower=name.lower(),
                description=description or "",
                parent_id=pid,
            )
            session.add(project)
            session.commit()
            session.refresh(project)
            epic = Epic(project_id=project.id) # type: ignore
            session.add(epic)
            session.commit()
            session.refresh(project)
            return EpicRecord(self.model_db, epic, project)
                 
    
