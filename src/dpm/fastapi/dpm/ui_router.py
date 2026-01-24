import logging
from pathlib import Path
from datetime import datetime
import time
import asyncio
from fastapi.templating import Jinja2Templates
from fastapi import APIRouter, Request, HTTPException, Form
from typing import Optional
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
        async def pm_nav_projects(request: Request, domain: str):
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
                return RedirectResponse(url=request.url_for("pm:nav-domain-projects", domain=domain))
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
        async def pm_nav_project_children(request: Request, domain: str, project_id: int):
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
                return RedirectResponse(url=request.url_for("pm:nav-project-children", domain=domain, project_id=project_id))
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
            return self.templates.TemplateResponse(
                "pm_nav_project_children.html",
                context,
                block_name="sb_main_content"
            )

        @router.get("/nav/{domain}/phase/{phase_id}/tasks", response_class=HTMLResponse, name="pm:nav-phase-tasks")
        async def pm_nav_phase_tasks(request: Request, domain: str, phase_id: int):
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
                return RedirectResponse(url=request.url_for("pm:nav-phase-tasks", domain=domain, phase_id=phase_id))
            db = self._get_db(domain)
            phase = db.get_phase_by_id(phase_id)
            if not phase:
                raise HTTPException(status_code=404, detail="Phase not found")

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

        # ====================================================================
        # CRUD Routes — Project management (must be before /{project_id} routes)
        # ====================================================================

        @router.get("/{domain}/project/new", response_class=HTMLResponse, name="pm:project-create")
        async def pm_project_create(request: Request, domain: str, parent_id: Optional[int] = None):
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
                return RedirectResponse(url=request.url_for("pm:project-create", domain=domain))
            db = self._get_db(domain)
            projects = db.get_projects()

            context = {
                "request": request,
                "domain": domain,
                "projects": projects,
                "preselect_parent_id": parent_id,
            }
            is_htmx = request.headers.get("HX-Request") == "true"
            if is_htmx:
                return self.templates.TemplateResponse(
                    "pm_project_create.html",
                    context,
                    block_name="sb_main_content"
                )
            else:
                return self.templates.TemplateResponse(
                    "pm_project_create.html",
                    context
                )

        @router.post("/{domain}/project/new", response_class=HTMLResponse, name="pm:project-create-submit")
        async def pm_project_create_submit(
            request: Request,
            domain: str,
            name: str = Form(...),
            description: str = Form(""),
            parent_id: str = Form("")
        ):
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
            db = self._get_db(domain)

            # Convert parent_id to int or None
            parent_id_int = int(parent_id) if parent_id else None

            try:
                project = db.add_project(
                    name=name,
                    description=description if description else None,
                    parent_id=parent_id_int
                )
                context = {
                    "request": request,
                    "success": True,
                    "message": f"Project '{name}' created successfully!",
                    "redirect_url": request.url_for("pm:project", domain=domain, project_id=project.project_id)
                }
            except Exception as e:
                logger.exception("Failed to create project")
                context = {
                    "request": request,
                    "success": False,
                    "message": f"Failed to create project: {str(e)}"
                }

            return self.templates.TemplateResponse("pm_form_result.html", context)

        @router.get("/{domain}/project/{project_id}/edit", response_class=HTMLResponse, name="pm:project-edit")
        async def pm_project_edit(request: Request, domain: str, project_id: int):
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
                return RedirectResponse(url=request.url_for("pm:project-edit", domain=domain, project_id=project_id))
            db = self._get_db(domain)
            project = db.get_project_by_id(project_id)
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")

            projects = db.get_projects()

            context = {
                "request": request,
                "domain": domain,
                "project": project,
                "projects": projects,
            }
            is_htmx = request.headers.get("HX-Request") == "true"
            if is_htmx:
                return self.templates.TemplateResponse(
                    "pm_project_edit.html",
                    context,
                    block_name="sb_main_content"
                )
            else:
                return self.templates.TemplateResponse(
                    "pm_project_edit.html",
                    context
                )

        @router.post("/{domain}/project/{project_id}/edit", response_class=HTMLResponse, name="pm:project-edit-submit")
        async def pm_project_edit_submit(
            request: Request,
            domain: str,
            project_id: int,
            name: str = Form(...),
            description: str = Form(""),
            parent_id: str = Form("")
        ):
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
            db = self._get_db(domain)

            project = db.get_project_by_id(project_id)
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")

            # Convert parent_id to int or None
            parent_id_int = int(parent_id) if parent_id else None

            # Prevent circular parent reference
            if parent_id_int == project_id:
                context = {
                    "request": request,
                    "success": False,
                    "message": "A project cannot be its own parent"
                }
                return self.templates.TemplateResponse("pm_form_result.html", context)

            try:
                project.name = name
                project.description = description if description else None
                project.parent_id = parent_id_int
                project.save()

                context = {
                    "request": request,
                    "success": True,
                    "message": f"Project '{name}' updated successfully!",
                    "redirect_url": request.url_for("pm:project", domain=domain, project_id=project.project_id)
                }
            except Exception as e:
                logger.exception("Failed to update project")
                context = {
                    "request": request,
                    "success": False,
                    "message": f"Failed to update project: {str(e)}"
                }

            return self.templates.TemplateResponse("pm_form_result.html", context)

        @router.get("/{domain}/project/{project_id}/delete", response_class=HTMLResponse, name="pm:project-delete")
        async def pm_project_delete(request: Request, domain: str, project_id: int):
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
                return RedirectResponse(url=request.url_for("pm:project-delete", domain=domain, project_id=project_id))
            db = self._get_db(domain)
            project = db.get_project_by_id(project_id)
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")

            phases = project.get_phases()
            tasks = project.get_tasks()
            children = project.get_kids()

            context = {
                "request": request,
                "domain": domain,
                "project": project,
                "phases_count": len(phases),
                "tasks_count": len(tasks),
                "children_count": len(children),
            }
            is_htmx = request.headers.get("HX-Request") == "true"
            if is_htmx:
                return self.templates.TemplateResponse(
                    "pm_project_delete.html",
                    context,
                    block_name="sb_main_content"
                )
            else:
                return self.templates.TemplateResponse(
                    "pm_project_delete.html",
                    context
                )

        @router.post("/{domain}/project/{project_id}/delete", response_class=HTMLResponse, name="pm:project-delete-submit")
        async def pm_project_delete_submit(request: Request, domain: str, project_id: int):
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
            db = self._get_db(domain)

            project = db.get_project_by_id(project_id)
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")

            project_name = project.name

            try:
                project.delete_from_db()
                context = {
                    "request": request,
                    "success": True,
                    "message": f"Project '{project_name}' deleted successfully!",
                    "redirect_url": request.url_for("pm:domain-projects", domain=domain)
                }
            except Exception as e:
                logger.exception("Failed to delete project")
                context = {
                    "request": request,
                    "success": False,
                    "message": f"Failed to delete project: {str(e)}"
                }

            return self.templates.TemplateResponse("pm_form_result.html", context)

        # ====================================================================
        # CRUD Routes — Phase management
        # ====================================================================

        @router.get("/{domain}/project/{project_id}/phase/new", response_class=HTMLResponse, name="pm:phase-create")
        async def pm_phase_create(request: Request, domain: str, project_id: int):
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
                return RedirectResponse(url=request.url_for("pm:phase-create", domain=domain, project_id=project_id))
            db = self._get_db(domain)
            project = db.get_project_by_id(project_id)
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")

            context = {
                "request": request,
                "domain": domain,
                "project": project,
            }
            is_htmx = request.headers.get("HX-Request") == "true"
            if is_htmx:
                return self.templates.TemplateResponse(
                    "pm_phase_create.html",
                    context,
                    block_name="sb_main_content"
                )
            else:
                return self.templates.TemplateResponse(
                    "pm_phase_create.html",
                    context
                )

        @router.post("/{domain}/project/{project_id}/phase/new", response_class=HTMLResponse, name="pm:phase-create-submit")
        async def pm_phase_create_submit(
            request: Request,
            domain: str,
            project_id: int,
            name: str = Form(...),
            description: str = Form("")
        ):
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
            db = self._get_db(domain)

            project = db.get_project_by_id(project_id)
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")

            try:
                phase = db.add_phase(
                    name=name,
                    description=description if description else None,
                    project_id=project_id
                )
                context = {
                    "request": request,
                    "success": True,
                    "message": f"Phase '{name}' created successfully!",
                    "redirect_url": request.url_for("pm:phase", domain=domain, phase_id=phase.phase_id)
                }
            except Exception as e:
                logger.exception("Failed to create phase")
                context = {
                    "request": request,
                    "success": False,
                    "message": f"Failed to create phase: {str(e)}"
                }

            return self.templates.TemplateResponse("pm_form_result.html", context)

        @router.get("/{domain}/phase/{phase_id}/edit", response_class=HTMLResponse, name="pm:phase-edit")
        async def pm_phase_edit(request: Request, domain: str, phase_id: int):
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
                return RedirectResponse(url=request.url_for("pm:phase-edit", domain=domain, phase_id=phase_id))
            db = self._get_db(domain)
            phase = db.get_phase_by_id(phase_id)
            if not phase:
                raise HTTPException(status_code=404, detail="Phase not found")

            projects = db.get_projects()

            context = {
                "request": request,
                "domain": domain,
                "phase": phase,
                "projects": projects,
            }
            is_htmx = request.headers.get("HX-Request") == "true"
            if is_htmx:
                return self.templates.TemplateResponse(
                    "pm_phase_edit.html",
                    context,
                    block_name="sb_main_content"
                )
            else:
                return self.templates.TemplateResponse(
                    "pm_phase_edit.html",
                    context
                )

        @router.post("/{domain}/phase/{phase_id}/edit", response_class=HTMLResponse, name="pm:phase-edit-submit")
        async def pm_phase_edit_submit(
            request: Request,
            domain: str,
            phase_id: int,
            name: str = Form(...),
            description: str = Form(""),
            project_id: str = Form(...)
        ):
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
            db = self._get_db(domain)

            phase = db.get_phase_by_id(phase_id)
            if not phase:
                raise HTTPException(status_code=404, detail="Phase not found")

            project_id_int = int(project_id)

            try:
                phase.name = name
                phase.description = description if description else None
                if phase.project_id != project_id_int:
                    phase.move_phase_and_tasks_to_project(project_id_int)
                phase.save()

                context = {
                    "request": request,
                    "success": True,
                    "message": f"Phase '{name}' updated successfully!",
                    "redirect_url": request.url_for("pm:phase", domain=domain, phase_id=phase.phase_id)
                }
            except Exception as e:
                logger.exception("Failed to update phase")
                context = {
                    "request": request,
                    "success": False,
                    "message": f"Failed to update phase: {str(e)}"
                }

            return self.templates.TemplateResponse("pm_form_result.html", context)

        @router.get("/{domain}/phase/{phase_id}/delete", response_class=HTMLResponse, name="pm:phase-delete")
        async def pm_phase_delete(request: Request, domain: str, phase_id: int):
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
                return RedirectResponse(url=request.url_for("pm:phase-delete", domain=domain, phase_id=phase_id))
            db = self._get_db(domain)
            phase = db.get_phase_by_id(phase_id)
            if not phase:
                raise HTTPException(status_code=404, detail="Phase not found")

            project = db.get_project_by_id(phase.project_id)
            tasks = phase.get_tasks()

            context = {
                "request": request,
                "domain": domain,
                "phase": phase,
                "project": project,
                "tasks_count": len(tasks),
            }
            is_htmx = request.headers.get("HX-Request") == "true"
            if is_htmx:
                return self.templates.TemplateResponse(
                    "pm_phase_delete.html",
                    context,
                    block_name="sb_main_content"
                )
            else:
                return self.templates.TemplateResponse(
                    "pm_phase_delete.html",
                    context
                )

        @router.post("/{domain}/phase/{phase_id}/delete", response_class=HTMLResponse, name="pm:phase-delete-submit")
        async def pm_phase_delete_submit(request: Request, domain: str, phase_id: int):
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
            db = self._get_db(domain)

            phase = db.get_phase_by_id(phase_id)
            if not phase:
                raise HTTPException(status_code=404, detail="Phase not found")

            phase_name = phase.name
            project_id = phase.project_id

            try:
                phase.delete_from_db()
                context = {
                    "request": request,
                    "success": True,
                    "message": f"Phase '{phase_name}' deleted successfully!",
                    "redirect_url": request.url_for("pm:project", domain=domain, project_id=project_id)
                }
            except Exception as e:
                logger.exception("Failed to delete phase")
                context = {
                    "request": request,
                    "success": False,
                    "message": f"Failed to delete phase: {str(e)}"
                }

            return self.templates.TemplateResponse("pm_form_result.html", context)

        # ====================================================================
        # CRUD Routes — Task management
        # ====================================================================

        @router.get("/{domain}/project/{project_id}/task/new", response_class=HTMLResponse, name="pm:task-create-in-project")
        async def pm_task_create_in_project(request: Request, domain: str, project_id: int):
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
                return RedirectResponse(url=request.url_for("pm:task-create-in-project", domain=domain, project_id=project_id))
            db = self._get_db(domain)
            project = db.get_project_by_id(project_id)
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")

            context = {
                "request": request,
                "domain": domain,
                "project": project,
                "phase": None,
            }
            is_htmx = request.headers.get("HX-Request") == "true"
            if is_htmx:
                return self.templates.TemplateResponse(
                    "pm_task_create.html",
                    context,
                    block_name="sb_main_content"
                )
            else:
                return self.templates.TemplateResponse(
                    "pm_task_create.html",
                    context
                )

        @router.post("/{domain}/project/{project_id}/task/new", response_class=HTMLResponse, name="pm:task-create-in-project-submit")
        async def pm_task_create_in_project_submit(
            request: Request,
            domain: str,
            project_id: int,
            name: str = Form(...),
            status: str = Form("ToDo"),
            description: str = Form("")
        ):
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
            db = self._get_db(domain)

            project = db.get_project_by_id(project_id)
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")

            try:
                task = db.add_task(
                    name=name,
                    status=status,
                    description=description if description else None,
                    project_id=project_id,
                    phase_id=None
                )
                context = {
                    "request": request,
                    "success": True,
                    "message": f"Task '{name}' created successfully!",
                    "redirect_url": request.url_for("pm:task-detail", domain=domain, task_id=task.task_id)
                }
            except Exception as e:
                logger.exception("Failed to create task")
                context = {
                    "request": request,
                    "success": False,
                    "message": f"Failed to create task: {str(e)}"
                }

            return self.templates.TemplateResponse("pm_form_result.html", context)

        @router.get("/{domain}/phase/{phase_id}/task/new", response_class=HTMLResponse, name="pm:task-create-in-phase")
        async def pm_task_create_in_phase(request: Request, domain: str, phase_id: int):
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
                return RedirectResponse(url=request.url_for("pm:task-create-in-phase", domain=domain, phase_id=phase_id))
            db = self._get_db(domain)
            phase = db.get_phase_by_id(phase_id)
            if not phase:
                raise HTTPException(status_code=404, detail="Phase not found")
            project = db.get_project_by_id(phase.project_id)

            context = {
                "request": request,
                "domain": domain,
                "project": project,
                "phase": phase,
            }
            is_htmx = request.headers.get("HX-Request") == "true"
            if is_htmx:
                return self.templates.TemplateResponse(
                    "pm_task_create.html",
                    context,
                    block_name="sb_main_content"
                )
            else:
                return self.templates.TemplateResponse(
                    "pm_task_create.html",
                    context
                )

        @router.post("/{domain}/phase/{phase_id}/task/new", response_class=HTMLResponse, name="pm:task-create-in-phase-submit")
        async def pm_task_create_in_phase_submit(
            request: Request,
            domain: str,
            phase_id: int,
            name: str = Form(...),
            status: str = Form("ToDo"),
            description: str = Form("")
        ):
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
            db = self._get_db(domain)

            phase = db.get_phase_by_id(phase_id)
            if not phase:
                raise HTTPException(status_code=404, detail="Phase not found")

            try:
                task = db.add_task(
                    name=name,
                    status=status,
                    description=description if description else None,
                    project_id=phase.project_id,
                    phase_id=phase_id
                )
                context = {
                    "request": request,
                    "success": True,
                    "message": f"Task '{name}' created successfully!",
                    "redirect_url": request.url_for("pm:task-detail", domain=domain, task_id=task.task_id)
                }
            except Exception as e:
                logger.exception("Failed to create task")
                context = {
                    "request": request,
                    "success": False,
                    "message": f"Failed to create task: {str(e)}"
                }

            return self.templates.TemplateResponse("pm_form_result.html", context)

        @router.get("/{domain}/task/{task_id}/edit", response_class=HTMLResponse, name="pm:task-edit")
        async def pm_task_edit(request: Request, domain: str, task_id: int):
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
                return RedirectResponse(url=request.url_for("pm:task-edit", domain=domain, task_id=task_id))
            db = self._get_db(domain)
            task = db.get_task_by_id(task_id)
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")

            projects = db.get_projects()
            phases = db.get_phases()

            context = {
                "request": request,
                "domain": domain,
                "task": task,
                "projects": projects,
                "phases": phases,
            }
            is_htmx = request.headers.get("HX-Request") == "true"
            if is_htmx:
                return self.templates.TemplateResponse(
                    "pm_task_edit.html",
                    context,
                    block_name="sb_main_content"
                )
            else:
                return self.templates.TemplateResponse(
                    "pm_task_edit.html",
                    context
                )

        @router.post("/{domain}/task/{task_id}/edit", response_class=HTMLResponse, name="pm:task-edit-submit")
        async def pm_task_edit_submit(
            request: Request,
            domain: str,
            task_id: int,
            name: str = Form(...),
            status: str = Form(...),
            description: str = Form(""),
            project_id: str = Form(...),
            phase_id: str = Form("")
        ):
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
            db = self._get_db(domain)

            task = db.get_task_by_id(task_id)
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")

            project_id_int = int(project_id)
            phase_id_int = int(phase_id) if phase_id else None

            try:
                task.name = name
                task.status = status
                task.description = description if description else None
                task.project_id = project_id_int
                task.phase_id = phase_id_int
                task.save()

                context = {
                    "request": request,
                    "success": True,
                    "message": f"Task '{name}' updated successfully!",
                    "redirect_url": request.url_for("pm:task-detail", domain=domain, task_id=task.task_id)
                }
            except Exception as e:
                logger.exception("Failed to update task")
                context = {
                    "request": request,
                    "success": False,
                    "message": f"Failed to update task: {str(e)}"
                }

            return self.templates.TemplateResponse("pm_form_result.html", context)

        @router.get("/{domain}/task/{task_id}/delete", response_class=HTMLResponse, name="pm:task-delete")
        async def pm_task_delete(request: Request, domain: str, task_id: int):
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
                return RedirectResponse(url=request.url_for("pm:task-delete", domain=domain, task_id=task_id))
            db = self._get_db(domain)
            task = db.get_task_by_id(task_id)
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")

            blockers = task.get_blockers()
            blocks = task.blocks_tasks()

            context = {
                "request": request,
                "domain": domain,
                "task": task,
                "blockers_count": len(blockers),
                "blocks_count": len(blocks),
            }
            is_htmx = request.headers.get("HX-Request") == "true"
            if is_htmx:
                return self.templates.TemplateResponse(
                    "pm_task_delete.html",
                    context,
                    block_name="sb_main_content"
                )
            else:
                return self.templates.TemplateResponse(
                    "pm_task_delete.html",
                    context
                )

        @router.post("/{domain}/task/{task_id}/delete", response_class=HTMLResponse, name="pm:task-delete-submit")
        async def pm_task_delete_submit(request: Request, domain: str, task_id: int):
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
            db = self._get_db(domain)

            task = db.get_task_by_id(task_id)
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")

            task_name = task.name
            project_id = task.project_id
            phase_id = task.phase_id

            try:
                task.delete_from_db()
                if phase_id:
                    redirect_url = request.url_for("pm:phase", domain=domain, phase_id=phase_id)
                else:
                    redirect_url = request.url_for("pm:project", domain=domain, project_id=project_id)
                context = {
                    "request": request,
                    "success": True,
                    "message": f"Task '{task_name}' deleted successfully!",
                    "redirect_url": redirect_url
                }
            except Exception as e:
                logger.exception("Failed to delete task")
                context = {
                    "request": request,
                    "success": False,
                    "message": f"Failed to delete task: {str(e)}"
                }

            return self.templates.TemplateResponse("pm_form_result.html", context)

        # ====================================================================
        # Detail View Routes — Individual item views
        # ====================================================================

        @router.get("/{domain}/project/{project_id}", response_class=HTMLResponse, name="pm:project")
        async def pm_project_detail(request: Request, domain: str, project_id: int):
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
