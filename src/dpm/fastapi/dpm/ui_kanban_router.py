from __future__ import annotations

import html
import json
import logging
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from dpm.fastapi.ops import ServerOps
from dpm.store.wrappers import ModelDB, TaskRecord
from dpm.store.domains import DPMManager

logger = logging.getLogger("UIKanbanRouter")


class PMDBKanbanRouter:
    """Router for kanban board views and task operations."""

    def __init__(self, server: ServerOps, dpm_manager: DPMManager) -> None:
        self.server = server
        self.dpm_manager = dpm_manager
        self.templates = server.templates

    def _get_db(self, domain: str) -> ModelDB:
        return self.dpm_manager.get_db_for_domain(domain)

    def become_router(self) -> APIRouter:
        router = APIRouter()

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

        @router.get("/{domain}/task/{task_id}/edit-modal", response_class=HTMLResponse, name="pm:task-edit-modal")
        async def pm_task_edit_modal(request: Request, domain: str, task_id: int) -> Response:
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
            task.delete_from_db()

            context = {
                "request": request,
                "success": True,
                "message": f"Task '{task_name}' deleted"
            }
            response = self.templates.TemplateResponse("pm_kanban_message.html", context)
            response.headers["HX-Trigger"] = "refresh-board"
            return response

        return router
