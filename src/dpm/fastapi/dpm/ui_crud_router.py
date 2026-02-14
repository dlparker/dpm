from __future__ import annotations

import logging
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, Response

from dpm.fastapi.ops import ServerOps
from dpm.store.wrappers import ModelDB
from dpm.store.domains import DPMManager

logger = logging.getLogger("UICrudRouter")


class PMDBCrudRouter:
    """Router for CRUD operations on projects, phases, and tasks."""

    def __init__(self, server: ServerOps, dpm_manager: DPMManager) -> None:
        self.server = server
        self.dpm_manager = dpm_manager
        self.templates = server.templates

    def _get_db(self, domain: str) -> ModelDB:
        return self.dpm_manager.get_db_for_domain(domain)

    def become_router(self) -> APIRouter:
        router = APIRouter()

        # ====================================================================
        # CRUD Routes — Project management (must be before /{project_id} routes)
        # ====================================================================

        @router.get("/{domain}/project/new", response_class=HTMLResponse, name="pm:project-create")
        async def pm_project_create(request: Request, domain: str, parent_id: int | None = None) -> Response:
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
            self.dpm_manager.set_last_domain(domain)
            db = self._get_db(domain)

            project = db.get_project_by_id(project_id)
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")

            project_name = project.name
            project.delete_from_db()

            context = {
                "request": request,
                "success": True,
                "message": f"Project '{project_name}' deleted successfully!",
                "redirect_url": request.url_for("pm:domain-projects", domain=domain)
            }
            return self.templates.TemplateResponse("pm_form_result.html", context)

        # ====================================================================
        # CRUD Routes — Phase management
        # ====================================================================

        @router.get("/{domain}/project/{project_id}/phase/new", response_class=HTMLResponse, name="pm:phase-create")
        async def pm_phase_create(request: Request, domain: str, project_id: int) -> Response:
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
            db = self._get_db(domain)

            phase = db.get_phase_by_id(phase_id)
            if not phase:
                raise HTTPException(status_code=404, detail="Phase not found")
            self.dpm_manager.set_last_phase(domain, phase)

            project_id_int = int(project_id)

            try:
                if phase.project_id != project_id_int:
                    db.move_phase_and_tasks_to_project(phase.phase_id, project_id_int)
                    phase.project_id = project_id_int
                phase.name = name
                phase.description = description if description else None
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
            self.dpm_manager.set_last_domain(domain)
            db = self._get_db(domain)

            phase = db.get_phase_by_id(phase_id)
            if not phase:
                raise HTTPException(status_code=404, detail="Phase not found")

            phase_name = phase.name
            project_id = phase.project_id
            phase.delete_from_db()

            context = {
                "request": request,
                "success": True,
                "message": f"Phase '{phase_name}' deleted successfully!",
                "redirect_url": request.url_for("pm:project", domain=domain, project_id=project_id)
            }
            return self.templates.TemplateResponse("pm_form_result.html", context)

        @router.get("/{domain}/phase/{phase_id}/edit-modal", response_class=HTMLResponse, name="pm:phase-edit-modal")
        async def pm_phase_edit_modal(request: Request, domain: str, phase_id: int) -> Response:
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
            db = self._get_db(domain)

            phase = db.get_phase_by_id(phase_id)
            if not phase:
                raise HTTPException(status_code=404, detail="Phase not found")
            self.dpm_manager.set_last_phase(domain, phase)

            project_id_int = int(project_id)

            try:
                if phase.project_id != project_id_int:
                    db.move_phase_and_tasks_to_project(phase.phase_id, project_id_int)
                    phase.project_id = project_id_int
                phase.name = name
                phase.description = description if description else None
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
            self.dpm_manager.set_last_domain(domain)
            db = self._get_db(domain)

            task = db.get_task_by_id(task_id)
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")

            task_name = task.name
            project_id = task.project_id
            phase_id = task.phase_id
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
            return self.templates.TemplateResponse("pm_form_result.html", context)

        return router
