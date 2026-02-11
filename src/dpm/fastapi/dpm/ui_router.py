from __future__ import annotations

import html
import json
import logging
import time
from datetime import datetime
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from dpm.fastapi.ops import ServerOps
from dpm.store.wrappers import  ModelDB, TaskRecord
from dpm.store.domains import DPMManager

logger = logging.getLogger("UIRouter")


def format_timestamp(ts: float | None) -> str | None:
    """Format Unix timestamp as readable datetime."""
    if ts is None:
        return None
    return datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')


def time_ago(ts: float | None) -> str | None:
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


class PMDBUIRouter:
    """Router for HTML UI pages using HTMX, Tailwind CSS, and daisyUI."""

    def __init__(self, server: ServerOps, dpm_manager: DPMManager) -> None:
        self.server = server
        self.dpm_manager = dpm_manager
        self.templates = server.templates
        self.templates.env.filters['format_timestamp'] = format_timestamp
        self.templates.env.filters['time_ago'] = time_ago

    def _get_db(self, domain: str) -> ModelDB:
        return self.dpm_manager.get_db_for_domain(domain)
    
    def become_router(self) -> APIRouter:
        router = APIRouter()

        # ====================================================================
        # Tree View Routes — PM section
        # ====================================================================

        @router.get("/domains", response_class=HTMLResponse, name="pm:domains")
        async def pm_domains(request: Request) -> Response:

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
        async def pm_nav_tree(request: Request) -> Response:
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
        async def pm_nav_projects(request: Request, domain: str) -> Response:
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
                return RedirectResponse(url=request.url_for("pm:nav-domain-projects", domain=domain))
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
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
                return RedirectResponse(url=request.url_for("pm:nav-project-children", domain=domain, project_id=project_id))
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
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
                return RedirectResponse(url=request.url_for("pm:nav-phase-tasks", domain=domain, phase_id=phase_id))
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
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
                return RedirectResponse(url=request.url_for("pm:domain-projects", domain=domain))
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
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
                return RedirectResponse(url=request.url_for("pm:project-chidren", domain=domain,
                                                            project_id=project_id))
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
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
                return RedirectResponse(url=request.url_for("pm:phase-tasks", domain=domain,
                                                            phase_id=phase_id))
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
        # CRUD Routes — Project management (must be before /{project_id} routes)
        # ====================================================================

        @router.get("/{domain}/project/new", response_class=HTMLResponse, name="pm:project-create")
        async def pm_project_create(request: Request, domain: str, parent_id: int | None = None) -> Response:
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
                return RedirectResponse(url=request.url_for("pm:project-create", domain=domain))
            self.dpm_manager.set_last_domain(domain)
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
        ) -> Response:
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
            self.dpm_manager.set_last_domain(domain)
            db = self._get_db(domain)

            # Convert parent_id to int or None
            parent_id_int = int(parent_id) if parent_id else None

            try:
                project = db.add_project(
                    name=name,
                    description=description if description else None,
                    parent_id=parent_id_int
                )
                self.dpm_manager.set_last_project(domain, project)
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
        async def pm_project_edit(request: Request, domain: str, project_id: int) -> Response:
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
                return RedirectResponse(url=request.url_for("pm:project-edit", domain=domain, project_id=project_id))
            db = self._get_db(domain)
            project = db.get_project_by_id(project_id)
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            self.dpm_manager.set_last_project(domain, project)

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
        ) -> Response:
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
            db = self._get_db(domain)

            project = db.get_project_by_id(project_id)
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            self.dpm_manager.set_last_project(domain, project)

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

        @router.get("/{domain}/project/{project_id}/edit-modal", response_class=HTMLResponse, name="pm:project-edit-modal")
        async def pm_project_edit_modal(request: Request, domain: str, project_id: int) -> Response:
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
            db = self._get_db(domain)
            project = db.get_project_by_id(project_id)
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            self.dpm_manager.set_last_project(domain, project)

            projects = db.get_projects()

            context = {
                "request": request,
                "domain": domain,
                "project": project,
                "projects": projects,
            }
            return self.templates.TemplateResponse("pm_project_edit_modal.html", context)

        @router.post("/{domain}/project/{project_id}/edit-modal", response_class=HTMLResponse, name="pm:project-edit-modal-submit")
        async def pm_project_edit_modal_submit(
            request: Request,
            domain: str,
            project_id: int,
            name: str = Form(...),
            description: str = Form(""),
            parent_id: str = Form("")
        ) -> Response:
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
            db = self._get_db(domain)

            project = db.get_project_by_id(project_id)
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            self.dpm_manager.set_last_project(domain, project)

            try:
                project.name = name
                project.description = description if description else None
                project.parent_id = int(parent_id) if parent_id else None
                project.save()

                # Return empty response with trigger to close modal
                response = HTMLResponse("")
                response.headers["HX-Trigger"] = '{"close-modal": true}'
                return response
            except Exception as e:
                logger.exception("Failed to update project")
                context = {
                    "request": request,
                    "success": False,
                    "message": f"Failed to update project: {str(e)}"
                }
                return self.templates.TemplateResponse("pm_form_result.html", context)

        @router.get("/{domain}/project/{project_id}/delete", response_class=HTMLResponse, name="pm:project-delete")
        async def pm_project_delete(request: Request, domain: str, project_id: int) -> Response:
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
                return RedirectResponse(url=request.url_for("pm:project-delete", domain=domain, project_id=project_id))
            db = self._get_db(domain)
            project = db.get_project_by_id(project_id)
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            self.dpm_manager.set_last_project(domain, project)

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
        async def pm_project_delete_submit(request: Request, domain: str, project_id: int) -> Response:
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
            self.dpm_manager.set_last_domain(domain)
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
        async def pm_phase_create(request: Request, domain: str, project_id: int) -> Response:
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
                return RedirectResponse(url=request.url_for("pm:phase-create", domain=domain, project_id=project_id))
            db = self._get_db(domain)
            project = db.get_project_by_id(project_id)
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            self.dpm_manager.set_last_project(domain, project)

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
        ) -> Response:
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
            db = self._get_db(domain)

            project = db.get_project_by_id(project_id)
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            self.dpm_manager.set_last_project(domain, project)

            try:
                phase = db.add_phase(
                    name=name,
                    description=description if description else None,
                    project_id=project_id
                )
                self.dpm_manager.set_last_phase(domain, phase)
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
        async def pm_phase_edit(request: Request, domain: str, phase_id: int) -> Response:
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
                return RedirectResponse(url=request.url_for("pm:phase-edit", domain=domain, phase_id=phase_id))
            db = self._get_db(domain)
            phase = db.get_phase_by_id(phase_id)
            if not phase:
                raise HTTPException(status_code=404, detail="Phase not found")
            self.dpm_manager.set_last_phase(domain, phase)

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
        ) -> Response:
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
            db = self._get_db(domain)

            phase = db.get_phase_by_id(phase_id)
            if not phase:
                raise HTTPException(status_code=404, detail="Phase not found")
            self.dpm_manager.set_last_phase(domain, phase)

            project_id_int = int(project_id)

            try:
                phase.name = name
                phase.description = description if description else None
                if phase.project_id != project_id_int:
                    db.move_phase_and_tasks_to_project(phase.phase_id, project_id_int)
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
        async def pm_phase_delete(request: Request, domain: str, phase_id: int) -> Response:
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
                return RedirectResponse(url=request.url_for("pm:phase-delete", domain=domain, phase_id=phase_id))
            db = self._get_db(domain)
            phase = db.get_phase_by_id(phase_id)
            if not phase:
                raise HTTPException(status_code=404, detail="Phase not found")
            self.dpm_manager.set_last_phase(domain, phase)

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
        async def pm_phase_delete_submit(request: Request, domain: str, phase_id: int) -> Response:
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
            self.dpm_manager.set_last_domain(domain)
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

        @router.get("/{domain}/phase/{phase_id}/edit-modal", response_class=HTMLResponse, name="pm:phase-edit-modal")
        async def pm_phase_edit_modal(request: Request, domain: str, phase_id: int) -> Response:
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
            db = self._get_db(domain)
            phase = db.get_phase_by_id(phase_id)
            if not phase:
                raise HTTPException(status_code=404, detail="Phase not found")
            self.dpm_manager.set_last_phase(domain, phase)

            projects = db.get_projects()

            context = {
                "request": request,
                "domain": domain,
                "phase": phase,
                "projects": projects,
            }
            return self.templates.TemplateResponse("pm_phase_edit_modal.html", context)

        @router.post("/{domain}/phase/{phase_id}/edit-modal", response_class=HTMLResponse, name="pm:phase-edit-modal-submit")
        async def pm_phase_edit_modal_submit(
            request: Request,
            domain: str,
            phase_id: int,
            name: str = Form(...),
            description: str = Form(""),
            project_id: str = Form(...)
        ) -> Response:
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
            db = self._get_db(domain)

            phase = db.get_phase_by_id(phase_id)
            if not phase:
                raise HTTPException(status_code=404, detail="Phase not found")
            self.dpm_manager.set_last_phase(domain, phase)

            project_id_int = int(project_id)

            try:
                phase.name = name
                phase.description = description if description else None
                if phase.project_id != project_id_int:
                    db.move_phase_and_tasks_to_project(phase.phase_id, project_id_int)
                phase.save()

                # Return empty response with trigger to close modal
                response = HTMLResponse("")
                response.headers["HX-Trigger"] = '{"close-modal": true}'
                return response
            except Exception as e:
                logger.exception("Failed to update phase")
                context = {
                    "request": request,
                    "success": False,
                    "message": f"Failed to update phase: {str(e)}"
                }
                return self.templates.TemplateResponse("pm_kanban_message.html", context)

        # ====================================================================
        # CRUD Routes — Task management
        # ====================================================================

        @router.get("/{domain}/project/{project_id}/task/new", response_class=HTMLResponse, name="pm:task-create-in-project")
        async def pm_task_create_in_project(request: Request, domain: str, project_id: int) -> Response:
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
                return RedirectResponse(url=request.url_for("pm:task-create-in-project", domain=domain, project_id=project_id))
            db = self._get_db(domain)
            project = db.get_project_by_id(project_id)
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            self.dpm_manager.set_last_project(domain, project)

            available_tasks = db.get_tasks()

            context = {
                "request": request,
                "domain": domain,
                "project": project,
                "phase": None,
                "available_tasks": available_tasks,
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
        ) -> Response:
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
            db = self._get_db(domain)

            project = db.get_project_by_id(project_id)
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            self.dpm_manager.set_last_project(domain, project)

            # Parse blocker IDs from form data
            form_data = await request.form()
            blocker_ids = [int(bid) for bid in form_data.getlist("blocker_ids") if bid]

            try:
                task = db.add_task(
                    name=name,
                    status=status,
                    description=description if description else None,
                    project_id=project_id,
                    phase_id=None
                )

                # Add blockers
                for bid in blocker_ids:
                    blocker_task = db.get_task_by_id(bid)
                    if blocker_task:
                        task.add_blocker(blocker_task)

                self.dpm_manager.set_last_task(domain, task)
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
        async def pm_task_create_in_phase(request: Request, domain: str, phase_id: int) -> Response:
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
                return RedirectResponse(url=request.url_for("pm:task-create-in-phase", domain=domain, phase_id=phase_id))
            db = self._get_db(domain)
            phase = db.get_phase_by_id(phase_id)
            if not phase:
                raise HTTPException(status_code=404, detail="Phase not found")
            self.dpm_manager.set_last_phase(domain, phase)
            project = db.get_project_by_id(phase.project_id)
            available_tasks = db.get_tasks()

            context = {
                "request": request,
                "domain": domain,
                "project": project,
                "phase": phase,
                "available_tasks": available_tasks,
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
        ) -> Response:
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
            db = self._get_db(domain)

            phase = db.get_phase_by_id(phase_id)
            if not phase:
                raise HTTPException(status_code=404, detail="Phase not found")
            self.dpm_manager.set_last_phase(domain, phase)

            # Parse blocker IDs from form data
            form_data = await request.form()
            blocker_ids = [int(bid) for bid in form_data.getlist("blocker_ids") if bid] # type: ignore

            try:
                task = db.add_task(
                    name=name,
                    status=status,
                    description=description if description else None,
                    project_id=phase.project_id,
                    phase_id=phase_id
                )

                # Add blockers
                for bid in blocker_ids:
                    blocker_task = db.get_task_by_id(bid)
                    if blocker_task:
                        task.add_blocker(blocker_task)

                self.dpm_manager.set_last_task(domain, task)
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

        @router.get("/{domain}/project/{project_id}/phases-options", response_class=HTMLResponse, name="pm:project-phases-options")
        async def pm_project_phases_options(request: Request, domain: str, project_id: int, selected_phase_id: int | None = None) -> HTMLResponse:
            """HTMX endpoint to get phase options for a project dropdown."""
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
            self.dpm_manager.set_last_domain(domain)
            db = self._get_db(domain)
            project = db.get_project_by_id(project_id)
            if not project:
                return HTMLResponse('<option value="">None (directly under project)</option>')

            phases = project.get_phases()
            options = ['<option value="">None (directly under project)</option>']
            for phase in phases:
                selected = 'selected' if selected_phase_id and phase.phase_id == selected_phase_id else ''
                options.append(f'<option value="{phase.phase_id}" {selected}>{phase.name}</option>')
            return HTMLResponse('\n'.join(options))

        @router.get("/{domain}/task/{task_id}/edit", response_class=HTMLResponse, name="pm:task-edit")
        async def pm_task_edit(request: Request, domain: str, task_id: int) -> Response:
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
                return RedirectResponse(url=request.url_for("pm:task-edit", domain=domain, task_id=task_id))
            db = self._get_db(domain)
            task = db.get_task_by_id(task_id)
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")
            self.dpm_manager.set_last_task(domain, task)

            projects = db.get_projects()
            current_project = db.get_project_by_id(task.project_id)
            phases = current_project.get_phases() if current_project else []
            all_tasks = db.get_tasks()
            # Filter out the current task from available blockers
            available_tasks = [t for t in all_tasks if t.task_id != task_id]
            current_blockers = task.get_blockers(only_not_done=False)
            current_blocker_ids = [b.task_id for b in current_blockers]

            context = {
                "request": request,
                "domain": domain,
                "task": task,
                "projects": projects,
                "phases": phases,
                "available_tasks": available_tasks,
                "current_blocker_ids": current_blocker_ids,
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
        ) -> Response:
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
            db = self._get_db(domain)

            task = db.get_task_by_id(task_id)
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")
            self.dpm_manager.set_last_task(domain, task)

            project_id_int = int(project_id)
            phase_id_int = int(phase_id) if phase_id else None

            # Validate phase belongs to the selected project
            if phase_id_int:
                phase = db.get_phase_by_id(phase_id_int)
                if not phase or phase.project_id != project_id_int:
                    # Phase doesn't belong to the selected project, clear it
                    phase_id_int = None

            # Parse blocker IDs from form data (multi-select checkboxes)
            form_data = await request.form()
            new_blocker_ids = set(int(bid) for bid in form_data.getlist("blocker_ids") if bid)

            try:
                task.name = name
                task.status = status
                task.description = description if description else None
                task.project_id = project_id_int
                task.phase_id = phase_id_int
                task.save()

                # Update blockers - get current blockers and compute diff
                current_blockers = task.get_blockers(only_not_done=False)
                current_blocker_ids = set(b.task_id for b in current_blockers)

                # Add new blockers
                for bid in new_blocker_ids - current_blocker_ids:
                    blocker_task = db.get_task_by_id(bid)
                    if blocker_task:
                        task.add_blocker(blocker_task)

                # Remove old blockers
                for bid in current_blocker_ids - new_blocker_ids:
                    blocker_task = db.get_task_by_id(bid)
                    if blocker_task:
                        task.delete_blocker(blocker_task)

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
        async def pm_task_delete(request: Request, domain: str, task_id: int) -> Response:
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
                return RedirectResponse(url=request.url_for("pm:task-delete", domain=domain, task_id=task_id))
            db = self._get_db(domain)
            task = db.get_task_by_id(task_id)
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")
            self.dpm_manager.set_last_task(domain, task)

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
        async def pm_task_delete_submit(request: Request, domain: str, task_id: int) -> Response:
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
            self.dpm_manager.set_last_domain(domain)
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
        async def pm_project_detail(request: Request, domain: str, project_id: int) -> Response:
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
                return RedirectResponse(url=request.url_for("pm:phase-tasks", domain=domain,
                                                            project_id=project_id))
            db = self._get_db(domain)
            project = db.get_project_by_id(project_id)
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
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
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
                return RedirectResponse(url=request.url_for("pm:phase-tasks", domain=domain,
                                                            phase_id=phase_id))
            db = self._get_db(domain)
            phase = db.get_phase_by_id(phase_id)
            if not phase:
                raise HTTPException(status_code=404, detail="Phase not found")
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
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
                return RedirectResponse(url=request.url_for("pm:task-detail", domain=domain,
                                                            task_id=task_id))
            db = self._get_db(domain)
            task = db.get_task_by_id(task_id)
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")
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

        # ====================================================================
        # Kanban Board Routes
        # ====================================================================

        @router.get("/board", response_class=HTMLResponse, name="pm:kanban-board-auto")
        async def pm_kanban_board_auto(request: Request) -> Response:
            project = self.dpm_manager.get_last_project()
            phase = self.dpm_manager.get_last_phase()
            last_domain = self.dpm_manager.get_last_domain()

            if project is None and phase is None:
                domain = last_domain if last_domain else self.dpm_manager.get_default_domain()
                return RedirectResponse(url=request.url_for("pm:kanban-board", domain=domain))

            if phase is not None:
                base_url = request.url_for("pm:kanban-board", domain=last_domain)
                return RedirectResponse(url=f"{base_url}?project_id={phase.project_id}&phase_id={phase.phase_id}")

            base_url = request.url_for("pm:kanban-board", domain=last_domain)
            return RedirectResponse(url=f"{base_url}?project_id={project.project_id}")

        @router.get("/{domain}/board", response_class=HTMLResponse, name="pm:kanban-board")
        async def pm_kanban_board(request: Request, domain: str,
                                   project_id: int | None = None,
                                   phase_id: int | None = None) -> Response:
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
                return RedirectResponse(url=request.url_for("pm:kanban-board", domain=domain))

            db = self._get_db(domain)
            projects = db.get_projects()
            selected_project = db.get_project_by_id(project_id) if project_id else None
            selected_phase = db.get_phase_by_id(phase_id) if phase_id else None

            if selected_phase:
                self.dpm_manager.set_last_phase(domain, selected_phase)
            elif selected_project:
                self.dpm_manager.set_last_project(domain, selected_project)
            else:
                self.dpm_manager.set_last_domain(domain)

            context = {
                "request": request,
                "domain": domain,
                "projects": projects,
                "selected_project": selected_project,
                "selected_phase": selected_phase,
            }
            is_htmx = request.headers.get("HX-Request") == "true"
            if is_htmx:
                return self.templates.TemplateResponse(
                    "pm_kanban_board.html",
                    context,
                    block_name="sb_main_content"
                )
            else:
                return self.templates.TemplateResponse(
                    "pm_kanban_board.html",
                    context
                )

        @router.get("/{domain}/board/columns", response_class=HTMLResponse, name="pm:kanban-columns")
        async def pm_kanban_columns(request: Request, domain: str,
                                     project_id: int | None = None,
                                     phase_id: int | None = None) -> Response:
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
            self.dpm_manager.set_last_domain(domain)
            db = self._get_db(domain)

            # Get tasks based on filters
            if phase_id:
                phase = db.get_phase_by_id(phase_id)
                all_tasks = phase.get_tasks() if phase else []
            elif project_id:
                project = db.get_project_by_id(project_id)
                all_tasks = project.get_tasks() if project else []
            else:
                all_tasks = db.get_tasks()

            # Enrich tasks with project/phase names and blockers
            def enrich_task(task: TaskRecord) -> TaskRecord:
                project = db.get_project_by_id(task.project_id)
                phase = db.get_phase_by_id(task.phase_id) if task.phase_id else None
                blockers = task.get_blockers(only_not_done=True)

                task.project_name = project.name if project else None # type: ignore
                task.phase_name = phase.name if phase else None # type: ignore
                task.blockers = blockers # type: ignore
                # JSON for client-side validation
                task.blockers_json = json.dumps([{"id": b.task_id, "name": b.name} for b in blockers]) # type: ignore
                return task

            enriched_tasks = [enrich_task(t) for t in all_tasks]

            # Split into columns
            # ToDo column includes ToDo and Blocked tasks
            todo_tasks = [t for t in enriched_tasks if t.status in ('ToDo', 'Blocked')]
            doing_tasks = [t for t in enriched_tasks if t.status == 'InProgress']
            done_tasks = [t for t in enriched_tasks if t.status == 'Done']

            context = {
                "request": request,
                "domain": domain,
                "todo_tasks": todo_tasks,
                "doing_tasks": doing_tasks,
                "done_tasks": done_tasks,
            }
            return self.templates.TemplateResponse("pm_kanban_columns.html", context)

        @router.get("/{domain}/board/phase-options", response_class=HTMLResponse, name="pm:kanban-phase-options")
        async def pm_kanban_phase_options(request: Request, domain: str, project_id: int) -> HTMLResponse:
            """HTMX endpoint to get phase options for the kanban filter dropdown."""
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
            self.dpm_manager.set_last_domain(domain)
            db = self._get_db(domain)
            project = db.get_project_by_id(project_id)
            if not project:
                return HTMLResponse('<li><span class="text-base-content/50 px-4 py-2 text-sm">No phases found</span></li>')

            phases = project.get_phases()
            if not phases:
                return HTMLResponse('<li><span class="text-base-content/50 px-4 py-2 text-sm">No phases in this project</span></li>')

            options = [f'''<li><a href="#" onclick="event.preventDefault(); document.activeElement.blur(); setPhaseFilter(null, 'All Phases');">All Phases</a></li>''']
            for phase in phases:
                html_name = html.escape(phase.name)
                options.append(f'''<li><a href="#" data-phase-id="{phase.phase_id}" data-phase-name="{html_name}" onclick="event.preventDefault(); document.activeElement.blur(); setPhaseFilter(parseInt(this.dataset.phaseId), this.dataset.phaseName);">{html_name}</a></li>''')
            return HTMLResponse('\n'.join(options))

        @router.post("/{domain}/board/move-task", response_class=HTMLResponse, name="pm:kanban-move-task")
        async def pm_kanban_move_task(request: Request, domain: str,
                                       task_id: int = Form(...),
                                       new_status: str = Form(...)) -> Response:
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
            db = self._get_db(domain)
            task = db.get_task_by_id(task_id)

            if not task:
                self.dpm_manager.set_last_domain(domain)
                context = {
                    "request": request,
                    "success": False,
                    "message": "Task not found"
                }
                return self.templates.TemplateResponse("pm_kanban_message.html", context)
            self.dpm_manager.set_last_task(domain, task)

            # Server-side blocker validation
            if new_status in ('InProgress', 'Done'):
                blockers = task.get_blockers(only_not_done=True)
                if blockers:
                    blocker_names = ', '.join(b.name for b in blockers)
                    context = {
                        "request": request,
                        "success": False,
                        "message": f"Cannot move: blocked by {blocker_names}"
                    }
                    return self.templates.TemplateResponse("pm_kanban_message.html", context)

            try:
                task.status = new_status
                task.save()

                context = {
                    "request": request,
                    "success": True,
                    "message": "Task moved successfully"
                }
                response = self.templates.TemplateResponse("pm_kanban_message.html", context)
                response.headers["HX-Trigger"] = "refresh-board"
                return response
            except Exception as e:
                logger.exception("Failed to move task")
                context = {
                    "request": request,
                    "success": False,
                    "message": f"Failed to move task: {str(e)}"
                }
                return self.templates.TemplateResponse("pm_kanban_message.html", context)

        @router.get("/{domain}/task/{task_id}/edit-modal", response_class=HTMLResponse, name="pm:task-edit-modal")
        async def pm_task_edit_modal(request: Request, domain: str, task_id: int) -> Response:
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
            db = self._get_db(domain)
            task = db.get_task_by_id(task_id)
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")
            self.dpm_manager.set_last_task(domain, task)

            projects = db.get_projects()
            current_project = db.get_project_by_id(task.project_id)
            phases = current_project.get_phases() if current_project else []
            all_tasks = db.get_tasks()
            available_tasks = [t for t in all_tasks if t.task_id != task_id]
            current_blockers = task.get_blockers(only_not_done=False)
            current_blocker_ids = [b.task_id for b in current_blockers]

            context = {
                "request": request,
                "domain": domain,
                "task": task,
                "projects": projects,
                "phases": phases,
                "available_tasks": available_tasks,
                "current_blocker_ids": current_blocker_ids,
            }
            return self.templates.TemplateResponse("pm_task_edit_modal.html", context)

        @router.post("/{domain}/task/{task_id}/edit-modal", response_class=HTMLResponse, name="pm:task-edit-modal-submit")
        async def pm_task_edit_modal_submit(
            request: Request,
            domain: str,
            task_id: int,
            name: str = Form(...),
            status: str = Form(...),
            description: str = Form(""),
            project_id: str = Form(...),
            phase_id: str = Form("")
        ) -> Response:
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
            db = self._get_db(domain)

            task = db.get_task_by_id(task_id)
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")
            self.dpm_manager.set_last_task(domain, task)

            project_id_int = int(project_id)
            phase_id_int = int(phase_id) if phase_id else None

            # Validate phase belongs to selected project
            if phase_id_int:
                phase = db.get_phase_by_id(phase_id_int)
                if not phase or phase.project_id != project_id_int:
                    phase_id_int = None

            # Parse blocker IDs
            form_data = await request.form()
            new_blocker_ids = set(int(bid) for bid in form_data.getlist("blocker_ids") if bid) # type: ignore

            try:
                task.name = name
                task.status = status
                task.description = description if description else None
                task.project_id = project_id_int
                task.phase_id = phase_id_int
                task.save()

                # Update blockers
                current_blockers = task.get_blockers(only_not_done=False)
                current_blocker_ids = set(b.task_id for b in current_blockers)

                for bid in new_blocker_ids - current_blocker_ids:
                    blocker_task = db.get_task_by_id(bid)
                    if blocker_task:
                        task.add_blocker(blocker_task)

                for bid in current_blocker_ids - new_blocker_ids:
                    blocker_task = db.get_task_by_id(bid)
                    if blocker_task:
                        task.delete_blocker(blocker_task)

                # Return empty response with triggers to refresh board and close modal
                response = HTMLResponse("")
                response.headers["HX-Trigger"] = '{"refresh-board": true, "close-modal": true}'
                return response
            except Exception as e:
                logger.exception("Failed to update task")
                context = {
                    "request": request,
                    "success": False,
                    "message": f"Failed to update task: {str(e)}"
                }
                return self.templates.TemplateResponse("pm_kanban_message.html", context)

        @router.post("/{domain}/task/{task_id}/delete-board", response_class=HTMLResponse, name="pm:task-delete-board")
        async def pm_task_delete_board(request: Request, domain: str, task_id: int) -> Response:
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
            self.dpm_manager.set_last_domain(domain)
            db = self._get_db(domain)

            task = db.get_task_by_id(task_id)
            if not task:
                context = {
                    "request": request,
                    "success": False,
                    "message": "Task not found"
                }
                return self.templates.TemplateResponse("pm_kanban_message.html", context)

            task_name = task.name

            try:
                task.delete_from_db()
                context = {
                    "request": request,
                    "success": True,
                    "message": f"Task '{task_name}' deleted"
                }
                response = self.templates.TemplateResponse("pm_kanban_message.html", context)
                response.headers["HX-Trigger"] = "refresh-board"
                return response
            except Exception as e:
                logger.exception("Failed to delete task")
                context = {
                    "request": request,
                    "success": False,
                    "message": f"Failed to delete task: {str(e)}"
                }
                return self.templates.TemplateResponse("pm_kanban_message.html", context)

        # This route must be last since /{domain} is a catch-all pattern
        @router.get("/{domain}", response_class=HTMLResponse, name="pm:domain")
        async def pm_domain(request: Request, domain: str) -> Response:
            if domain in ('favicon.ico', 'robots.txt'):
                raise HTTPException(status_code=404)
            if domain == 'default':
                domain = self.dpm_manager.get_default_domain()
                return RedirectResponse(url=request.url_for("pm:domain", domain=domain))
            try:
                self.dpm_manager.set_last_domain(domain)
            except Exception as e:
                raise HTTPException(status_code=404, detail=f"Domain '{domain}' not found")

            # Get domain info
            all_domains = self.dpm_manager.get_domains()
            domain_info = all_domains.get(domain)
            if not domain_info:
                raise HTTPException(status_code=404, detail=f"Domain '{domain}' not found")

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
