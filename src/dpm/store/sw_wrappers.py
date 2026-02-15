from typing import Optional
from sqlmodel import Session, select
from dpm.store.sw_models import GuardrailType, Vision, Subsystem, Deliverable, Epic, Story, SWTask
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
    def guardrail_type(self) -> GuardrailType:
        return self._epic.guardrail_type

    @guardrail_type.setter
    def guardrail_type(self, value: GuardrailType):
        self._epic.guardrail_type = value

    @property
    def project(self) -> ProjectRecord:
        return self.model_db.get_project_by_id(self.project_id)

    @property
    def project_model(self) -> Project:
        return self.model_db.get_project_by_id(self.project_id)._project

    def save(self):
        super().save()
        with Session(self.model_db.engine) as session:
            epic = session.exec(select(Epic).where(Epic.id == self._epic.id)).first()
            if epic:
                epic.guardrail_type = self._epic.guardrail_type
                session.add(epic)
                session.commit()
                session.refresh(epic)
                self._epic = epic


class StoryRecord(PhaseRecord):

    def __init__(self, model_db: ModelDB, story: Story):
        super().__init__(model_db=model_db, phase=story.phase)
        self._story = story

    @property
    def story_id(self):
        return self._story.id

    @property
    def guardrail_type(self) -> GuardrailType:
        return self._story.guardrail_type

    @guardrail_type.setter
    def guardrail_type(self, value: GuardrailType):
        self._story.guardrail_type = value

    def save(self):
        result = super().save()
        with Session(self.model_db.engine) as session:
            story = session.exec(select(Story).where(Story.id == self._story.id)).first()
            if story:
                story.guardrail_type = self._story.guardrail_type
                session.add(story)
                session.commit()
                session.refresh(story)
                self._story = story
        return result

class SWTaskRecord(TaskRecord):

    def __init__(self, model_db: ModelDB, swtask: SWTask):
        super().__init__(model_db=model_db, task=swtask.task)
        self._swtask = swtask

    @property
    def swtask_id(self):
        return self._swtask.id

    @property
    def guardrail_type(self) -> GuardrailType:
        return self._swtask.guardrail_type

    @guardrail_type.setter
    def guardrail_type(self, value: GuardrailType):
        self._swtask.guardrail_type = value

    def save(self):
        result = super().save()
        with Session(self.model_db.engine) as session:
            swtask = session.exec(select(SWTask).where(SWTask.id == self._swtask.id)).first()
            if swtask:
                swtask.guardrail_type = self._swtask.guardrail_type
                session.add(swtask)
                session.commit()
                session.refresh(swtask)
                self._swtask = swtask
        return result


class SWModelDB:

    def __init__(self, model_db: ModelDB):
        self.model_db = model_db

    # --- Delete cascade helpers (idempotent) ---

    def delete_sw_overlay_for_project(self, project_id: int):
        with Session(self.model_db.engine) as session:
            for model_cls in (Vision, Subsystem, Deliverable, Epic):
                row = session.exec(select(model_cls).where(model_cls.project_id == project_id)).first()
                if row:
                    session.delete(row)
            session.commit()

    def delete_sw_overlay_for_phase(self, phase_id: int):
        with Session(self.model_db.engine) as session:
            row = session.exec(select(Story).where(Story.phase_id == phase_id)).first()
            if row:
                session.delete(row)
                session.commit()

    def delete_sw_overlay_for_task(self, task_id: int):
        with Session(self.model_db.engine) as session:
            row = session.exec(select(SWTask).where(SWTask.task_id == task_id)).first()
            if row:
                session.delete(row)
                session.commit()

    # --- Lookup by SW ID ---

    def get_vision_by_id(self, vision_id: int) -> Optional[VisionRecord]:
        with Session(self.model_db.engine) as session:
            vision = session.exec(select(Vision).where(Vision.id == vision_id)).first()
            if vision:
                return VisionRecord(self.model_db, vision)
            return None

    def get_subsystem_by_id(self, subsystem_id: int) -> Optional[SubsystemRecord]:
        with Session(self.model_db.engine) as session:
            subsystem = session.exec(select(Subsystem).where(Subsystem.id == subsystem_id)).first()
            if subsystem:
                return SubsystemRecord(self.model_db, subsystem)
            return None

    def get_deliverable_by_id(self, deliverable_id: int) -> Optional[DeliverableRecord]:
        with Session(self.model_db.engine) as session:
            deliverable = session.exec(select(Deliverable).where(Deliverable.id == deliverable_id)).first()
            if deliverable:
                return DeliverableRecord(self.model_db, deliverable)
            return None

    def get_epic_by_id(self, epic_id: int) -> Optional[EpicRecord]:
        with Session(self.model_db.engine) as session:
            epic = session.exec(select(Epic).where(Epic.id == epic_id)).first()
            if epic:
                return EpicRecord(self.model_db, epic)
            return None

    def get_story_by_id(self, story_id: int) -> Optional[StoryRecord]:
        with Session(self.model_db.engine) as session:
            story = session.exec(select(Story).where(Story.id == story_id)).first()
            if story:
                return StoryRecord(self.model_db, story)
            return None

    def get_swtask_by_id(self, swtask_id: int) -> Optional[SWTaskRecord]:
        with Session(self.model_db.engine) as session:
            swtask = session.exec(select(SWTask).where(SWTask.id == swtask_id)).first()
            if swtask:
                return SWTaskRecord(self.model_db, swtask)
            return None

    # --- Lookup from base model ID ---

    def get_vision_for_project(self, project_id: int) -> Optional[VisionRecord]:
        with Session(self.model_db.engine) as session:
            vision = session.exec(select(Vision).where(Vision.project_id == project_id)).first()
            if vision:
                return VisionRecord(self.model_db, vision)
            return None

    def get_subsystem_for_project(self, project_id: int) -> Optional[SubsystemRecord]:
        with Session(self.model_db.engine) as session:
            subsystem = session.exec(select(Subsystem).where(Subsystem.project_id == project_id)).first()
            if subsystem:
                return SubsystemRecord(self.model_db, subsystem)
            return None

    def get_deliverable_for_project(self, project_id: int) -> Optional[DeliverableRecord]:
        with Session(self.model_db.engine) as session:
            deliverable = session.exec(select(Deliverable).where(Deliverable.project_id == project_id)).first()
            if deliverable:
                return DeliverableRecord(self.model_db, deliverable)
            return None

    def get_epic_for_project(self, project_id: int) -> Optional[EpicRecord]:
        with Session(self.model_db.engine) as session:
            epic = session.exec(select(Epic).where(Epic.project_id == project_id)).first()
            if epic:
                return EpicRecord(self.model_db, epic)
            return None

    def get_story_for_phase(self, phase_id: int) -> Optional[StoryRecord]:
        with Session(self.model_db.engine) as session:
            story = session.exec(select(Story).where(Story.phase_id == phase_id)).first()
            if story:
                return StoryRecord(self.model_db, story)
            return None

    def get_swtask_for_task(self, task_id: int) -> Optional[SWTaskRecord]:
        with Session(self.model_db.engine) as session:
            swtask = session.exec(select(SWTask).where(SWTask.task_id == task_id)).first()
            if swtask:
                return SWTaskRecord(self.model_db, swtask)
            return None

    # --- List queries ---

    def get_visions(self) -> list[VisionRecord]:
        with Session(self.model_db.engine) as session:
            visions = session.exec(select(Vision).order_by(Vision.id)).all()
            return [VisionRecord(self.model_db, v) for v in visions]

    def get_subsystems(self, vision: Optional[VisionRecord] = None) -> list[SubsystemRecord]:
        with Session(self.model_db.engine) as session:
            if vision:
                # Subsystems whose Project.parent_id == vision.project_id
                stmt = select(Subsystem).join(Project, Subsystem.project_id == Project.id).where(
                    Project.parent_id == vision.project_id
                ).order_by(Subsystem.id)
            else:
                stmt = select(Subsystem).order_by(Subsystem.id)
            subsystems = session.exec(stmt).all()
            return [SubsystemRecord(self.model_db, s) for s in subsystems]

    def get_deliverables(self, parent: Optional[ProjectRecord] = None) -> list[DeliverableRecord]:
        with Session(self.model_db.engine) as session:
            if parent:
                stmt = select(Deliverable).join(Project, Deliverable.project_id == Project.id).where(
                    Project.parent_id == parent.project_id
                ).order_by(Deliverable.id)
            else:
                stmt = select(Deliverable).order_by(Deliverable.id)
            deliverables = session.exec(stmt).all()
            return [DeliverableRecord(self.model_db, d) for d in deliverables]

    def get_epics(self, parent: Optional[ProjectRecord] = None) -> list[EpicRecord]:
        with Session(self.model_db.engine) as session:
            if parent:
                stmt = select(Epic).join(Project, Epic.project_id == Project.id).where(
                    Project.parent_id == parent.project_id
                ).order_by(Epic.id)
            else:
                stmt = select(Epic).order_by(Epic.id)
            epics = session.exec(stmt).all()
            return [EpicRecord(self.model_db, e) for e in epics]

    def get_stories(self, epic: Optional[EpicRecord] = None) -> list[StoryRecord]:
        with Session(self.model_db.engine) as session:
            if epic:
                # Stories whose Phase.project_id == epic.project_id
                stmt = select(Story).join(Phase, Story.phase_id == Phase.id).where(
                    Phase.project_id == epic.project_id
                ).order_by(Story.id)
            else:
                stmt = select(Story).order_by(Story.id)
            stories = session.exec(stmt).all()
            return [StoryRecord(self.model_db, s) for s in stories]

    def get_swtasks(self, story: Optional[StoryRecord] = None,
                    epic: Optional[EpicRecord] = None) -> list[SWTaskRecord]:
        with Session(self.model_db.engine) as session:
            if story:
                stmt = select(SWTask).join(Task, SWTask.task_id == Task.id).where(
                    Task.phase_id == story.phase_id
                ).order_by(SWTask.id)
            elif epic:
                stmt = select(SWTask).join(Task, SWTask.task_id == Task.id).where(
                    Task.project_id == epic.project_id
                ).order_by(SWTask.id)
            else:
                stmt = select(SWTask).order_by(SWTask.id)
            swtasks = session.exec(stmt).all()
            return [SWTaskRecord(self.model_db, t) for t in swtasks]

    # --- Type detection ---

    def get_sw_type(self, project_id: int) -> Optional[str]:
        with Session(self.model_db.engine) as session:
            if session.exec(select(Vision).where(Vision.project_id == project_id)).first():
                return "Vision"
            if session.exec(select(Subsystem).where(Subsystem.project_id == project_id)).first():
                return "Subsystem"
            if session.exec(select(Deliverable).where(Deliverable.project_id == project_id)).first():
                return "Deliverable"
            if session.exec(select(Epic).where(Epic.project_id == project_id)).first():
                return "Epic"
            return None

    def get_sw_phase_type(self, phase_id: int) -> Optional[str]:
        with Session(self.model_db.engine) as session:
            if session.exec(select(Story).where(Story.phase_id == phase_id)).first():
                return "Story"
            return None

    def get_sw_task_type(self, task_id: int) -> Optional[str]:
        with Session(self.model_db.engine) as session:
            if session.exec(select(SWTask).where(SWTask.task_id == task_id)).first():
                return "SWTask"
            return None

    # --- Wrap utility ---

    def wrap_project(self, project_record: ProjectRecord):
        pid = project_record.project_id
        with Session(self.model_db.engine) as session:
            vision = session.exec(select(Vision).where(Vision.project_id == pid)).first()
            if vision:
                return VisionRecord(self.model_db, vision)
            subsystem = session.exec(select(Subsystem).where(Subsystem.project_id == pid)).first()
            if subsystem:
                return SubsystemRecord(self.model_db, subsystem)
            deliverable = session.exec(select(Deliverable).where(Deliverable.project_id == pid)).first()
            if deliverable:
                return DeliverableRecord(self.model_db, deliverable)
            epic = session.exec(select(Epic).where(Epic.project_id == pid)).first()
            if epic:
                return EpicRecord(self.model_db, epic)
        return project_record

    # --- Factory methods ---

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
            subsystem = Subsystem(project_id=project.id) # type: ignore
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
            deliverable = Deliverable(project_id=project.id) # type: ignore
            session.add(deliverable)
            session.commit()
            session.refresh(deliverable)
            return DeliverableRecord(self.model_db, deliverable)

    def add_epic(self, domain: PMDBDomain, name: str,
                 description: Optional[str] = None,
                 vision: Optional[VisionRecord] = None,
                 subsystem: Optional[SubsystemRecord] = None,
                 deliverable: Optional[DeliverableRecord] = None,
                 guardrail_type: Optional[GuardrailType] = None) -> EpicRecord:

        parent_id = None
        if deliverable:
            parent_id = deliverable.project_id
        elif subsystem:
            parent_id = subsystem.project_id
        elif vision:
            parent_id = vision.project_id
        project = self.add_proj_base(domain, name, description, parent_id)
        gt = guardrail_type or GuardrailType.PRODUCTION
        with Session(self.model_db.engine) as session:
            epic = Epic(project_id=project.id, guardrail_type=gt) # type: ignore
            session.add(epic)
            session.commit()
            session.refresh(epic)
            return EpicRecord(self.model_db, epic)

    def add_story(self, domain: PMDBDomain, name: str,
                  description: Optional[str] = None,
                  vision: Optional[VisionRecord] = None,
                  subsystem: Optional[SubsystemRecord] = None,
                  deliverable: Optional[DeliverableRecord] = None,
                  epic: Optional[EpicRecord] = None,
                  guardrail_type: Optional[GuardrailType] = None) -> StoryRecord:

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

        # Inherit guardrail_type from epic if not provided
        if guardrail_type is None and epic:
            gt = epic.guardrail_type
        elif guardrail_type is not None:
            gt = guardrail_type
        else:
            gt = GuardrailType.PRODUCTION

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
            story = Story(phase_id=phase.id, guardrail_type=gt) # type: ignore
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
                 epic: Optional[EpicRecord] = None,
                 story: Optional[StoryRecord] = None,
                 guardrail_type: Optional[GuardrailType] = None,
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

        # Inherit guardrail_type: story > epic > PRODUCTION
        if guardrail_type is not None:
            gt = guardrail_type
        elif story:
            gt = story.guardrail_type
        elif epic:
            gt = epic.guardrail_type
        else:
            gt = GuardrailType.PRODUCTION

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
            swtask = SWTask(task_id=task.id, guardrail_type=gt) # type: ignore
            session.add(swtask)
            session.commit()
            session.refresh(swtask)
            return SWTaskRecord(self.model_db, swtask)
