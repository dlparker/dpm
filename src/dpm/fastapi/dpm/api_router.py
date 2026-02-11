"""REST API router with CRUD operations for task management."""
from pathlib import Path
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from dpm.store.wrappers import ModelDB


# ============================================================================
# Pydantic models for request/response
# ============================================================================

class DomainResponse(BaseModel):
    name: str
    filepath: str
    description: Optional[str] = None


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    parent_id: Optional[int] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    parent_id: Optional[int] = None


class ProjectResponse(BaseModel):
    project_id: int
    name: str
    description: Optional[str]
    parent_id: Optional[int]
    save_time: Optional[datetime]

    class Config:
        from_attributes = True


class PhaseCreate(BaseModel):
    name: str
    description: Optional[str] = None
    project_id: int
    follows_id: Optional[int] = None


class PhaseUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    follows_id: Optional[int] = None


class PhaseResponse(BaseModel):
    phase_id: int
    name: str
    description: Optional[str]
    project_id: int
    follows_id: Optional[int]
    save_time: Optional[datetime]

    class Config:
        from_attributes = True


class TaskCreate(BaseModel):
    name: str
    description: Optional[str] = None
    status: str = "ToDo"
    project_id: Optional[int] = None
    phase_id: Optional[int] = None


class TaskUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    project_id: Optional[int] = None
    phase_id: Optional[int] = None


class TaskResponse(BaseModel):
    task_id: int
    name: str
    description: Optional[str]
    status: str
    project_id: Optional[int]
    phase_id: Optional[int]
    save_time: Optional[datetime]

    class Config:
        from_attributes = True


class BlockerCreate(BaseModel):
    blocked_task_id: int
    blocking_task_id: int


class BlockerResponse(BaseModel):
    task_id: int
    name: str
    status: str


class TAPFocusResponse(BaseModel):
    task_id: Optional[int] = None
    uuid: str

class PMDBAPIService:

    def __init__(self, server, dpm_manager, prefix_tag="pm_api"):
        self.server = server
        self.prefix_tag = prefix_tag
        self.dpm_manager = dpm_manager
        self._router = APIRouter(tags=[prefix_tag])

    def become_router(self) -> APIRouter:
        """Return a router with all routes bound to this instance."""
        self._router.add_api_route("/domains", self.list_domains, methods=["GET"], response_model=list[DomainResponse])
        self._router.add_api_route("/{domain}/projects", self.list_projects, methods=["GET"], response_model=list[ProjectResponse])
        self._router.add_api_route("/{domain}/projects/{project_id}", self.get_project, methods=["GET"], response_model=ProjectResponse)
        self._router.add_api_route("/{domain}/projects", self.create_project, methods=["POST"], response_model=ProjectResponse, status_code=201)
        self._router.add_api_route("/{domain}/projects/{project_id}", self.update_project, methods=["PUT"], response_model=ProjectResponse)
        self._router.add_api_route("/{domain}/projects/{project_id}", self.delete_project, methods=["DELETE"], status_code=204)
        self._router.add_api_route("/{domain}/projects/{project_id}/phases", self.list_project_phases, methods=["GET"], response_model=list[PhaseResponse])
        self._router.add_api_route("/{domain}/projects/{project_id}/tasks", self.list_project_tasks, methods=["GET"], response_model=list[TaskResponse])
        self._router.add_api_route("/{domain}/phases", self.list_phases, methods=["GET"], response_model=list[PhaseResponse])
        self._router.add_api_route("/{domain}/phases/{phase_id}", self.get_phase, methods=["GET"], response_model=PhaseResponse)
        self._router.add_api_route("/{domain}/phases", self.create_phase, methods=["POST"], response_model=PhaseResponse, status_code=201)
        self._router.add_api_route("/{domain}/phases/{phase_id}", self.update_phase, methods=["PUT"], response_model=PhaseResponse)
        self._router.add_api_route("/{domain}/phases/{phase_id}", self.delete_phase, methods=["DELETE"], status_code=204)
        self._router.add_api_route("/{domain}/phases/{phase_id}/tasks", self.list_phase_tasks, methods=["GET"], response_model=list[TaskResponse])
        self._router.add_api_route("/{domain}/tasks", self.list_tasks, methods=["GET"], response_model=list[TaskResponse])
        self._router.add_api_route("/{domain}/tasks/{task_id}", self.get_task, methods=["GET"], response_model=TaskResponse)
        self._router.add_api_route("/{domain}/tasks", self.create_task, methods=["POST"], response_model=TaskResponse, status_code=201)
        self._router.add_api_route("/{domain}/tasks/{task_id}", self.update_task, methods=["PUT"], response_model=TaskResponse)
        self._router.add_api_route("/{domain}/tasks/{task_id}", self.delete_task, methods=["DELETE"], status_code=204)
        self._router.add_api_route("/{domain}/tasks/{task_id}/blockers", self.list_task_blockers, methods=["GET"], response_model=list[BlockerResponse])
        self._router.add_api_route("/{domain}/tasks/{task_id}/blockers", self.add_blocker, methods=["POST"], status_code=201)
        self._router.add_api_route("/{domain}/tasks/{task_id}/blockers/{blocker_id}", self.remove_blocker, methods=["DELETE"], status_code=204)
        self._router.add_api_route("/{domain}/tasks/{task_id}/blocks", self.list_tasks_blocked_by, methods=["GET"], response_model=list[BlockerResponse])
        return self._router

    def _get_db(self, domain: str) -> ModelDB:
        if domain == "default":
            domain = self.dpm_manager.get_default_domain()
        return self.dpm_manager.get_db_for_domain(domain)

                               
    # ========================================================================
    # Project endpoints
    # ========================================================================

    async def list_domains(self):
        return [DomainResponse(name=name,
                               filepath=str(item.db_path), description=item.description)
                for name, item in self.dpm_manager.get_domains().items()]

    async def list_projects(self, domain: str, parent_id: Optional[int] = None):
        db = self._get_db(domain)
        if parent_id is not None:
            projects = db.get_projects_by_parent_id(parent_id)
        else:
            projects = db.get_projects()
        return [ProjectResponse(
            project_id=p.project_id, # type: ignore
            name=p.name,
            description=p.description,
            parent_id=p.parent_id,
            save_time=p.save_time
        ) for p in projects]

    async def get_project(self, domain: str, project_id: int):
        """Get a project by ID."""
        db = self._get_db(domain)
        project = db.get_project_by_id(project_id)
        if project:
            return ProjectResponse(
                project_id=project.project_id, # type: ignore
                name=project.name,
                description=project.description,
                parent_id=project.parent_id,
                save_time=project.save_time
            )
        raise HTTPException(status_code=404, detail="Project not found")

    async def create_project(self, domain: str, data: ProjectCreate):
        """Create a new project."""
        db = self._get_db(domain)
        try:
            project = db.add_project(
                name=data.name,
                description=data.description,
                parent_id=data.parent_id
            )
            return ProjectResponse(
                project_id=project.project_id,# type: ignore
                name=project.name,
                description=project.description,
                parent_id=project.parent_id,
                save_time=project.save_time
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    async def update_project(self, domain: str, project_id: int, data: ProjectUpdate):
        """Update a project."""
        db = self._get_db(domain)
        project = db.get_project_by_id(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        if data.name is not None:
            project.name = data.name
        if data.description is not None:
            project.description = data.description
        if data.parent_id is not None:
            project.parent_id = data.parent_id

        try:
            project.save()
            return ProjectResponse(
                project_id=project.project_id,# type: ignore
                name=project.name,
                description=project.description,
                parent_id=project.parent_id,
                save_time=project.save_time
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    async def delete_project(self, domain: str, project_id: int):
        """Delete a project."""
        db = self._get_db(domain)
        project = db.get_project_by_id(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        project.delete_from_db()

    async def list_project_phases(self, domain: str, project_id: int):
        """List phases for a project in order."""
        db = self._get_db(domain)
        project = db.get_project_by_id(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        phases = project.get_phases()
        return [PhaseResponse(
            phase_id=p.phase_id,
            name=p.name,
            description=p.description,
            project_id=p.project_id,
            follows_id=p.follows_id,
            save_time=p.save_time
        ) for p in phases]

    async def list_project_tasks(self, domain: str, project_id: int):
        """List tasks for a project."""
        db = self._get_db(domain)
        project = db.get_project_by_id(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        tasks = project.get_tasks()
        return [TaskResponse(
            task_id=t.task_id,# type: ignore
            name=t.name,
            description=t.description,
            status=t.status,
            project_id=t.project_id,
            phase_id=t.phase_id,
            save_time=t.save_time
        ) for t in tasks]

    # ========================================================================
    # Phase endpoints
    # ========================================================================

    async def list_phases(self, domain: str, project_id: Optional[int] = None):
        """List phases, optionally filtered by project."""
        db = self._get_db(domain)
        if project_id is not None:
            phases = db.get_phases_by_project_id(project_id)
        else:
            # Get all phases from all projects
            phases = []
            for project in db.get_projects():
                phases.extend(project.get_phases())
        return [PhaseResponse(
            phase_id=p.phase_id,
            name=p.name,
            description=p.description,
            project_id=p.project_id,
            follows_id=p.follows_id,
            save_time=p.save_time
        ) for p in phases]

    async def get_phase(self, domain: str, phase_id: int):
        """Get a phase by ID."""
        db = self._get_db(domain)
        phase = db.get_phase_by_id(phase_id)
        if not phase:
            raise HTTPException(status_code=404, detail="Phase not found")
        return PhaseResponse(
            phase_id=phase.phase_id, # type: ignore
            name=phase.name,
            description=phase.description,
            project_id=phase.project_id,
            follows_id=phase.follows_id,
            save_time=phase.save_time
        )

    async def create_phase(self, domain: str, data: PhaseCreate):
        """Create a new phase."""
        db = self._get_db(domain)
        try:
            phase = db.add_phase(
                name=data.name,
                description=data.description,
                project_id=data.project_id,
                follows_id=data.follows_id
            )
            return PhaseResponse(
                phase_id=phase.phase_id, # type: ignore
                name=phase.name,
                description=phase.description,
                project_id=phase.project_id,
                follows_id=phase.follows_id,
                save_time=phase.save_time
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    async def update_phase(self, domain: str, phase_id: int, data: PhaseUpdate):
        """Update a phase."""
        db = self._get_db(domain)
        phase = db.get_phase_by_id(phase_id)
        if not phase:
            raise HTTPException(status_code=404, detail="Phase not found")

        if data.name is not None:
            phase.name = data.name
        if data.description is not None:
            phase.description = data.description
        if data.follows_id is not None:
            phase.follows_id = data.follows_id

        try:
            phase.save()
            # Refresh to get updated follows_id
            phase = db.get_phase_by_id(phase_id)
            return PhaseResponse(
                phase_id=phase.phase_id, # type: ignore
                name=phase.name, # type: ignore
                description=phase.description, # type: ignore
                project_id=phase.project_id, # type: ignore
                follows_id=phase.follows_id, # type: ignore
                save_time=phase.save_time # type: ignore
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    async def delete_phase(self, domain: str, phase_id: int):
        """Delete a phase."""
        db = self._get_db(domain)
        phase = db.get_phase_by_id(phase_id)
        if not phase:
            raise HTTPException(status_code=404, detail="Phase not found")
        phase.delete_from_db()

    async def list_phase_tasks(self, domain: str, phase_id: int):
        """List tasks for a phase."""
        db = self._get_db(domain)
        phase = db.get_phase_by_id(phase_id)
        if not phase:
            raise HTTPException(status_code=404, detail="Phase not found")
        tasks = phase.get_tasks()
        return [TaskResponse(
            task_id=t.task_id, # type: ignore
            name=t.name,
            description=t.description,
            status=t.status,
            project_id=t.project_id,
            phase_id=t.phase_id,
            save_time=t.save_time
        ) for t in tasks]

    # ========================================================================
    # Task endpoints
    # ========================================================================

    async def list_tasks(
        self,
        domain: str,
        status: Optional[str] = None,
        project_id: Optional[int] = None,
        phase_id: Optional[int] = None
    ):
        """List tasks with optional filters."""
        db = self._get_db(domain)
        if status is not None:
            tasks = db.get_tasks_by_status(status)
        elif project_id is not None:
            tasks = db.get_tasks_by_project_id(project_id)
        elif phase_id is not None:
            tasks = db.get_tasks_by_phase_id(phase_id)
        else:
            tasks = db.get_tasks()
        return [TaskResponse(
            task_id=t.task_id, # type: ignore
            name=t.name,
            description=t.description,
            status=t.status,
            project_id=t.project_id,
            phase_id=t.phase_id,
            save_time=t.save_time
        ) for t in tasks]

    async def get_task(self, domain: str, task_id: int):
        """Get a task by ID."""
        db = self._get_db(domain)
        task = db.get_task_by_id(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return TaskResponse(
            task_id=task.task_id, # type: ignore
            name=task.name,
            description=task.description,
            status=task.status,
            project_id=task.project_id,
            phase_id=task.phase_id,
            save_time=task.save_time
        )

    async def create_task(self, domain: str, data: TaskCreate):
        """Create a new task."""
        db = self._get_db(domain)
        try:
            task = db.add_task(
                name=data.name,
                description=data.description,
                status=data.status,
                project_id=data.project_id,
                phase_id=data.phase_id
            )
            return TaskResponse(
                task_id=task.task_id, # type: ignore
                name=task.name,
                description=task.description,
                status=task.status,
                project_id=task.project_id,
                phase_id=task.phase_id,
                save_time=task.save_time
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    async def update_task(self, domain: str, task_id: int, data: TaskUpdate):
        """Update a task."""
        db = self._get_db(domain)
        task = db.get_task_by_id(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        if data.name is not None:
            task.name = data.name
        if data.description is not None:
            task.description = data.description
        if data.status is not None:
            task.status = data.status
        if data.project_id is not None:
            task.project_id = data.project_id
        if data.phase_id is not None:
            task.phase_id = data.phase_id

        try:
            task.save()
            return TaskResponse(
                task_id=task.task_id, # type: ignore
                name=task.name,
                description=task.description,
                status=task.status,
                project_id=task.project_id,
                phase_id=task.phase_id,
                save_time=task.save_time
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    async def delete_task(self, domain: str, task_id: int):
        """Delete a task."""
        db = self._get_db(domain)
        task = db.get_task_by_id(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        task.delete_from_db()

    # ========================================================================
    # Blocker endpoints
    # ========================================================================

    async def list_task_blockers(self, domain: str, task_id: int, include_done: bool = False):
        """List tasks that block this task."""
        db = self._get_db(domain)
        task = db.get_task_by_id(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        blockers = task.get_blockers(only_not_done=not include_done)
        return [BlockerResponse(
            task_id=b.task_id,
            name=b.name,
            status=b.status
        ) for b in blockers]

    async def add_blocker(self, domain: str, task_id: int, data: BlockerCreate):
        """Add a blocker to a task."""
        db = self._get_db(domain)
        if task_id != data.blocked_task_id:
            raise HTTPException(
                status_code=400,
                detail="URL task_id must match blocked_task_id"
            )

        blocked_task = db.get_task_by_id(data.blocked_task_id)
        if not blocked_task:
            raise HTTPException(status_code=404, detail="Blocked task not found")

        blocking_task = db.get_task_by_id(data.blocking_task_id)
        if not blocking_task:
            raise HTTPException(status_code=404, detail="Blocking task not found")

        try:
            blocked_task.add_blocker(blocking_task)
            return {"message": "Blocker added"}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    async def remove_blocker(self, domain: str, task_id: int, blocker_id: int):
        """Remove a blocker from a task."""
        db = self._get_db(domain)
        task = db.get_task_by_id(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        blocker_task = db.get_task_by_id(blocker_id)
        if not blocker_task:
            raise HTTPException(status_code=404, detail="Blocker task not found")

        task.delete_blocker(blocker_task)

    async def list_tasks_blocked_by(self, domain: str, task_id: int):
        """List tasks that are blocked by this task."""
        db = self._get_db(domain)
        task = db.get_task_by_id(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        blocked = task.blocks_tasks()
        return [BlockerResponse(
            task_id=b.task_id,
            name=b.name,
            status=b.status
        ) for b in blocked]
