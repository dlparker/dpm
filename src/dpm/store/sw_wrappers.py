from typing import Optional
from sqlmodel import Session, select
from dpm.store.sw_models import Vision, Subsystem, Deliverable, Epic, Story, SWTask
from dpm.store.models import Project, Phase, Task
from dpm.store.domains import PMDBDomain
from dpm.store.wrappers import  ModelDB, ProjectRecord, PhaseRecord, TaskRecord


class VisionRecord(ProjectRecord):

    def __init__(self, model_db: ModelDB, vision: Vision):
        super().__init__(model_db=model_db, project=vision.project)
        self._vision = vision

    @property
    def vision_id(self):
        return self._vision.id

class SubsystemRecord(ProjectRecord):

    def __init__(self, model_db: ModelDB, subsystem: Subsystem):
        super().__init__(model_db=model_db, project=subsystem.project)
        self._subsystem = subsystem

    @property
    def subsystem_id(self):
        return self._subsystem.id


class DeliverableRecord(ProjectRecord):

    def __init__(self, model_db: ModelDB, deliverable: Deliverable):
        super().__init__(model_db=model_db, project=deliverable.project)
        self._deliverable = deliverable

    @property
    def deliverable_id(self):
        return self._deliverable.id

class EpicRecord(ProjectRecord):

    def __init__(self, model_db: ModelDB, epic: Epic):
        super().__init__(model_db=model_db, project=epic.project)
        self._epic = epic

    @property
    def epic_id(self) -> int:
        return self._epic.id # type: ignore

    @property
    def project(self) -> ProjectRecord:
        return self.model_db.get_project_by_id(self.project_id)

    @property
    def project_model(self) -> Project:
        return self.model_db.get_project_by_id(self.project_id)._project


class StoryRecord(PhaseRecord):

    def __init__(self, model_db: ModelDB, story: Story):
        super().__init__(model_db=model_db, phase=story.phase)
        self._story = story

    @property
    def story_id(self):
        return self._story.id

class SWTaskRecord(TaskRecord):

    def __init__(self, model_db: ModelDB, swtask: SWTask):
        super().__init__(model_db=model_db, task=swtask.task)
        self._swtask = swtask

    @property
    def swtask_id(self):
        return self._swtask.id


class SWModelDB:

    def __init__(self, model_db: ModelDB):
        self.model_db = model_db

    def add_proj_base(self, domain: PMDBDomain, name: str,
                 description: Optional[str] = None,
                 parent_id: Optional[int] = None):
        with Session(self.model_db.engine) as session:
            existing = session.exec(select(Project).where(Project.name_lower == name.lower())).first()
            if existing:
                raise Exception(f"Already have a project named {name}")
            if parent_id:
                p_proj = session.exec(select(Project).where(Project.id == parent_id)).first()
                if not p_proj:
                    raise Exception(f"Invalid parent id supplied")
            project = Project(
                name=name,
                name_lower=name.lower(),
                description=description or "",
                parent_id=parent_id
            )
            session.add(project)
            session.commit()
            session.refresh(project)
        return project
    
    def add_vision(self, domain: PMDBDomain, name: str,
                 description: Optional[str] = None) -> VisionRecord:
        project = self.add_proj_base(domain, name, description)
        with Session(self.model_db.engine) as session:
            vision = Vision(project_id=project.id) # type: ignore
            session.add(vision)
            session.commit()
            session.refresh(vision)
            return VisionRecord(self.model_db, vision)
        
    def add_subsystem(self, domain: PMDBDomain, name: str,
                      description: Optional[str] = None,
                      vision: Optional[VisionRecord] = None) -> SubsystemRecord:
        parent_id = None
        if vision:
            parent_id = vision.project_id
        project = self.add_proj_base(domain, name, description, parent_id)
        with Session(self.model_db.engine) as session:
            subsystem = Subsystem(project_id=project.id, parent_id=parent_id) # type: ignore
            session.add(subsystem)
            session.commit()
            session.refresh(subsystem)
            return SubsystemRecord(self.model_db, subsystem)
        
    def add_deliverable(self, domain: PMDBDomain, name: str,
                        description: Optional[str] = None,
                        vision: Optional[VisionRecord] = None,
                        subsystem: Optional[SubsystemRecord] = None) -> DeliverableRecord:
        parent_id = None
        if subsystem:
            parent_id = subsystem.project_id
        elif vision:
            parent_id = vision.project_id
        project = self.add_proj_base(domain, name, description, parent_id)
        with Session(self.model_db.engine) as session:
            deliverable = Deliverable(project_id=project.id, parent_id=parent_id) # type: ignore
            session.add(deliverable)
            session.commit()
            session.refresh(deliverable)
            return DeliverableRecord(self.model_db, deliverable)
        
    def add_epic(self, domain: PMDBDomain, name: str,
                 description: Optional[str] = None,
                 vision: Optional[VisionRecord] = None,
                 subsystem: Optional[SubsystemRecord] = None,
                 deliverable: Optional[DeliverableRecord] = None) -> EpicRecord:

        parent_id = None
        if deliverable:
            parent_id = deliverable.project_id
        elif subsystem:
            parent_id = subsystem.project_id
        elif vision:
            parent_id = vision.project_id
        project = self.add_proj_base(domain, name, description, parent_id)
        with Session(self.model_db.engine) as session:
            epic = Epic(project_id=project.id, parent_id=parent_id) # type: ignore
            session.add(epic)
            session.commit()
            session.refresh(epic)
            return EpicRecord(self.model_db, epic)
                 
    def add_story(self, domain: PMDBDomain, name: str,
                  description: Optional[str] = None,
                  vision: Optional[VisionRecord] = None,
                  subsystem: Optional[SubsystemRecord] = None,
                  deliverable: Optional[DeliverableRecord] = None,
                  epic: Optional[Epic] = None) -> StoryRecord:

        project_id = None
        if epic:
            project_id = epic.project_id
        elif deliverable:
            project_id = deliverable.project_id
        elif subsystem:
            project_id = subsystem.project_id
        elif vision:
            project_id = vision.project_id
        if project_id is None:
            raise Exception(f"cannot add story '{name}' without an Epic, Deliverable, Subsystem of Vision to hang it on")
        
        with Session(self.model_db.engine) as session:
            existing = session.exec(select(Phase).where(Phase.name_lower == name.lower())).first()
            if existing:
                raise Exception(f"Already have a phase named {name}")
            p_proj = session.exec(select(Project).where(Project.id == project_id)).first()
            if not p_proj:
                raise Exception(f"Invalid project id supplied")
            phase = Phase(
                name=name,
                name_lower=name.lower(),
                description=description or "",
                project_id=project_id
            )
            session.add(phase)
            session.commit()
            session.refresh(phase)
        with Session(self.model_db.engine) as session:
            story = Story(phase_id=phase.id) # type: ignore
            session.add(story)
            session.commit()
            session.refresh(story)
            return StoryRecord(self.model_db, story)


    def add_task(self,
                 domain: PMDBDomain,
                 name: str,
                 description: Optional[str] = None,
                 vision: Optional[VisionRecord] = None,
                 subsystem: Optional[SubsystemRecord] = None,
                 deliverable: Optional[DeliverableRecord] = None,
                 epic: Optional[Epic] = None,
                 story: Optional[Story] = None,
                 ) -> SWTaskRecord:

        project_id = None
        phase_id = None
        if story:
            project_id = story.project_id
            phase_id = story.phase_id
        elif epic:
            project_id = epic.project_id
        elif deliverable:
            project_id = deliverable.project_id
        elif subsystem:
            project_id = subsystem.project_id
        elif vision:
            project_id = vision.project_id
        if project_id is None:
            raise Exception(f"cannot add task '{name}' without a Story, Epic, Deliverable, Subsystem or Vision to hang it on")
        
        with Session(self.model_db.engine) as session:
            existing = session.exec(select(Task).where(Task.name_lower == name.lower())).first()
            if existing:
                raise Exception(f"Already have a task named {name}")
            p_proj = session.exec(select(Project).where(Project.id == project_id)).first()
            if not p_proj:
                raise Exception(f"Invalid project id supplied")
            if phase_id:
                phase = session.exec(select(Phase).where(Phase.id == phase_id)).first()
                if not phase:
                    raise Exception(f"Invalid phase id supplied")
            task = Task(name=name,
                        name_lower=name.lower(),
                        status="Todo",
                        description=description or "",
                        project_id=project_id,
                        phase_id=phase_id
                        )
            session.add(task)
            session.commit()
            session.refresh(task)
        with Session(self.model_db.engine) as session:
            swtask = SWTask(task_id=task.id) # type: ignore
            session.add(swtask)
            session.commit()
            session.refresh(swtask)
            return SWTaskRecord(self.model_db, swtask)
        
    
