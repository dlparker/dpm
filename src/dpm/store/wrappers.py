from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import json
import logging
from enum import StrEnum, auto

from sqlmodel import SQLModel, Field, Session, create_engine, select, Relationship
from dpm.store.models import Blocker, Project, Phase, Task

log = logging.getLogger(__name__)


class ProjectRecord:
    """Wrapper around Project model providing business logic and DB operations."""

    def __init__(self, model_db: "ModelDB",  project: Project):
        self.model_db = model_db
        self._project = project

    @property
    def project_id(self):
        return self._project.id

    @project_id.setter
    def project_id(self, value):
        self._project.id = value

    @property
    def name(self):
        return self._project.name

    @name.setter
    def name(self, value):
        self._project.name = value
        self._project.name_lower = value.lower()

    @property
    def description(self):
        return self._project.description

    @description.setter
    def description(self, value):
        self._project.description = value

    @property
    def parent_id(self):
        return self._project.parent_id

    @parent_id.setter
    def parent_id(self, value):
        self._project.parent_id = value

    @property
    def save_time(self):
        return self._project.save_time

    @property
    def parent(self):
        if self._project.parent_id:
            return self.model_db.get_project_by_id(self._project.parent_id)
        return None

    @parent.setter
    def parent(self, value):
        self._project.parent_id = value.project_id

    def __repr__(self):
        return f"project {self.project_id} {self.name[:20]}"

    def __eq__(self, other):
        if other and self.project_id:
            if self.project_id == other.project_id:
                return True
        return False

    def save(self):
        self.model_db.save_project_record(self)

    def get_kids(self):
        return self.model_db.get_projects_by_parent_id(self.project_id)

    def get_tasks(self):
        return self.model_db.get_tasks_for_project(self)

    def new_phase(self, name, description=None, follows=None):
        phases = self.get_phases()
        if follows:
            if follows not in phases:
                raise Exception('invalid follows spec on new phase, does not exist in project')
            follows_id = follows.phase_id
        else:
            follows_id = None
        return self.model_db.add_phase(name=name, description=description, project=self,
                                       follows_id=follows_id)

    def add_phase(self, phase, follows=None):
        phases = self.get_phases()
        follows_id = None
        if follows:
            if follows not in phases:
                raise Exception('invalid follows spec on new phase, does not exist in project')
            follows_id = follows.phase_id
        phase._phase.project_id = self.project_id
        phase._follows_id = follows_id
        new_phase = phase.save()
        # Update the passed phase with the new data from save
        if new_phase:
            phase._phase = new_phase._phase
            phase._follows_id = new_phase._follows_id
        return phase

    def get_phases(self):
        return self.model_db.get_phases_by_project_id(self.project_id)

    def delete_from_db(self):
        if self.project_id is None:
            return
        phases = self.get_phases()
        if self.parent_id:
            new_project = self.parent
        else:
            orphs = self.model_db.get_project_by_name('Orphans')
            if orphs is None:
                desc = "A project used to collect phases that are orphaned when "
                desc += "a project is deleted but still has phases. This is done "
                desc += "automatically. "
                orphs = self.model_db.add_project(name="Orphans", description=desc)
            new_project = orphs

        if len(phases) == 0:
            self.model_db.replace_task_project_refs(self.project_id, new_project.project_id)
        else:
            for phase in phases:
                phase.change_project(new_project.project_id)
        self.model_db.delete_project_record(self)
        self._project.id = None

    def to_json_dict(self):
        d = dict(
            project_id=self.project_id,
            name=self.name,
            description=self.description,
            parent_id=self.parent_id,
            save_time=self.save_time,
            model_db=self.model_db,
        )
        return FilterWrapper(d)


class PhaseRecord:
    """Wrapper around Phase model providing business logic and DB operations."""

    def __init__(self, model_db: "ModelDB", phase: Phase, follows_id: Optional[int] = None):
        self.model_db = model_db
        self._phase = phase
        self._follows_id = follows_id

    @property
    def phase_id(self):
        return self._phase.id

    @phase_id.setter
    def phase_id(self, value):
        self._phase.id = value

    @property
    def name(self):
        return self._phase.name

    @name.setter
    def name(self, value):
        self._phase.name = value
        self._phase.name_lower = value.lower()

    @property
    def description(self):
        return self._phase.description

    @description.setter
    def description(self, value):
        self._phase.description = value

    @property
    def project_id(self):
        return self._phase.project_id

    @project_id.setter
    def project_id(self, value):
        self._phase.project_id = value

    @property
    def follows_id(self):
        return self._follows_id

    @follows_id.setter
    def follows_id(self, value):
        self._follows_id = value

    @property
    def save_time(self):
        return self._phase.save_time

    @property
    def follows(self):
        if self._follows_id:
            return self.model_db.get_phase_by_id(self._follows_id)
        return None

    @follows.setter
    def follows(self, value):
        self._follows_id = value.phase_id

    @property
    def follower(self):
        return self.model_db.get_phase_that_follows(self.phase_id)

    @property
    def project(self):
        return self.model_db.get_project_by_id(self._phase.project_id)

    @project.setter
    def project(self, value):
        self._phase.project_id = value.project_id

    def __eq__(self, other):
        if other and self.phase_id:
            if self.phase_id == other.phase_id:
                return True
        return False

    def __repr__(self):
        return f"phase {self.phase_id} {self.name[:20]}"

    def save(self):
        return self.model_db.save_phase_record(self)

    def get_tasks(self):
        return self.model_db.get_tasks_for_phase(self)

    def change_project(self, new_project_id):
        new_version = self.model_db.move_phase_and_tasks_to_project(self.phase_id, new_project_id)
        self._phase = new_version._phase
        self._follows_id = new_version._follows_id

    def delete_from_db(self):
        if self.phase_id is None:
            return
        orig_id = self.phase_id
        self.model_db.replace_task_phase_refs(orig_id, None)
        follower = self.model_db.get_phase_that_follows(orig_id)
        if follower:
            save_link_id = self._follows_id
            follower._follows_id = None
            follower.save()
        self.model_db.delete_phase_record(self)
        if follower:
            follower._follows_id = save_link_id
            follower.save()
        self._phase.id = None



class TaskRecord:
    """Wrapper around Task model providing business logic and DB operations."""

    def __init__(self, model_db: "ModelDB", task: Task):
        self.model_db = model_db
        self._task = task

    @property
    def task_id(self):
        return self._task.id

    @task_id.setter
    def task_id(self, value):
        self._task.id = value

    @property
    def name(self):
        return self._task.name

    @name.setter
    def name(self, value):
        self._task.name = value
        self._task.name_lower = value.lower()

    @property
    def description(self):
        return self._task.description

    @description.setter
    def description(self, value):
        self._task.description = value

    @property
    def status(self):
        return self._task.status

    @status.setter
    def status(self, value):
        self._task.status = value

    @property
    def project_id(self):
        return self._task.project_id

    @project_id.setter
    def project_id(self, value):
        self._task.project_id = value

    @property
    def phase_id(self):
        return self._task.phase_id

    @phase_id.setter
    def phase_id(self, value):
        self._task.phase_id = value

    @property
    def save_time(self):
        return self._task.save_time

    @property
    def project(self):
        if self._task.project_id:
            return self.model_db.get_project_by_id(self._task.project_id)
        return None

    @project.setter
    def project(self, value):
        if self._task.project_id != value.project_id:
            if self._task.phase_id:
                self._task.phase_id = None
        self._task.project_id = value.project_id

    @property
    def phase(self):
        if self._task.phase_id:
            return self.model_db.get_phase_by_id(self._task.phase_id)
        return None

    @phase.setter
    def phase(self, value):
        self._task.phase_id = value.phase_id

    def __repr__(self):
        return f"task {self.task_id} {self.name[:20]}"

    def __eq__(self, other):
        if other and self.task_id:
            if self.task_id == other.task_id:
                return True
        return False

    def add_blocker(self, other_task):
        if other_task.task_id == self.task_id:
            raise Exception('would create loop')
        for other_need in other_task.get_blockers():
            if other_need.task_id == self.task_id:
                raise Exception('would create loop')
        return self.model_db.add_task_blocker(self, other_task)

    def delete_blocker(self, other_task):
        self.model_db.delete_task_blocker(self, other_task)

    def get_blockers(self, descend=False, only_not_done=True):
        res = self.model_db.get_task_blockers(self, only_not_done=only_not_done)
        if descend:
            orig = res
            for rec in orig:
                more = rec.get_blockers(descend=True, only_not_done=only_not_done)
                for item in more:
                    if item not in res:
                        res.append(item)
        return res

    def blocks_tasks(self, ascend=False):
        res = self.model_db.get_tasks_blocked(self)
        if ascend:
            orig = res
            for rec in orig:
                more = self.model_db.get_tasks_blocked(rec)
                if len(more) > 0:
                    res += more
        return res

    def save(self):
        if self.phase_id and not self.project_id:
            self.project_id = self.phase.project_id
        new_rec = self.model_db.save_task_record(self)
        self._task.id = new_rec.task_id
        return True

    def delete_from_db(self):
        if self.task_id is not None:
            self.model_db.delete_task_record(self)
            self._task.id = None

    def add_to_project(self, project):
        self._task.project_id = project.project_id
        self.save()

    def add_to_phase(self, phase, move_to_project=False):
        phase_project = phase.project
        if self.project_id is not None and not move_to_project:
            proj = self.model_db.get_project_by_id(self.project_id)
            if phase_project != proj:
                raise Exception(f'cannot add task to phase {phase}, it is not part of project {proj}')
        else:
            self._task.project_id = phase_project.project_id
        self._task.phase_id = phase.phase_id
        self.save()


class ModelDB:
    """SQLModel-based database for task management."""

    default_file_name = "model_db.sqlite"
    valid_status_values = ("ToDo", "Doing", "Done")

    def __init__(self, store_dir:Path, name_override=None, autocreate=False):
        if name_override:
            name = name_override
        else:
            name = self.default_file_name
        self.store_dir = store_dir
        self.name = name
        self.filepath = Path(store_dir, name).resolve()
        self.engine = None
        from dpm.store.sw_wrappers import SWModelDB
        self.sw_model_db = SWModelDB(self)
        log.debug("new sqlmodel store for model db, not open yet")
        if not self.filepath.exists():
            if autocreate:
                self.open()
            else:
                raise Exception(f'no {name} file in {store_dir} and no autocreate')
        else:
            self.open()
            
    def open(self) -> None:
        self.engine = create_engine(f"sqlite:///{self.filepath}", echo=False)
        SQLModel.metadata.create_all(self.engine)
        log.debug("created sqlmodel store for model_db")

    def close(self):
        if self.engine:
            self.engine.dispose()
            self.engine = None

    # Task methods
    def add_task(self, name, description=None, status='ToDo', project_id=None, phase_id=None):
        with Session(self.engine) as session:
            existing = session.exec(select(Task).where(Task.name_lower == name.lower())).first()
            if existing:
                raise Exception(f"Already have a task named {name}")
            if status not in self.valid_status_values:
                raise Exception(f"Status not valid: {status}")
            if not project_id and phase_id:
                phase = session.exec(select(Phase).where(Phase.id == phase_id)).first()
                if phase:
                    project_id = phase.project_id
            task = Task(
                name=name,
                name_lower=name.lower(),
                status=status,
                description=description or "",
                project_id=project_id,
                phase_id=phase_id,
            )
            session.add(task)
            session.commit()
            session.refresh(task)
            return TaskRecord(self, task)

    def get_task_by_name(self, name):
        with Session(self.engine) as session:
            task = session.exec(select(Task).where(Task.name_lower == name.lower())).first()
            if task:
                return TaskRecord(self, task)
            return None

    def get_task_by_id(self, tid):
        with Session(self.engine) as session:
            task = session.exec(select(Task).where(Task.id == tid)).first()
            if task:
                return TaskRecord(self, task)
            return None

    def get_tasks(self):
        with Session(self.engine) as session:
            tasks = session.exec(select(Task).order_by(Task.id)).all()
            return [TaskRecord(self, t) for t in tasks]

    def get_tasks_by_status(self, status):
        if status not in self.valid_status_values:
            raise Exception(f"Status not valid: {status}")
        with Session(self.engine) as session:
            tasks = session.exec(select(Task).where(Task.status == status).order_by(Task.id)).all()
            return [TaskRecord(self, t) for t in tasks]

    def get_tasks_by_project_id(self, project_id):
        with Session(self.engine) as session:
            tasks = session.exec(select(Task).where(Task.project_id == project_id).order_by(Task.id)).all()
            return [TaskRecord(self, t) for t in tasks]

    def get_tasks_by_phase_id(self, phase_id):
        with Session(self.engine) as session:
            tasks = session.exec(select(Task).where(Task.phase_id == phase_id).order_by(Task.id)).all()
            return [TaskRecord(self, t) for t in tasks]

    def get_tasks_for_project(self, record):
        if record.project_id is None:
            return []
        return self.get_tasks_by_project_id(record.project_id)

    def get_tasks_for_phase(self, record):
        if record.phase_id is None:
            return []
        return self.get_tasks_by_phase_id(record.phase_id)

    def save_task_record(self, record):
        with Session(self.engine) as session:
            if record.task_id is not None:
                existing = session.exec(select(Task).where(Task.id == record.task_id)).first()
                if not existing:
                    raise Exception(f"Trying to save task with invalid task_id")

            dup = session.exec(
                select(Task).where(Task.name_lower == record.name.lower(), Task.id != record.task_id)
            ).first()
            if dup:
                raise Exception(f"Already have a task named {record.name}")

            if record.phase_id:
                phase = session.exec(select(Phase).where(Phase.id == record.phase_id)).first()
                if not phase:
                    raise Exception(f"Trying to save task with invalid phase_id")
                if phase.project_id != record.project_id:
                    raise Exception(f"Task cannot be in phase but not in same project")

            if record.task_id is None:
                task = Task(
                    name=record.name,
                    name_lower=record.name.lower(),
                    description=record.description,
                    status=record.status,
                    project_id=record.project_id,
                    phase_id=record.phase_id,
                )
                session.add(task)
                session.commit()
                session.refresh(task)
                record._task = task
            else:
                task = session.exec(select(Task).where(Task.id == record.task_id)).first()
                if task:
                    task.name = record.name
                    task.name_lower = record.name.lower()
                    task.description = record.description
                    task.status = record.status
                    task.project_id = record.project_id
                    task.phase_id = record.phase_id
                    task.save_time = datetime.now()
                    session.add(task)
                    session.commit()
                    session.refresh(task)
                    record._task = task
            return record

    def delete_task_record(self, record):
        with Session(self.engine) as session:
            task = session.exec(select(Task).where(Task.id == record.task_id)).first()
            if task:
                session.delete(task)
                # Delete blockers
                blockers = session.exec(
                    select(Blocker).where((Blocker.item == record.task_id) | (Blocker.requires == record.task_id))
                ).all()
                for b in blockers:
                    session.delete(b)
                session.commit()

    def replace_task_project_refs(self, project_id, new_project_id):
        with Session(self.engine) as session:
            if new_project_id is not None:
                proj = session.exec(select(Project).where(Project.id == new_project_id)).first()
                if not proj:
                    raise Exception('Invalid project id')
            tasks = session.exec(select(Task).where(Task.project_id == project_id)).all()
            for task in tasks:
                task.project_id = new_project_id
                task.save_time = datetime.now()
                session.add(task)
            session.commit()

    def replace_task_phase_refs(self, phase_id, new_phase_id):
        if phase_id == new_phase_id:
            return
        with Session(self.engine) as session:
            if new_phase_id is None:
                tasks = session.exec(select(Task).where(Task.phase_id == phase_id)).all()
                for task in tasks:
                    task.phase_id = None
                    task.save_time = datetime.now()
                    session.add(task)
            else:
                new_phase = session.exec(select(Phase).where(Phase.id == new_phase_id)).first()
                if not new_phase:
                    raise Exception('Invalid phase id')
                tasks = session.exec(select(Task).where(Task.phase_id == phase_id)).all()
                for task in tasks:
                    task.phase_id = new_phase_id
                    task.project_id = new_phase.project_id
                    task.save_time = datetime.now()
                    session.add(task)
            session.commit()

    # Blocker methods
    def add_task_blocker(self, record, depends_on):
        with Session(self.engine) as session:
            existing = session.exec(
                select(Blocker).where(Blocker.item == record.task_id, Blocker.requires == depends_on.task_id)
            ).first()
            if existing:
                return existing.id
            blocker = Blocker(item=record.task_id, requires=depends_on.task_id)
            session.add(blocker)
            session.commit()
            session.refresh(blocker)
            return blocker.id

    def delete_task_blocker(self, record, depends_on):
        with Session(self.engine) as session:
            blocker = session.exec(
                select(Blocker).where(Blocker.item == record.task_id, Blocker.requires == depends_on.task_id)
            ).first()
            if blocker:
                session.delete(blocker)
                session.commit()

    def get_task_blockers(self, record, only_not_done=True):
        with Session(self.engine) as session:
            blockers = session.exec(select(Blocker).where(Blocker.item == record.task_id)).all()
            res = []
            for b in blockers:
                task = session.exec(select(Task).where(Task.id == b.requires)).first()
                if task:
                    if only_not_done:
                        if task.status != 'Done':
                            res.append(TaskRecord(self, task))
                    else:
                        res.append(TaskRecord(self, task))
            return res

    def get_tasks_blocked(self, record):
        with Session(self.engine) as session:
            blockers = session.exec(select(Blocker).where(Blocker.requires == record.task_id)).all()
            res = []
            for b in blockers:
                task = session.exec(select(Task).where(Task.id == b.item)).first()
                if task:
                    res.append(TaskRecord(self, task))
            return res

    # Project methods
    def add_project(self, name, description=None, parent_id=None, parent=None) -> ProjectRecord:
        with Session(self.engine) as session:
            existing = session.exec(select(Project).where(Project.name_lower == name.lower())).first()
            if existing:
                raise Exception(f"Already have a project named {name}")
            pid = None
            if parent_id is not None:
                pid = parent_id
            elif parent is not None:
                pid = parent.project_id
            if pid:
                proj = session.exec(select(Project).where(Project.id == pid)).first()
                if not proj:
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
            return ProjectRecord(self, project)

    def get_project_by_id(self, project_id) -> ProjectRecord:
        with Session(self.engine) as session:
            project = session.exec(select(Project).where(Project.id == project_id)).first()
            if project:
                return ProjectRecord(self, project)
            return None

    def get_project_by_name(self, name) -> ProjectRecord:
        with Session(self.engine) as session:
            project = session.exec(select(Project).where(Project.name_lower == name.lower())).first()
            if project:
                return ProjectRecord(self, project)
            return None

    def get_projects(self) -> list[ProjectRecord]:
        with Session(self.engine) as session:
            projects = session.exec(select(Project)).all()
            return [ProjectRecord(self, p) for p in projects]

    def get_projects_by_parent_id(self, parent_id) -> list[ProjectRecord]:
        with Session(self.engine) as session:
            if parent_id:
                projects = session.exec(select(Project).where(Project.parent_id == parent_id)).all()
            else:
                projects = session.exec(select(Project).where(Project.parent_id == None)).all()
            return [ProjectRecord(self, p) for p in projects]

    def save_project_record(self, record) -> ProjectRecord:
        with Session(self.engine) as session:
            if record.project_id is not None:
                existing = session.exec(select(Project).where(Project.id == record.project_id)).first()
                if not existing:
                    raise Exception(f"Trying to save project with invalid project_id")

            dup = session.exec(
                select(Project).where(Project.name_lower == record.name.lower(), Project.id != record.project_id)
            ).first()
            if dup:
                raise Exception(f"Already have a project named {record.name}")

            if record.project_id is None:
                project = Project(
                    name=record.name,
                    name_lower=record.name.lower(),
                    description=record.description,
                    parent_id=record.parent_id,
                )
                session.add(project)
                session.commit()
                session.refresh(project)
                record._project = project
            else:
                project = session.exec(select(Project).where(Project.id == record.project_id)).first()
                project.name = record.name # type: ignore
                project.name_lower = record.name.lower() # type: ignore
                project.description = record.description # type: ignore
                project.parent_id = record.parent_id # type: ignore
                project.save_time = datetime.now() # type: ignore
                session.add(project)
                session.commit()
                session.refresh(project)
                record._project = project
            return record

    def delete_project_record(self, record):
        # First, recursively delete children (must happen outside the session that deletes parent)
        children = self.get_projects_by_parent_id(record.project_id)
        for child in children:
            child.delete_from_db()

        with Session(self.engine) as session:
            project = session.exec(select(Project).where(Project.id == record.project_id)).first()
            if project:
                session.delete(project)
                session.commit()

    # Phase methods
    def add_phase(self,
                  name:str,
                  description:Optional[str]=None,
                  project_id:Optional[int]=None,
                  project: Optional[Project]=None,
                  follows_id: Optional[int]=None) -> PhaseRecord:
        return self._save_phase(name=name, description=description, phase_id=None,
                                project_id=project_id, project=project, follows_id=follows_id)

    def _save_phase(self, name, description=None, phase_id=None,
                    project_id=None, project=None, follows_id=None)  -> PhaseRecord:
        with Session(self.engine) as session:
            existing = session.exec(select(Phase).where(Phase.name_lower == name.lower())).first()
            if existing and existing.id != phase_id:
                raise Exception(f"Already have a phase named {name}")

            if project_id is None and project is None:
                raise Exception('phases must have a project')
            if project is not None:
                project_id = project.project_id

            proj = session.exec(select(Project).where(Project.id == project_id)).first()
            if not proj:
                raise Exception(f"Invalid project id supplied")

            if follows_id is None:
                last_phase = session.exec(
                    select(Phase).where(Phase.project_id == project_id).order_by(Phase.position.desc())
                ).first()
                if not last_phase:
                    position = 1.0
                else:
                    position = last_phase.position + 1.0
                    if last_phase.id != phase_id:
                        follows_id = last_phase.id
            else:
                if follows_id == phase_id:
                    raise Exception('phase cannot follow itself')
                follows_phase = session.exec(select(Phase).where(Phase.id == follows_id)).first()
                if not follows_phase:
                    raise Exception(f"Invalid phase id supplied for follows property")
                if follows_phase.project_id != project_id:
                    raise Exception(f"Phase linking through follows property limited to same project")

                next_phase = session.exec(
                    select(Phase).where(
                        Phase.project_id == project_id,
                        Phase.id != phase_id,
                        Phase.position > follows_phase.position
                    ).order_by(Phase.position) # type: ignore
                ).first()
                if not next_phase:
                    position = follows_phase.position + 1.0
                else:
                    offset = (next_phase.position - follows_phase.position) * 0.75
                    position = follows_phase.position + offset

            if phase_id is None:
                phase = Phase(
                    name=name,
                    name_lower=name.lower(),
                    description=description,
                    project_id=project_id,
                    position=position,
                )
                session.add(phase)
                session.commit()
                session.refresh(phase)
                return PhaseRecord(self, phase, follows_id)
            else:
                phase = session.exec(select(Phase).where(Phase.id == phase_id)).first()
                if not phase:
                    raise Exception("Supplied phase_id does not exist")
                phase.name = name
                phase.name_lower = name.lower()
                phase.description = description
                phase.project_id = project_id
                phase.position = position
                phase.save_time = datetime.now()
                session.add(phase)
                session.commit()
                session.refresh(phase)
                return PhaseRecord(self, phase, follows_id)

    def get_phase_by_id(self, phase_id) -> PhaseRecord:
        with Session(self.engine) as session:
            phase = session.exec(select(Phase).where(Phase.id == phase_id)).first()
            if not phase:
                return None
            follows_id = self._get_follows_id(session, phase)
            return PhaseRecord(self, phase, follows_id)

    def get_phase_by_name(self, name) -> PhaseRecord:
        with Session(self.engine) as session:
            phase = session.exec(select(Phase).where(Phase.name_lower == name.lower())).first()
            if not phase:
                return None
            follows_id = self._get_follows_id(session, phase)
            return PhaseRecord(self, phase, follows_id)

    def _get_follows_id(self, session, phase) -> int:
        prev = session.exec(
            select(Phase).where(
                Phase.project_id == phase.project_id,
                Phase.position < phase.position
            ).order_by(Phase.position.desc())
        ).first()
        return prev.id if prev else None

    def get_phases_by_project_id(self, project_id)  -> list[PhaseRecord]:
        with Session(self.engine) as session:
            phases = session.exec(
                select(Phase).where(Phase.project_id == project_id).order_by(Phase.position)
            ).all()
            result = []
            for phase in phases:
                follows_id = self._get_follows_id(session, phase)
                result.append(PhaseRecord(self, phase, follows_id))
            return result

    def get_phase_that_follows(self, follows_phase_id) -> PhaseRecord: 
        with Session(self.engine) as session:
            phase = session.exec(select(Phase).where(Phase.id == follows_phase_id)).first()
            if not phase:
                return None
            next_phase = session.exec(
                select(Phase).where(
                    Phase.project_id == phase.project_id,
                    Phase.position > phase.position
                ).order_by(Phase.position)
            ).first()
            if not next_phase:
                return None
            follows_id = self._get_follows_id(session, next_phase)
            return PhaseRecord(self, next_phase, follows_id)

    def save_phase_record(self, record)  -> PhaseRecord:
        result = self._save_phase(
            name=record.name,
            description=record.description,
            phase_id=record.phase_id,
            project_id=record.project_id,
            follows_id=record.follows_id,
        )
        # Update the original record with the saved data
        record._phase = result._phase
        record._follows_id = result._follows_id
        return record

    def delete_phase_record(self, record):
        with Session(self.engine) as session:
            phase = session.exec(select(Phase).where(Phase.id == record.phase_id)).first()
            if phase:
                session.delete(phase)
                session.commit()

    def move_phase_and_tasks_to_project(self, phase_id, new_project_id)  -> PhaseRecord:
        with Session(self.engine) as session:
            last_phase = session.exec(
                select(Phase).where(Phase.project_id == new_project_id).order_by(Phase.position.desc())
            ).first()
            if not last_phase:
                position = 1.0
                follows_id = None
            else:
                position = last_phase.position + 1.0
                follows_id = last_phase.id if last_phase.id != phase_id else None

            phase = session.exec(select(Phase).where(Phase.id == phase_id)).first()
            if not phase:
                raise Exception("consistency error")
            phase.project_id = new_project_id
            phase.position = position
            phase.save_time = datetime.now()
            session.add(phase)

            tasks = session.exec(select(Task).where(Task.phase_id == phase_id)).all()
            for task in tasks:
                task.project_id = new_project_id
                task.save_time = datetime.now()
                session.add(task)

            session.commit()
            session.refresh(phase)
            return PhaseRecord(self, phase, follows_id)

    def make_backup(self, store_dir, filename):
        otb = ModelDB(store_dir, name_override=filename, autocreate=True)

        for project in self.get_projects():
            if project.parent_id is not None:
                continue
            new_proj = Project(
                name=project.name,
                name_lower=project.name.lower(),
                description=project.description,
                parent_id=None,
            )
            with Session(otb.engine) as session:
                session.add(new_proj)
                session.commit()

        for project in self.get_projects():
            if project.parent_id is None:
                continue
            n_parent = otb.get_project_by_name(project.parent.name)
            new_proj = Project(
                name=project.name,
                name_lower=project.name.lower(),
                description=project.description,
                parent_id=n_parent.project_id,
            )
            with Session(otb.engine) as session:
                session.add(new_proj)
                session.commit()

        for project in self.get_projects():
            new_project = otb.get_project_by_name(project.name)
            for phase in project.get_phases():
                new_phase = otb.add_phase(
                    name=phase.name,
                    description=phase.description,
                    project_id=new_project.project_id,
                )
                for task in phase.get_tasks():
                    otb.add_task(
                        name=task.name,
                        description=task.description,
                        status=task.status,
                        project_id=new_project.project_id,
                        phase_id=new_phase.phase_id,
                    )
            for task in project.get_tasks():
                if task.phase_id is not None:
                    continue
                otb.add_task(
                    name=task.name,
                    description=task.description,
                    status=task.status,
                    project_id=new_project.project_id,
                )

        for o_task in self.get_tasks():
            n_task = otb.get_task_by_name(o_task.name)
            for o_b_task in o_task.get_blockers():
                n_b_task = otb.get_task_by_name(o_b_task.name)
                n_task.add_blocker(n_b_task)
                n_task.save()

        otb.close()
        return otb.filepath

