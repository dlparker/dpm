from __future__ import annotations

import html
import json
import logging
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, Response

from dpm.fastapi.ops import ServerOps
from dpm.store.domains import DPMManager
from dpm.store.sw_wrappers import SWModelDB

logger = logging.getLogger("SWKanbanRouter")


class SWKanbanRouter:
    """Router for SW kanban board views and task operations."""

    def __init__(self, server: ServerOps, dpm_manager: DPMManager) -> None:
        self.server = server
        self.dpm_manager = dpm_manager
        self.templates = server.templates

    def _get_sw_db(self, domain: str) -> SWModelDB:
        return self.dpm_manager.get_db_for_domain(domain).sw_model_db

    def become_router(self) -> APIRouter:
        router = APIRouter(prefix="/sw")

        @router.get("/{domain}/board", response_class=HTMLResponse, name="sw:board")
        async def sw_board(request: Request, domain: str,
                           epic_id: int | None = None,
                           story_id: int | None = None) -> Response:
            sw = self._get_sw_db(domain)
            epics = sw.get_epics()
            selected_epic = sw.get_epic_by_id(epic_id) if epic_id else None
            selected_story = sw.get_story_by_id(story_id) if story_id else None

            context = {
                "request": request,
                "domain": domain,
                "epics": epics,
                "selected_epic": selected_epic,
                "selected_story": selected_story,
            }
            is_htmx = request.headers.get("HX-Request") == "true"
            if is_htmx:
                return self.templates.TemplateResponse(
                    "sw_kanban_board.html", context, block_name="sb_main_content"
                )
            return self.templates.TemplateResponse("sw_kanban_board.html", context)

        @router.get("/{domain}/board/columns", response_class=HTMLResponse, name="sw:board-columns")
        async def sw_board_columns(request: Request, domain: str,
                                   epic_id: int | None = None,
                                   story_id: int | None = None) -> Response:
            sw = self._get_sw_db(domain)

            # Get tasks based on filters
            if story_id:
                story = sw.get_story_by_id(story_id)
                all_tasks = sw.get_swtasks(story=story) if story else []
            elif epic_id:
                epic = sw.get_epic_by_id(epic_id)
                all_tasks = sw.get_swtasks(epic=epic) if epic else []
            else:
                all_tasks = sw.get_swtasks()

            # Enrich tasks with story name and blockers
            for task in all_tasks:
                story_rec = sw.get_story_for_phase(task.phase_id) if task.phase_id else None
                task.story_name = story_rec.name if story_rec else None  # type: ignore
                blockers = task.get_blockers(only_not_done=True)
                task.blockers = blockers  # type: ignore
                task.blockers_json = json.dumps([{"id": b.task_id, "name": b.name} for b in blockers])  # type: ignore

            # Split into columns — handle "Todo" from sw_wrappers.add_task
            todo_tasks = [t for t in all_tasks if t.status in ('ToDo', 'Todo', 'Blocked')]
            doing_tasks = [t for t in all_tasks if t.status == 'Doing']
            done_tasks = [t for t in all_tasks if t.status == 'Done']

            context = {
                "request": request,
                "domain": domain,
                "todo_tasks": todo_tasks,
                "doing_tasks": doing_tasks,
                "done_tasks": done_tasks,
            }
            return self.templates.TemplateResponse("sw_kanban_columns.html", context)

        @router.get("/{domain}/board/story-options", response_class=HTMLResponse, name="sw:board-story-options")
        async def sw_board_story_options(request: Request, domain: str, epic_id: int) -> HTMLResponse:
            sw = self._get_sw_db(domain)
            epic = sw.get_epic_by_id(epic_id)
            if not epic:
                return HTMLResponse('<li><span class="text-base-content/50 px-4 py-2 text-sm">No stories found</span></li>')

            stories = sw.get_stories(epic=epic)
            if not stories:
                return HTMLResponse('<li><span class="text-base-content/50 px-4 py-2 text-sm">No stories in this epic</span></li>')

            options = ['''<li><a href="#" onclick="event.preventDefault(); document.activeElement.blur(); setStoryFilter(null, 'All Stories');">All Stories</a></li>''']
            for story in stories:
                html_name = html.escape(story.name)
                options.append(f'''<li><a href="#" data-story-id="{story.story_id}" data-story-name="{html_name}" onclick="event.preventDefault(); document.activeElement.blur(); setStoryFilter(parseInt(this.dataset.storyId), this.dataset.storyName);">{html_name}</a></li>''')
            return HTMLResponse('\n'.join(options))

        @router.post("/{domain}/board/move-task", response_class=HTMLResponse, name="sw:board-move-task")
        async def sw_board_move_task(request: Request, domain: str,
                                     task_id: int = Form(...),
                                     new_status: str = Form(...)) -> Response:
            sw = self._get_sw_db(domain)
            task = sw.get_swtask_by_id(task_id)

            if not task:
                context = {
                    "request": request,
                    "success": False,
                    "message": "Task not found",
                }
                return self.templates.TemplateResponse("pm_kanban_message.html", context)

            # Server-side blocker validation
            if new_status in ('Doing', 'Done'):
                blockers = task.get_blockers(only_not_done=True)
                if blockers:
                    blocker_names = ', '.join(b.name for b in blockers)
                    context = {
                        "request": request,
                        "success": False,
                        "message": f"Cannot move: blocked by {blocker_names}",
                    }
                    return self.templates.TemplateResponse("pm_kanban_message.html", context)

            task.status = new_status
            task.save()

            context = {
                "request": request,
                "success": True,
                "message": "Task moved successfully",
            }
            response = self.templates.TemplateResponse("pm_kanban_message.html", context)
            response.headers["HX-Trigger"] = "refresh-board"
            return response

        @router.post("/{domain}/board/delete-task", response_class=HTMLResponse, name="sw:board-delete-task")
        async def sw_board_delete_task(request: Request, domain: str,
                                       task_id: int = Form(...)) -> Response:
            sw = self._get_sw_db(domain)
            task = sw.get_swtask_by_id(task_id)

            if not task:
                context = {
                    "request": request,
                    "success": False,
                    "message": "Task not found",
                }
                return self.templates.TemplateResponse("pm_kanban_message.html", context)

            task_name = task.name
            task.delete_from_db()

            context = {
                "request": request,
                "success": True,
                "message": f"Task '{task_name}' deleted",
            }
            response = self.templates.TemplateResponse("pm_kanban_message.html", context)
            response.headers["HX-Trigger"] = "refresh-board"
            return response

        return router
