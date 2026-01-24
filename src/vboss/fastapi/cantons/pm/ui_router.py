import logging
from pathlib import Path
from datetime import datetime
import time
import asyncio
from fastapi.templating import Jinja2Templates
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

logger = logging.getLogger("UIRouter")


def format_timestamp(ts):
    """Format Unix timestamp as readable datetime."""
    if ts is None:
        return None
    return datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')


def time_ago(ts):
    """Format Unix timestamp as relative time (e.g., '2 seconds ago')."""
    if ts is None:
        return None
    elapsed = time.time() - ts
    if elapsed < 60:
        return f"{int(elapsed)}s ago"
    elif elapsed < 3600:
        return f"{int(elapsed / 60)}m ago"
    elif elapsed < 86400:
        return f"{int(elapsed / 3600)}h ago"
    else:
        return f"{int(elapsed / 86400)}d ago"


class PMUIRouter:
    """Router for HTML UI pages using HTMX, Tailwind CSS, and daisyUI."""

    def __init__(self, server):
        self.server = server
        self.domain_catalog = server.domain_catalog
        self.templates = server.templates
        self.templates.env.filters['format_timestamp'] = format_timestamp
        self.templates.env.filters['time_ago'] = time_ago

    def become_router(self):
        router = APIRouter()

        # ====================================================================
        # Tree View Routes — PM section
        # ====================================================================

        @router.get("/domains", response_class=HTMLResponse, name="pm:domains")
        async def pm_domains(request: Request):
            """Return domains list for tree view."""
            domains = [
                {"name": name, "description": item.description}
                for name, item in self.domain_catalog.pmdb_domains.items()
            ]
            return self.templates.TemplateResponse(
                "pm_domains.html",
                {"request": request, "domains": domains}
            )

        @router.get("/TAP/task", response_class=HTMLResponse, name="pm:tap-task") 
        async def tap_task(request: Request):
            from vboss.fastapi.server import TAPFocus
            if self.server.tap_focus is None:
                domain = next(iter(self.domain_catalog.pmdb_domains))
                db = self.domain_catalog.pmdb_domains[domain].db
                f_dict = dict(domain=domain, url_name="pm:", task_id=1)
                focus = self.server.tap_focus = TAPFocus(state=f_dict)
            else:
                focus = self.server.tap_focus
                db = self.domain_catalog.pmdb_domains[focus.state['domain']].db
            task = db.get_task_by_id(focus.state['task_id'])
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")
            
            return self.templates.TemplateResponse(
                "tap_task.html",
                {
                    "request": request,
                    "domain": focus.state['domain'],
                    "task": task
                }
            )

        @router.get("/{domain}/projects", response_class=HTMLResponse, name="pm:domain-projects")
        async def pm_projects(request: Request, domain: str):
            db = self.domain_catalog.pmdb_domains[domain].db
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
        async def pm_project_children(request: Request, domain: str, project_id: int):
            """Return phases and tasks for a project."""
            db = self.domain_catalog.pmdb_domains[domain].db
            project = db.get_project_by_id(project_id)
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")

            phases = project.get_phases()
            all_tasks = project.get_tasks()
            direct_tasks = [t for t in all_tasks if t.phase_id is None]

            return self.templates.TemplateResponse(
                "frags/pm_project_children.html",
                {
                    "request": request,
                    "domain": domain,
                    "project": project,
                    "phases": phases,
                    "tasks": direct_tasks
                }
            )

        @router.get("/{domain}/project/{project_id}/children-frag", response_class=HTMLResponse, name="pm:project-children-frag")
        async def pm_project_children(request: Request, domain: str, project_id: int):
            """Return phases and tasks for a project."""
            db = self.domain_catalog.pmdb_domains[domain].db
            project = db.get_project_by_id(project_id)
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")

            phases = project.get_phases()
            all_tasks = project.get_tasks()
            direct_tasks = [t for t in all_tasks if t.phase_id is None]

            return self.templates.TemplateResponse(
                "pm_project_children.html",
                {
                    "request": request,
                    "domain": domain,
                    "project": project,
                    "phases": phases,
                    "tasks": direct_tasks
                }
            )
            rendered_html = render_block(
                environment, "page.html.jinja2", "content", magic_number=42
            )            
        @router.get("/{domain}/phase/{phase_id}/tasks", response_class=HTMLResponse, name="pm:phase-tasks")
        async def pm_phase_tasks(request: Request, domain: str, phase_id: int):
            """Return tasks for a phase."""
            db = self.domain_catalog.pmdb_domains[domain].db
            phase = db.get_phase_by_id(phase_id)
            if not phase:
                raise HTTPException(status_code=404, detail="Phase not found")

            tasks = phase.get_tasks()
            return self.templates.TemplateResponse(
                "pm_tasks.html",
                {
                    "request": request,
                    "domain": domain,
                    "phase": phase,
                    "tasks": tasks
                }
            )

        @router.get("/{domain}/phase/{phase_id}/tasks-partial", response_class=HTMLResponse, name="pm:phase-tasks-partial")
        async def pm_phase_tasks(request: Request, domain: str, phase_id: int):
            db = self.domain_catalog.pmdb_domains[domain].db
            phase = db.get_phase_by_id(phase_id)
            if not phase:
                raise HTTPException(status_code=404, detail="Phase not found")

            tasks = phase.get_tasks()
            return self.templates.TemplateResponse(
                "pm_tasks_partial.html",
                {
                    "request": request,
                    "domain": domain,
                    "phase": phase,
                    "tasks": tasks
                }
            )

        @router.get("/{domain}/task/{task_id}", response_class=HTMLResponse, name="pm:task-detail")
        async def pm_task(request: Request, domain: str, task_id: int):
            """Return detail view for a single task."""
            db = self.domain_catalog.pmdb_domains[domain].db
            task = db.get_task_by_id(task_id)
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")

            return self.templates.TemplateResponse(
                "pm_task.html",
                {
                    "request": request,
                    "domain": domain,
                    "task": task
                }
            )

        @router.get("/{domain}/task/{task_id}/partial", response_class=HTMLResponse, name="pm:task-detail-partial")
        async def pm_task(request: Request, domain: str, task_id: int):
            db = self.domain_catalog.pmdb_domains[domain].db
            task = db.get_task_by_id(task_id)
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")

            return self.templates.TemplateResponse(
                "pm_task_partial.html",
                {
                    "request": request,
                    "domain": domain,
                    "task": task
                }
            )

        return router
