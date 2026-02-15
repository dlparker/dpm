from __future__ import annotations

import logging
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, Response

from dpm.fastapi.ops import ServerOps
from dpm.store.domains import DPMManager
from dpm.store.sw_wrappers import SWModelDB

logger = logging.getLogger("SWUIRouter")


class SWUIRouter:
    """Router for Software taxonomy UI views."""

    def __init__(self, server: ServerOps, dpm_manager: DPMManager) -> None:
        self.server = server
        self.dpm_manager = dpm_manager
        self.templates = server.templates

    def _get_sw_db(self, domain: str) -> SWModelDB:
        return self.dpm_manager.get_db_for_domain(domain).sw_model_db

    def _render(self, request: Request, template: str, context: dict) -> Response:
        is_htmx = request.headers.get("HX-Request") == "true"
        if is_htmx:
            return self.templates.TemplateResponse(
                template, context, block_name="sb_main_content"
            )
        return self.templates.TemplateResponse(template, context)

    def become_router(self) -> APIRouter:
        router = APIRouter(prefix="/sw")

        # ====================================================================
        # Detail View Routes
        # ====================================================================

        @router.get("/{domain}", response_class=HTMLResponse, name="sw:domain")
        async def sw_domain(request: Request, domain: str) -> Response:
            sw = self._get_sw_db(domain)
            visions = sw.get_visions()
            all_epics = sw.get_epics()
            # Orphan epics: those whose underlying project has no parent_id
            orphan_epics = [e for e in all_epics if e.parent_id is None]
            context = {
                "request": request,
                "domain": domain,
                "visions": visions,
                "orphan_epics": orphan_epics,
            }
            return self._render(request, "sw_domain.html", context)

        @router.get("/{domain}/vision/{vision_id}", response_class=HTMLResponse, name="sw:vision")
        async def sw_vision(request: Request, domain: str, vision_id: int) -> Response:
            sw = self._get_sw_db(domain)
            vision = sw.get_vision_by_id(vision_id)
            if not vision:
                raise HTTPException(status_code=404, detail="Vision not found")
            subsystems = sw.get_subsystems(vision=vision)
            epics = sw.get_epics(parent=vision)
            context = {
                "request": request,
                "domain": domain,
                "vision": vision,
                "subsystems": subsystems,
                "epics": epics,
            }
            return self._render(request, "sw_vision.html", context)

        @router.get("/{domain}/subsystem/{subsystem_id}", response_class=HTMLResponse, name="sw:subsystem")
        async def sw_subsystem(request: Request, domain: str, subsystem_id: int) -> Response:
            sw = self._get_sw_db(domain)
            subsystem = sw.get_subsystem_by_id(subsystem_id)
            if not subsystem:
                raise HTTPException(status_code=404, detail="Subsystem not found")
            deliverables = sw.get_deliverables(parent=subsystem)
            epics = sw.get_epics(parent=subsystem)
            context = {
                "request": request,
                "domain": domain,
                "subsystem": subsystem,
                "deliverables": deliverables,
                "epics": epics,
            }
            return self._render(request, "sw_subsystem.html", context)

        @router.get("/{domain}/deliverable/{deliverable_id}", response_class=HTMLResponse, name="sw:deliverable")
        async def sw_deliverable(request: Request, domain: str, deliverable_id: int) -> Response:
            sw = self._get_sw_db(domain)
            deliverable = sw.get_deliverable_by_id(deliverable_id)
            if not deliverable:
                raise HTTPException(status_code=404, detail="Deliverable not found")
            epics = sw.get_epics(parent=deliverable)
            context = {
                "request": request,
                "domain": domain,
                "deliverable": deliverable,
                "epics": epics,
            }
            return self._render(request, "sw_deliverable.html", context)

        @router.get("/{domain}/epic/{epic_id}", response_class=HTMLResponse, name="sw:epic")
        async def sw_epic(request: Request, domain: str, epic_id: int) -> Response:
            sw = self._get_sw_db(domain)
            epic = sw.get_epic_by_id(epic_id)
            if not epic:
                raise HTTPException(status_code=404, detail="Epic not found")
            stories = sw.get_stories(epic=epic)
            tasks = sw.get_swtasks(epic=epic)
            # Direct tasks: those not assigned to any story (no phase_id)
            direct_tasks = [t for t in tasks if t.phase_id is None]
            context = {
                "request": request,
                "domain": domain,
                "epic": epic,
                "stories": stories,
                "tasks": direct_tasks,
            }
            return self._render(request, "sw_epic.html", context)

        @router.get("/{domain}/story/{story_id}", response_class=HTMLResponse, name="sw:story")
        async def sw_story(request: Request, domain: str, story_id: int) -> Response:
            sw = self._get_sw_db(domain)
            story = sw.get_story_by_id(story_id)
            if not story:
                raise HTTPException(status_code=404, detail="Story not found")
            tasks = sw.get_swtasks(story=story)
            context = {
                "request": request,
                "domain": domain,
                "story": story,
                "tasks": tasks,
            }
            return self._render(request, "sw_story.html", context)

        @router.get("/{domain}/task/{swtask_id}", response_class=HTMLResponse, name="sw:task")
        async def sw_task(request: Request, domain: str, swtask_id: int) -> Response:
            sw = self._get_sw_db(domain)
            task = sw.get_swtask_by_id(swtask_id)
            if not task:
                raise HTTPException(status_code=404, detail="SWTask not found")
            blockers = task.get_blockers(only_not_done=False)
            blocks = task.blocks_tasks()
            context = {
                "request": request,
                "domain": domain,
                "task": task,
                "blockers": blockers,
                "blocks": blocks,
            }
            return self._render(request, "sw_task.html", context)

        # ====================================================================
        # Sidebar Nav Routes (always return fragment)
        # ====================================================================

        @router.get("/nav/{domain}/tree", response_class=HTMLResponse, name="sw:nav-tree")
        async def sw_nav_tree(request: Request, domain: str) -> Response:
            sw = self._get_sw_db(domain)
            visions = sw.get_visions()
            all_epics = sw.get_epics()
            orphan_epics = [e for e in all_epics if e.parent_id is None]
            context = {
                "request": request,
                "domain": domain,
                "visions": visions,
                "orphan_epics": orphan_epics,
            }
            return self.templates.TemplateResponse(
                "sw_nav_tree.html", context, block_name="sb_main_content"
            )

        @router.get("/nav/{domain}/items", response_class=HTMLResponse, name="sw:nav-domain-items")
        async def sw_nav_domain_items(request: Request, domain: str) -> Response:
            sw = self._get_sw_db(domain)
            visions = sw.get_visions()
            all_epics = sw.get_epics()
            orphan_epics = [e for e in all_epics if e.parent_id is None]
            context = {
                "request": request,
                "domain": domain,
                "visions": visions,
                "orphan_epics": orphan_epics,
            }
            return self.templates.TemplateResponse(
                "sw_nav_domain.html", context, block_name="sb_main_content"
            )

        @router.get("/nav/{domain}/vision/{vision_id}/children", response_class=HTMLResponse, name="sw:nav-vision-children")
        async def sw_nav_vision_children(request: Request, domain: str, vision_id: int) -> Response:
            sw = self._get_sw_db(domain)
            vision = sw.get_vision_by_id(vision_id)
            if not vision:
                raise HTTPException(status_code=404, detail="Vision not found")
            subsystems = sw.get_subsystems(vision=vision)
            epics = sw.get_epics(parent=vision)
            context = {
                "request": request,
                "domain": domain,
                "vision": vision,
                "subsystems": subsystems,
                "epics": epics,
            }
            return self.templates.TemplateResponse(
                "sw_nav_vision_children.html", context, block_name="sb_main_content"
            )

        @router.get("/nav/{domain}/epic/{epic_id}/children", response_class=HTMLResponse, name="sw:nav-epic-children")
        async def sw_nav_epic_children(request: Request, domain: str, epic_id: int) -> Response:
            sw = self._get_sw_db(domain)
            epic = sw.get_epic_by_id(epic_id)
            if not epic:
                raise HTTPException(status_code=404, detail="Epic not found")
            stories = sw.get_stories(epic=epic)
            context = {
                "request": request,
                "domain": domain,
                "epic": epic,
                "stories": stories,
            }
            return self.templates.TemplateResponse(
                "sw_nav_epic_children.html", context, block_name="sb_main_content"
            )

        @router.get("/nav/{domain}/story/{story_id}/tasks", response_class=HTMLResponse, name="sw:nav-story-tasks")
        async def sw_nav_story_tasks(request: Request, domain: str, story_id: int) -> Response:
            sw = self._get_sw_db(domain)
            story = sw.get_story_by_id(story_id)
            if not story:
                raise HTTPException(status_code=404, detail="Story not found")
            tasks = sw.get_swtasks(story=story)
            context = {
                "request": request,
                "domain": domain,
                "story": story,
                "tasks": tasks,
            }
            return self.templates.TemplateResponse(
                "sw_nav_story_tasks.html", context, block_name="sb_main_content"
            )

        return router
