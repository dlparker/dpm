import logging
from pathlib import Path
from datetime import datetime
import time
import asyncio
from fastapi.templating import Jinja2Templates
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

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

    def __init__(self, server, dpm_manager):
        self.server = server
        self.dpm_manager = dpm_manager
        self.templates = server.templates
        self.templates.env.filters['format_timestamp'] = format_timestamp
        self.templates.env.filters['time_ago'] = time_ago

    def _get_db(self, domain):
        return self.dpm_manager.get_db_for_domain(domain)
    
    def become_router(self):
        router = APIRouter()

        # ====================================================================
        # Tree View Routes — PM section
        # ====================================================================

        @router.get("/domains", response_class=HTMLResponse, name="pm:domains")
        async def pm_domains(request: Request):

            domains = [
                {"name": name, "description": item.description}
                for name, item in self.dpm_manager.get_domains().items()
            ]
            context = {"request": request, "domains": domains}
            is_htmx = request.headers.get("HX-Request") == "true"
            if is_htmx:
                return self.templates.TemplateResponse(
                    "pm_domains.html",
                    context,
                    block_name="sb_main_content"
                )
            else:
                return self.templates.TemplateResponse(
                    "pm_domains.html",
                    context
                )

        @router.get("/nav_tree", response_class=HTMLResponse, name="pm:nav_tree")
        async def pm_domains(request: Request):
            domains = [
                {"name": name, "description": item.description}
                for name, item in self.dpm_manager.get_domains().items()
            ]
            context = {"request": request, "domains": domains}
            is_htmx = request.headers.get("HX-Request") == "true"
            if is_htmx:
                return self.templates.TemplateResponse(
                    "pm_domains.html",
                    context,
                    block_name="sb_main_content"
                )
            else:
                return self.templates.TemplateResponse(
                    "pm_domains.html",
                    context
                )

        @router.get("/{domain}/projects", response_class=HTMLResponse, name="pm:domain-projects")
        async def pm_projects(request: Request, domain: str):
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
                return RedirectResponse(url=request.url_for("pm:domain-projects", domain=domain))            
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
        async def pm_project_children(request: Request, domain: str, project_id: int):
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
                return RedirectResponse(url=request.url_for("pm:project-chidren", domain=domain,
                                                            project_id=project_id))            
            db = self._get_db(domain)
            project = db.get_project_by_id(project_id)
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")

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
        async def pm_phase_tasks(request: Request, domain: str, phase_id: int):
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
                return RedirectResponse(url=request.url_for("pm:phase-tasks", domain=domain,
                                                            phase_id=phase_id))            
            db = self._get_db(domain)
            phase = db.get_phase_by_id(phase_id)
            if not phase:
                raise HTTPException(status_code=404, detail="Phase not found")

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

        @router.get("/{domain}/project/{project_id}", response_class=HTMLResponse, name="pm:project")
        async def pm_phase_tasks(request: Request, domain: str, project_id: int):
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
                return RedirectResponse(url=request.url_for("pm:phase-tasks", domain=domain,
                                                            project_id=project_id))            
            db = self._get_db(domain)
            project = db.get_project_by_id(project_id)
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
            
        @router.get("/{domain}/phase/{phase_id}", response_class=HTMLResponse, name="pm:phase")
        async def pm_phase_tasks(request: Request, domain: str, phase_id: int):
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
                return RedirectResponse(url=request.url_for("pm:phase-tasks", domain=domain,
                                                            phase_id=phase_id))            
            db = self._get_db(domain)
            phase = db.get_phase_by_id(phase_id)
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

        @router.get("/{domain}/task/{task_id}", response_class=HTMLResponse, name="pm:task-detail")
        async def pm_task(request: Request, domain: str, task_id: int):
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
                return RedirectResponse(url=request.url_for("pm:task-detail", domain=domain,
                                                            task_id=task_id))            
            db = self._get_db(domain)
            task = db.get_task_by_id(task_id)
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")

            context = {
                "request": request,
                "domain": domain,
                "task": task
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
        
        return router
