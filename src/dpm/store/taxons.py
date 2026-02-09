from enum import StrEnum, auto
from typing import Optional, TYPE_CHECKING
from datetime import datetime

from sqlmodel import SQLModel, Field

if TYPE_CHECKING:
    from dpm.store.models import ModelDB


class DPMBase(StrEnum):
    domain = auto()
    project = auto()
    phase = auto()
    task = auto()


class TaxonDef(SQLModel, table=True):
    __tablename__ = 'taxon_def'
    __table_args__ = {'sqlite_autoincrement': True}
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    name_lower: str = Field(index=True, unique=True)
    covers_dpm: str
    allow_multiple: bool = Field(default=True)
    parent_id: Optional[int] = Field(default=None, foreign_key="taxon_def.id")
    save_time: Optional[datetime] = Field(default_factory=datetime.now)


class TaxonLevel(SQLModel, table=True):
    __tablename__ = 'taxon_level'
    __table_args__ = {'sqlite_autoincrement': True}
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    name_lower: str = Field(index=True)
    taxo_type: str
    taxon_def_id: int = Field(foreign_key="taxon_def.id")
    parent_level_id: Optional[int] = Field(default=None, foreign_key="taxon_level.id")
    domain_name: Optional[str] = None
    project_id: Optional[int] = Field(default=None, foreign_key="project.id")
    phase_id: Optional[int] = Field(default=None, foreign_key="phase.id")
    task_id: Optional[int] = Field(default=None, foreign_key="task.id")
    description: Optional[str] = None
    save_time: Optional[datetime] = Field(default_factory=datetime.now)


class TaxonDefRecord:
    """Wrapper around TaxonDef model providing business logic and DB operations."""

    def __init__(self, model_db: "ModelDB", taxon_def: TaxonDef):
        self.model_db = model_db
        self._taxon_def = taxon_def

    @property
    def taxon_def_id(self):
        return self._taxon_def.id

    @taxon_def_id.setter
    def taxon_def_id(self, value):
        self._taxon_def.id = value

    @property
    def name(self):
        return self._taxon_def.name

    @name.setter
    def name(self, value):
        self._taxon_def.name = value
        self._taxon_def.name_lower = value.lower()

    @property
    def covers_dpm(self):
        return DPMBase(self._taxon_def.covers_dpm)

    @covers_dpm.setter
    def covers_dpm(self, value):
        self._taxon_def.covers_dpm = str(value)

    @property
    def allow_multiple(self):
        return self._taxon_def.allow_multiple

    @allow_multiple.setter
    def allow_multiple(self, value):
        self._taxon_def.allow_multiple = value

    @property
    def parent_id(self):
        return self._taxon_def.parent_id

    @parent_id.setter
    def parent_id(self, value):
        self._taxon_def.parent_id = value

    @property
    def save_time(self):
        return self._taxon_def.save_time

    @property
    def parent(self):
        if self._taxon_def.parent_id:
            return self.model_db.get_taxon_def_by_id(self._taxon_def.parent_id)
        return None

    @parent.setter
    def parent(self, value):
        self._taxon_def.parent_id = value.taxon_def_id

    @property
    def children(self):
        return self.model_db.get_taxon_defs_by_parent_id(self.taxon_def_id)

    def get_child_by_name(self, name):
        """Search descendants for a TaxonDefRecord with the given name."""
        name_lower = name.lower()
        for child in self.children:
            if child._taxon_def.name_lower == name_lower:
                return child
            found = child.get_child_by_name(name)
            if found:
                return found
        return None

    def __repr__(self):
        return f"taxon_def {self.taxon_def_id} {self.name[:20]}"

    def __eq__(self, other):
        if other and self.taxon_def_id:
            if self.taxon_def_id == other.taxon_def_id:
                return True
        return False

    def save(self):
        self.model_db.save_taxon_def_record(self)

    def delete_from_db(self):
        if self.taxon_def_id is not None:
            self.model_db.delete_taxon_def_record(self)
            self._taxon_def.id = None

    def to_json_dict(self):
        from dpm.store.models import FilterWrapper
        d = dict(
            taxon_def_id=self.taxon_def_id,
            name=self.name,
            covers_dpm=str(self.covers_dpm),
            allow_multiple=self.allow_multiple,
            parent_id=self.parent_id,
            save_time=self.save_time,
            model_db=self.model_db,
        )
        return FilterWrapper(d)


class TaxonLevelRecord:
    """Wrapper around TaxonLevel model providing business logic and DB operations."""

    def __init__(self, model_db: "ModelDB", taxon_level: TaxonLevel):
        self.model_db = model_db
        self._taxon_level = taxon_level

    @property
    def taxon_level_id(self):
        return self._taxon_level.id

    @taxon_level_id.setter
    def taxon_level_id(self, value):
        self._taxon_level.id = value

    @property
    def name(self):
        return self._taxon_level.name

    @name.setter
    def name(self, value):
        self._taxon_level.name = value
        self._taxon_level.name_lower = value.lower()

    @property
    def taxo_type(self):
        return DPMBase(self._taxon_level.taxo_type)

    @property
    def taxon_def_id(self):
        return self._taxon_level.taxon_def_id

    @property
    def taxo_def(self):
        return self.model_db.get_taxon_def_by_id(self._taxon_level.taxon_def_id)

    @property
    def parent_level_id(self):
        return self._taxon_level.parent_level_id

    @property
    def parent_level(self):
        if self._taxon_level.parent_level_id:
            return self.model_db.get_taxon_level_by_id(self._taxon_level.parent_level_id)
        return None

    @property
    def domain_name(self):
        return self._taxon_level.domain_name

    @property
    def project_id(self):
        return self._taxon_level.project_id

    @property
    def phase_id(self):
        return self._taxon_level.phase_id

    @property
    def task_id(self):
        return self._taxon_level.task_id

    @property
    def description(self):
        return self._taxon_level.description

    @description.setter
    def description(self, value):
        self._taxon_level.description = value

    @property
    def save_time(self):
        return self._taxon_level.save_time

    @property
    def dpm_model(self):
        """Get the underlying DPM object (project/phase/task record)."""
        if self.taxo_type == DPMBase.project and self.project_id:
            return self.model_db.get_project_by_id(self.project_id)
        elif self.taxo_type == DPMBase.phase and self.phase_id:
            return self.model_db.get_phase_by_id(self.phase_id)
        elif self.taxo_type == DPMBase.task and self.task_id:
            return self.model_db.get_task_by_id(self.task_id)
        return None

    @property
    def domain_level(self):
        """Walk up the parent chain to find the domain-level ancestor."""
        if self.taxo_type == DPMBase.domain:
            return self
        parent = self.parent_level
        while parent:
            if parent.taxo_type == DPMBase.domain:
                return parent
            parent = parent.parent_level
        return None

    def add_project_level(self, taxon_def_record:TaxonDefRecord, name:str, description=None):
        """Add a project sub-level under this level."""
        domain_level = self.domain_level
        parent_level = None if self.taxo_type == DPMBase.domain else self
        return self.model_db.add_taxon_level_for_project(
            domain_level, taxon_def_record, name,
            parent_level=parent_level, description=description,
        )

    def add_phase_level(self, taxon_def_record:TaxonDefRecord, name:str, description=None):
        """Add a phase sub-level under this project level."""
        return self.model_db.add_taxon_level_for_phase(
            self, taxon_def_record, name, description=description,
        )

    def add_task_level(self, taxon_def_record:TaxonDefRecord, name:str, description=None):
        """Add a task sub-level under this level."""
        return self.model_db.add_taxon_level_for_task(
            self, taxon_def_record, name, description=description,
        )

    def add_child(self, taxon_def_record:TaxonDefRecord, name:str, description=None):
        if taxon_def_record.covers_dpm == DPMBase.project:
            return self.add_project_level(taxon_def_record, name, description)
        elif taxon_def_record.covers_dpm == DPMBase.phase:
            return self.add_phase_level(taxon_def_record, name, description)
        elif taxon_def_record.covers_dpm == DPMBase.task:
            return self.add_task_level(taxon_def_record, name, description)
        else:
            raise Exception(f'no such type "{taxon_def_record.covers_dpm}"')
            
    def get_children(self):
        return self.model_db.get_taxon_levels_by_parent_id(self.taxon_level_id)

    def __repr__(self):
        return f"taxon_level {self.taxon_level_id} {self.name[:20]}"

    def __eq__(self, other):
        if other and self.taxon_level_id:
            if self.taxon_level_id == other.taxon_level_id:
                return True
        return False

    def save(self):
        self.model_db.save_taxon_level_record(self)

    def delete_from_db(self):
        if self.taxon_level_id is not None:
            self.model_db.delete_taxon_level_record(self)
            self._taxon_level.id = None

    def to_json_dict(self):
        from dpm.store.models import FilterWrapper
        d = dict(
            taxon_level_id=self.taxon_level_id,
            name=self.name,
            taxo_type=str(self.taxo_type),
            taxon_def_id=self.taxon_def_id,
            parent_level_id=self.parent_level_id,
            domain_name=self.domain_name,
            project_id=self.project_id,
            phase_id=self.phase_id,
            task_id=self.task_id,
            description=self.description,
            save_time=self.save_time,
            model_db=self.model_db,
        )
        return FilterWrapper(d)

def build_software_taxonomy(model_db: "ModelDB"):
    
    taxonomy = model_db.add_taxon_def(
        name="Software Project",
        covers_dpm=DPMBase.domain,
    )
    vision = model_db.add_taxon_def(
        name="Vision",
        covers_dpm=DPMBase.project,
        parent_id=taxonomy.taxon_def_id,
        allow_multiple=False,
    )
    deliverable = model_db.add_taxon_def(
        name="Deliverable",
        covers_dpm=DPMBase.project,
        parent_id=vision.taxon_def_id,
    )
    epic = model_db.add_taxon_def(
        name="Epic",
        covers_dpm=DPMBase.project,
        parent_id=deliverable.taxon_def_id,
    )
    story = model_db.add_taxon_def(
        name="Story",
        covers_dpm=DPMBase.phase,
        parent_id=epic.taxon_def_id,
    )
    task = model_db.add_taxon_def(
        name="Task",
        covers_dpm=DPMBase.task,
        parent_id=story.taxon_def_id,
    )
    return taxonomy
    
def build_software_suite_taxonomy(model_db: "ModelDB"):
    
    taxonomy = model_db.add_taxon_def(
        name="Software Project Suite",
        covers_dpm=DPMBase.domain,
    )
    vision = model_db.add_taxon_def(
        name="Vision",
        covers_dpm=DPMBase.project,
        parent_id=taxonomy.taxon_def_id,
        allow_multiple=False,
    )
    subsystem = model_db.add_taxon_def(
        name="Subsystem",
        covers_dpm=DPMBase.project,
        parent_id=vision.taxon_def_id,
        allow_multiple=False,
    )
    deliverable = model_db.add_taxon_def(
        name="Deliverable",
        covers_dpm=DPMBase.project,
        parent_id=subsystem.taxon_def_id,
    )
    epic = model_db.add_taxon_def(
        name="Epic",
        covers_dpm=DPMBase.project,
        parent_id=deliverable.taxon_def_id,
    )
    story = model_db.add_taxon_def(
        name="Story",
        covers_dpm=DPMBase.phase,
        parent_id=epic.taxon_def_id,
    )
    task = model_db.add_taxon_def(
        name="Task",
        covers_dpm=DPMBase.task,
        parent_id=story.taxon_def_id,
    )
    return taxonomy
    
