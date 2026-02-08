from enum import StrEnum, auto
from typing import Optional

from dpm.store.models import (ModelDB, TaskRecord, ProjectRecord, PhaseRecord,
                                FilterWrapper, Task, Project, Phase,
                                DPMManager, DomainCatalog)

class DPMBase(StrEnum):
    domain = auto()
    project = auto()
    phase = auto()
    task = auto()
    
class TaxoDef:
    """ Used to define a taxonomy"""
    
    def __init__(self,
                 covers_dpm: DPMBase,
                 name: str,
                 allow_multiple: Optional[bool] = True,
                 parent: Optional['TaxoDef'] = None):
        self.covers_dpm = covers_dpm
        self.name = name,
        self.allow_multiple = allow_multiple,
        self.parent = parent,
        self.children = []


class TaxoLevel:
    """ Used to hold a taxonomy instance"""
    def __init__(self, taxo_type: DPMBase, taxo_def: TaxoDef, name:str):
        self.taxo_type = taxo_type
        self.taxo_def = taxo_def
        self.name = name
        self.dpm_model = None
        
class TaxoLevelForDomain(TaxoLevel):

    def __init__(self, catalog: DomainCatalog, taxo_def: TaxoDef, name:str):
        super().__init__(DPMBase.domain, taxo_def, name)
        if name not in catalog.pmdb_domains:
            raise Exception(f'must create domain "{name}" before trying to set a taxonomy level using it')
        self.dpm_domain = catalog.pmdb_domains[name]
          
class TaxoLevelForProject(TaxoLevel):

    def __init__(self,
                 domain_level:TaxoLevelForDomain,
                 taxo_def: TaxoDef,
                 name:str,
                 parent_level: Optional['TaxoLevelForProject'] = None,
                 description:Optional[str] = None):
        super().__init__(DPMBase.project, taxo_def, name)
        self.description = description
        self.domain_level = domain_level
        self.db = domain_level.dpm_domain.db
        self.parent_level = parent_level
        parent_project_id = None if parent_level is None else parent_level.dpm_model.parent_id 
        self.dpm_model = self.db.add_project(self.name, self.description, parent_id=parent_project_id)
      
class TaxoLevelForPhase(TaxoLevel):
    def __init__(self,
                 taxo_def: TaxoDef,
                 name:str,
                 project_level: TaxoLevelForProject,
                 description:Optional[str] = None):
        super().__init__(DPMBase.phase, taxo_def, name)
        self.project_level = project_level
        self.domain_level = project_level.domain_level
        self.description = description
        self.db = self.domain_level.dpm_domain.db
        self.dpm_model = self.db.add_phase(self.name, self.description, project_id=project_level.dpm_model.project_id)
      
class TaxoLevelForTask(TaxoLevel):
    
    def __init__(self,
                 taxo_def: TaxoDef,
                 name:str, parent_level:[TaxoLevelForProject | TaxoLevelForPhase],
                 description:Optional[str] = None):
        super().__init__(DPMBase.domain, taxo_def, name)
        self.parent_level = parent_level
        if self.parent_level.taxo_type == DPMBase.phase:
            self.project_level = self.parent_level.project_level
            dpm_project_id = self.parent_level.dpm_model.project.project_id
            dpm_phase_id = self.parent_level.dpm_model.phase_id
        else:
            self.project_level = self.parent_level
            dpm_project = self.parent_level.dpm_model.project_id
            dpm_phase = None
        self.domain_level = self.project_level.domain_level
        self.db = self.domain_level.dpm_domain.db
        self.dpm_model = self.db.add_task(name=name,
                                          description=description,
                                          project_id=dpm_project_id,
                                          phase_id=dpm_phase_id)


