from __future__ import annotations

import logging
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from dpm.fastapi.ops import ServerOps
from dpm.store.wrappers import ModelDB
from dpm.store.domains import DomainMode, DPMManager, PMDBDomain
from dpm.store.sw_wrappers import (
    VisionRecord, SubsystemRecord, DeliverableRecord, EpicRecord,
)

logger = logging.getLogger("UIRouter")


class PMDBUIRouter:
    """Router for HTML UI pages using HTMX, Tailwind CSS, and daisyUI."""

    def __init__(self, server: ServerOps, dpm_manager: DPMManager) -> None:
        self.server = server
        self.dpm_manager = dpm_manager
        self.templates = server.templates

    def _get_db(self, domain: str) -> ModelDB:
        return self.dpm_manager.get_db_for_domain(domain)

    def _get_domain_info(self, domain: str) -> PMDBDomain:
        return self.dpm_manager.get_domains()[domain]

    def _is_sw_domain(self, domain: str) -> bool:
        return self._get_domain_info(domain).domain_mode == DomainMode.SOFTWARE

    def become_router(self) -> APIRouter:
        router = APIRouter()

        # ====================================================================
        # Tree View Routes — PM section
        # ====================================================================

        @router.get("/domains", response_class=HTMLResponse, name="pm:domains")
        async def pm_domains(request: Request) -> Response:

            domains = [
                {"name": name, "description": item.description,
                 "domain_mode": item.domain_mode.value if item.domain_mode else "default"}
                for name, item in self.dpm_manager.get_domains().items()
            ]
            context = {"request": request, "domains": domains}
            is_htmx = request.headers.get("HX-Request") == "true"
            if is_htmx:
                return self.templates.TemplateResponse(
                    "pm_domains_tree.html",
                    context,
                    block_name="sb_main_content"
                )
            else:
                return self.templates.TemplateResponse(
                    "pm_domains_tree.html",
                    context
                )

        @router.get("/nav_tree", response_class=HTMLResponse, name="pm:nav_tree")
        async def pm_nav_tree(request: Request) -> Response:
            domains = [
                {"name": name, "description": item.description,
                 "domain_mode": item.domain_mode.value if item.domain_mode else "default"}
                for name, item in self.dpm_manager.get_domains().items()
            ]
            context = {"request": request, "domains": domains}
            is_htmx = request.headers.get("HX-Request") == "true"
            if is_htmx:
                return self.templates.TemplateResponse(
                    "pm_nav_tree.html",
                    context,
                    block_name="sb_main_content"
                )
            else:
                return self.templates.TemplateResponse(
                    "pm_nav_tree.html",
                    context
                )

        # ====================================================================
        # Nav Tree Routes — Compact versions for sidebar navigation
        # ====================================================================

        @router.get("/nav/{domain}/projects", response_class=HTMLResponse, name="pm:nav-domain-projects")
        async def pm_nav_projects(request: Request, domain: str) -> Response:
            self.dpm_manager.set_last_domain(domain)
            db = self._get_db(domain)
            projects = db.get_projects()
            context = {
                "request": request,
                "domain": domain,
                "projects": projects,
            }
            return self.templates.TemplateResponse(
                "pm_nav_projects.html",
                context,
                block_name="sb_main_content"
            )

        @router.get("/nav/{domain}/project/{project_id}/children", response_class=HTMLResponse, name="pm:nav-project-children")
        async def pm_nav_project_children(request: Request, domain: str, project_id: int) -> Response:
            db = self._get_db(domain)
            project = db.get_project_by_id(project_id)
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            self.dpm_manager.set_last_project(domain, project)

            phases = project.get_phases()
            all_tasks = project.get_tasks()
            direct_tasks = [t for t in all_tasks if t.phase_id is None]

            context = {
                "request": request,
                "domain": domain,
                "project": project,
                "phases": phases,
                "tasks": direct_tasks
            }
            return self.templates.TemplateResponse(
                "pm_nav_project_children.html",
                context,
                block_name="sb_main_content"
            )

        @router.get("/nav/{domain}/phase/{phase_id}/tasks", response_class=HTMLResponse, name="pm:nav-phase-tasks")
        async def pm_nav_phase_tasks(request: Request, domain: str, phase_id: int) -> Response:
            db = self._get_db(domain)
            phase = db.get_phase_by_id(phase_id)
            if not phase:
                raise HTTPException(status_code=404, detail="Phase not found")
            self.dpm_manager.set_last_phase(domain, phase)

            tasks = phase.get_tasks()
            context = {
                "request": request,
                "domain": domain,
                "phase": phase,
                "tasks": tasks
            }
            return self.templates.TemplateResponse(
                "pm_nav_tasks.html",
                context,
                block_name="sb_main_content"
            )

        # ====================================================================
        # Main Content Routes — Full detail views
        # ====================================================================

        @router.get("/{domain}/projects", response_class=HTMLResponse, name="pm:domain-projects")
        async def pm_projects(request: Request, domain: str) -> Response:
            self.dpm_manager.set_last_domain(domain)
            db = self._get_db(domain)
            projects = db.get_projects()
            is_htmx = request.headers.get("HX-Request") == "true"
            context = {
                "request": request,
                "domain": domain,
                "projects": projects,
            }
            if is_htmx:
                # HTMX → render only the main content block
                return self.templates.TemplateResponse(
                    "pm_projects.html",
                    context,
                    block_name="sb_main_content"
                )
            else:
                return self.templates.TemplateResponse(
                    "pm_projects.html",
                    context
                )

        @router.get("/{domain}/project/{project_id}/children", response_class=HTMLResponse, name="pm:project-children")
        async def pm_project_children(request: Request, domain: str, project_id: int) -> Response:
            db = self._get_db(domain)
            project = db.get_project_by_id(project_id)
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            self.dpm_manager.set_last_project(domain, project)

            phases = project.get_phases()
            all_tasks = project.get_tasks()
            direct_tasks = [t for t in all_tasks if t.phase_id is None]

            context = {
                "request": request,
                "domain": domain,
                "project": project,
                "phases": phases,
                "tasks": direct_tasks
            }

            is_htmx = request.headers.get("HX-Request") == "true"
            if is_htmx:
                return self.templates.TemplateResponse(
                    "pm_project_children.html",
                    context,
                    block_name="sb_main_content"
                )
            else:
                return self.templates.TemplateResponse(
                    "pm_project_children.html",
                    context
                )

        @router.get("/{domain}/phase/{phase_id}/tasks", response_class=HTMLResponse, name="pm:phase-tasks")
        async def pm_phase_tasks(request: Request, domain: str, phase_id: int) -> Response:
            db = self._get_db(domain)
            phase = db.get_phase_by_id(phase_id)
            if not phase:
                raise HTTPException(status_code=404, detail="Phase not found")
            self.dpm_manager.set_last_phase(domain, phase)

            tasks = phase.get_tasks()
            context =  {
                "request": request,
                "domain": domain,
                "phase": phase,
                "tasks": tasks
            }
            is_htmx = request.headers.get("HX-Request") == "true"
            if is_htmx:
                return self.templates.TemplateResponse(
                    "pm_tasks.html",
                    context,
                    block_name="sb_main_content"
                )
            else:
                return self.templates.TemplateResponse(
                    "pm_tasks.html",
                    context,
                )

        # ====================================================================
        # Detail View Routes — Individual item views
        # ====================================================================

        @router.get("/{domain}/project/{project_id}", response_class=HTMLResponse, name="pm:project")
        async def pm_project_detail(request: Request, domain: str, project_id: int) -> Response:
            db = self._get_db(domain)
            project = db.get_project_by_id(project_id)
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")

            # Redirect to SW detail page if this project has an SW overlay
            if self._is_sw_domain(domain):
                sw = db.sw_model_db
                wrapped = sw.wrap_project(project)
                if isinstance(wrapped, VisionRecord):
                    return RedirectResponse(
                        url=request.url_for("sw:vision", domain=domain, vision_id=wrapped.vision_id),
                        status_code=307)
                if isinstance(wrapped, SubsystemRecord):
                    return RedirectResponse(
                        url=request.url_for("sw:subsystem", domain=domain, subsystem_id=wrapped.subsystem_id),
                        status_code=307)
                if isinstance(wrapped, DeliverableRecord):
                    return RedirectResponse(
                        url=request.url_for("sw:deliverable", domain=domain, deliverable_id=wrapped.deliverable_id),
                        status_code=307)
                if isinstance(wrapped, EpicRecord):
                    return RedirectResponse(
                        url=request.url_for("sw:epic", domain=domain, epic_id=wrapped.epic_id),
                        status_code=307)

            self.dpm_manager.set_last_project(domain, project)

            context =  {
                "request": request,
                "domain": domain,
                "project": project,
            }
            is_htmx = request.headers.get("HX-Request") == "true"
            if is_htmx:
                return self.templates.TemplateResponse(
                    "pm_project.html",
                    context,
                    block_name="sb_main_content"
                )
            else:
                return self.templates.TemplateResponse(
                    "pm_project.html",
                    context,
                )

        @router.get("/last/project/", response_class=HTMLResponse, name="pm:last_project")
        async def pm_last_project(request: Request) -> Response:
            domain = self.dpm_manager.get_last_domain()
            project = self.dpm_manager.get_last_project()
            if domain is None or project is None:
                return RedirectResponse(url=request.url_for("pm:domains"))
            db = self._get_db(domain)
            # get fresh copy
            project = db.get_project_by_id(project.project_id) # type: ignore
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            context =  {
                "request": request,
                "domain": domain,
                "project": project,
            }
            is_htmx = request.headers.get("HX-Request") == "true"
            if is_htmx:
                return self.templates.TemplateResponse(
                    "pm_project.html",
                    context,
                    block_name="sb_main_content"
                )
            else:
                return self.templates.TemplateResponse(
                    "pm_project.html",
                    context,
                )

        @router.get("/last/phase/", response_class=HTMLResponse, name="pm:last_phase")
        async def pm_last_phase(request: Request) -> Response:
            domain = self.dpm_manager.get_last_domain()
            phase = self.dpm_manager.get_last_phase()
            if domain is None or phase is None:
                return RedirectResponse(url=request.url_for("pm:domains"))
            db = self._get_db(domain)
            # get fresh copy
            phase = db.get_phase_by_id(phase.phase_id) # type: ignore
            if not phase:
                raise HTTPException(status_code=404, detail="Phase not found")
            context =  {
                "request": request,
                "domain": domain,
                "phase": phase,
            }
            is_htmx = request.headers.get("HX-Request") == "true"
            if is_htmx:
                return self.templates.TemplateResponse(
                    "pm_phase.html",
                    context,
                    block_name="sb_main_content"
                )
            else:
                return self.templates.TemplateResponse(
                    "pm_phase.html",
                    context,
                )

        @router.get("/last/task/", response_class=HTMLResponse, name="pm:last_task")
        async def pm_last_task(request: Request) -> Response:
            domain = self.dpm_manager.get_last_domain()
            task = self.dpm_manager.get_last_task()
            if domain is None or task is None:
                return RedirectResponse(url=request.url_for("pm:domains"))
            db = self._get_db(domain)
            # get fresh copy
            task = db.get_task_by_id(task.task_id) # type: ignore
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")
            blockers = task.get_blockers(only_not_done=False)
            blocks = task.blocks_tasks()

            context = {
                "request": request,
                "domain": domain,
                "task": task,
                "blockers": blockers,
                "blocks": blocks,
            }
            is_htmx = request.headers.get("HX-Request") == "true"
            if is_htmx:
                return self.templates.TemplateResponse(
                    "pm_task.html",
                    context,
                    block_name="sb_main_content"
                )
            else:
                return self.templates.TemplateResponse(
                    "pm_task.html",
                    context
                )

        @router.get("/{domain}/phase/{phase_id}", response_class=HTMLResponse, name="pm:phase")
        async def pm_phase(request: Request, domain: str, phase_id: int) -> Response:
            db = self._get_db(domain)
            phase = db.get_phase_by_id(phase_id)
            if not phase:
                raise HTTPException(status_code=404, detail="Phase not found")

            # Redirect to SW story page if this phase has an SW overlay
            if self._is_sw_domain(domain):
                story = db.sw_model_db.get_story_for_phase(phase_id)
                if story:
                    return RedirectResponse(
                        url=request.url_for("sw:story", domain=domain, story_id=story.story_id),
                        status_code=307)

            self.dpm_manager.set_last_phase(domain, phase)

            context =  {
                "request": request,
                "domain": domain,
                "phase": phase,
            }
            is_htmx = request.headers.get("HX-Request") == "true"
            if is_htmx:
                return self.templates.TemplateResponse(
                    "pm_phase.html",
                    context,
                    block_name="sb_main_content"
                )
            else:
                return self.templates.TemplateResponse(
                    "pm_phase.html",
                    context,
                )

        @router.get("/{domain}/task/{task_id}", response_class=HTMLResponse, name="pm:task-detail")
        async def pm_task(request: Request, domain: str, task_id: int) -> Response:
            db = self._get_db(domain)
            task = db.get_task_by_id(task_id)
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")

            # Redirect to SW task page if this task has an SW overlay
            if self._is_sw_domain(domain):
                swtask = db.sw_model_db.get_swtask_for_task(task_id)
                if swtask:
                    return RedirectResponse(
                        url=request.url_for("sw:task", domain=domain, swtask_id=swtask.swtask_id),
                        status_code=307)

            self.dpm_manager.set_last_task(domain, task)

            blockers = task.get_blockers(only_not_done=False)
            blocks = task.blocks_tasks()

            context = {
                "request": request,
                "domain": domain,
                "task": task,
                "blockers": blockers,
                "blocks": blocks,
            }
            is_htmx = request.headers.get("HX-Request") == "true"
            if is_htmx:
                return self.templates.TemplateResponse(
                    "pm_task.html",
                    context,
                    block_name="sb_main_content"
                )
            else:
                return self.templates.TemplateResponse(
                    "pm_task.html",
                    context
                )

        # This route must be last since /{domain} is a catch-all pattern
        @router.get("/{domain}", response_class=HTMLResponse, name="pm:domain")
        async def pm_domain(request: Request, domain: str) -> Response:
            if domain in ('favicon.ico', 'robots.txt'):
                raise HTTPException(status_code=404)

            all_domains = self.dpm_manager.get_domains()
            domain_info = all_domains.get(domain)
            if not domain_info:
                raise HTTPException(status_code=404, detail=f"Domain '{domain}' not found")

            if domain_info.domain_mode == DomainMode.SOFTWARE:
                return RedirectResponse(
                    url=request.url_for("sw:domain", domain=domain),
                    status_code=307
                )

            self.dpm_manager.set_last_domain(domain)
            db = self._get_db(domain)
            projects = db.get_projects()

            context = {
                "request": request,
                "domain_name": domain,
                "domain_description": domain_info.description,
                "projects": projects,
            }
            is_htmx = request.headers.get("HX-Request") == "true"
            if is_htmx:
                return self.templates.TemplateResponse(
                    "pm_domain.html",
                    context,
                    block_name="sb_main_content"
                )
            else:
                return self.templates.TemplateResponse(
                    "pm_domain.html",
                    context
                )

        return router
