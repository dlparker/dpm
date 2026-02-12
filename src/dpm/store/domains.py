from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import json
from enum import StrEnum, auto

from dpm.store.wrappers import ModelDB, ProjectRecord, PhaseRecord, TaskRecord

class DomainMode(StrEnum):
    DEFAULT = auto()
    SOFTWARE = auto() # use Vision, Subsytem, Deliverable, Epic, Story, Task Taxons


@dataclass
class PMDBDomain:
    name: str
    db_path: Path
    description: str
    db: ModelDB
    domain_mode: Optional[DomainMode] = DomainMode.DEFAULT

@dataclass
class DomainCatalog:
    pmdb_domains: dict[str,PMDBDomain] = field(default_factory=dict[str,PMDBDomain])

    @classmethod
    def from_json_config(cls, config_path):
        with open(config_path) as f:
            config = json.load(f)
        assert "databases" in config
        assert isinstance(config['databases'], dict)
        catalog = cls()
        for name, data in config['databases'].items():
            assert "path" in data
            assert "description" in data
            path_str = data['path']
            if path_str.startswith('/'):
                path = Path(path_str)
            elif path_str.startswith('./'):
                path = config_path.parent / path_str
            else:
                raise Exception(f"cannot figure out path string {path_str}")
            assert path.exists()
            if "domain_mode" in data:
                mode = DomainMode(data['domain_mode'])
            else:
                mode = DomainMode.DEFAULT
            domain = PMDBDomain(name=name,
                                db_path=path,
                                description = data['description'],
                                db=ModelDB(store_dir=path.parent, name_override=path.name),
                                domain_mode=mode
                                )
            
            catalog.pmdb_domains[name] = domain
        return catalog

class DPMManager:

    def __init__(self, config_path: str):
        self._config_path = Path(config_path)
        self.domain_catalog = DomainCatalog.from_json_config(self._config_path)
        self.last_domain = None
        self.last_project = None
        self.last_phase = None
        self.last_task = None
        self._load_state()

    @property
    def _state_path(self) -> Path:
        return self._config_path.parent / ".dpm_state.json"

    def _load_state(self):
        """Load persisted state from disk."""
        if not self._state_path.exists():
            return
        with open(self._state_path) as f:
            state = json.load(f)

        # Restore domain
        domain = state.get("last_domain")
        if domain and domain in self.domain_catalog.pmdb_domains:
            self.last_domain = domain
            db = self.get_db_for_domain(domain)

            # Restore project
            project_id = state.get("last_project_id")
            if project_id is not None:
                self.last_project = db.get_project_by_id(project_id)

            # Restore phase
            phase_id = state.get("last_phase_id")
            if phase_id is not None:
                self.last_phase = db.get_phase_by_id(phase_id)

            # Restore task
            task_id = state.get("last_task_id")
            if task_id is not None:
                self.last_task = db.get_task_by_id(task_id)

    def _save_state(self):
        """Persist current state to disk."""
        state = {
            "last_domain": self.last_domain,
            "last_project_id": self.last_project.project_id if self.last_project else None,
            "last_phase_id": self.last_phase.phase_id if self.last_phase else None,
            "last_task_id": self.last_task.task_id if self.last_task else None,
        }
        with open(self._state_path, "w") as f:
            json.dump(state, f, indent=2)

    def get_db_for_domain(self, domain):
        return self.domain_catalog.pmdb_domains[domain].db

    def get_default_domain(self):
        if not self.last_domain:
            self.last_domain = next(iter(self.domain_catalog.pmdb_domains))
        return self.last_domain

    async def shutdown(self):
        for rec in self.domain_catalog.pmdb_domains.values():
            rec.db.close()

    def get_domains(self):
        return self.domain_catalog.pmdb_domains

    def set_last_domain(self, domain):
        if domain not in self.domain_catalog.pmdb_domains:
            raise Exception(f"No such domain {domain}")
        self.last_domain = domain
        self._save_state()

    def get_last_domain(self):
        return self.last_domain

    def set_last_project(self, domain:str, project: ProjectRecord):
        if domain not in self.domain_catalog.pmdb_domains:
            raise Exception(f"No such domain {domain}")
        self.last_domain = domain
        db = self.get_db_for_domain(domain)
        p_check = db.get_project_by_id(project_id=project.project_id)
        if p_check is None:
            raise Exception(f"No such project {project.project_id} {project.name} in domain {domain}")
        self.last_project = project
        self._save_state()

    def get_last_project(self):
        return self.last_project

    def set_last_phase(self, domain:str, phase: PhaseRecord):
        if domain not in self.domain_catalog.pmdb_domains:
            raise Exception(f"No such domain {domain}")
        self.last_domain = domain
        db = self.get_db_for_domain(domain)
        p_check = db.get_phase_by_id(phase_id=phase.phase_id)
        if p_check is None:
            raise Exception(f"No such phase {phase.phase_id} {phase.name} in domain {domain}")
        self.last_phase = phase
        self.last_project = phase.project
        self._save_state()

    def get_last_phase(self):
        return self.last_phase

    def set_last_task(self, domain:str, task: TaskRecord):
        if domain not in self.domain_catalog.pmdb_domains:
            raise Exception(f"No such domain {domain}")
        self.last_domain = domain
        db = self.get_db_for_domain(domain)
        p_check = db.get_task_by_id(task.task_id)
        if p_check is None:
            raise Exception(f"No such task {task.task_id} {task.name} in domain {domain}")
        self.last_task = task
        self.last_project = task.project
        if task.phase:
            self.last_phase = task.phase
        self._save_state()

    def get_last_task(self):
        return self.last_task
        

    
