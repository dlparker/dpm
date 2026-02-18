from __future__ import annotations

import logging
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response

from dpm.fastapi.ops import ServerOps
from dpm.store.domains import DomainMode, DPMManager
from dpm.store.sw_wrappers import (
    VisionRecord, SubsystemRecord, DeliverableRecord, EpicRecord,
)

logger = logging.getLogger("UIRouter")


class UIRouter:

    def __init__(self, server: ServerOps, dpm_manager: DPMManager) -> None:
        self.server = server
        self.dpm_manager = dpm_manager
        self.domain_catalog = dpm_manager.domain_catalog
        self.templates = server.templates

    async def _get_status_data(self) -> dict[str, str]:
        return {
            "status": "running",
        }

    def _build_recent_items(self, request: Request) -> list[dict]:
        """Build recent items list with correct labels and URLs for both PM and SW domains."""
        items: list[dict] = []
        last_domain = self.dpm_manager.get_last_domain()
        if not last_domain:
            return items

        domain_info = self.dpm_manager.get_domains().get(last_domain)
        if not domain_info:
            return items

        items.append({
            "label": "Domain",
            "name": last_domain,
            "url": str(request.url_for("pm:domain", domain=last_domain)),
            "badge_class": "badge-primary",
        })

        is_sw = domain_info.domain_mode == DomainMode.SOFTWARE
        last_project = self.dpm_manager.get_last_project()
        last_phase = self.dpm_manager.get_last_phase()
        last_task = self.dpm_manager.get_last_task()

        if last_project:
            if is_sw:
                sw = domain_info.db.sw_model_db
                wrapped = sw.wrap_project(last_project)
                if isinstance(wrapped, VisionRecord):
                    items.append({"label": "Vision", "name": wrapped.name,
                                  "url": str(request.url_for("sw:vision", domain=last_domain, vision_id=wrapped.vision_id)),
                                  "badge_class": "badge-primary"})
                elif isinstance(wrapped, SubsystemRecord):
                    items.append({"label": "Subsystem", "name": wrapped.name,
                                  "url": str(request.url_for("sw:subsystem", domain=last_domain, subsystem_id=wrapped.subsystem_id)),
                                  "badge_class": "badge-secondary"})
                elif isinstance(wrapped, DeliverableRecord):
                    items.append({"label": "Deliverable", "name": wrapped.name,
                                  "url": str(request.url_for("sw:deliverable", domain=last_domain, deliverable_id=wrapped.deliverable_id)),
                                  "badge_class": "badge-accent"})
                elif isinstance(wrapped, EpicRecord):
                    items.append({"label": "Epic", "name": wrapped.name,
                                  "url": str(request.url_for("sw:epic", domain=last_domain, epic_id=wrapped.epic_id)),
                                  "badge_class": "badge-info"})
                else:
                    items.append({"label": "Project", "name": last_project.name,
                                  "url": str(request.url_for("pm:project", domain=last_domain, project_id=last_project.project_id)),
                                  "badge_class": "badge-secondary"})
            else:
                items.append({"label": "Project", "name": last_project.name,
                              "url": str(request.url_for("pm:project", domain=last_domain, project_id=last_project.project_id)),
                              "badge_class": "badge-secondary"})

        if last_phase and last_phase.phase_id is not None:
            if is_sw:
                sw = domain_info.db.sw_model_db
                story = sw.get_story_for_phase(last_phase.phase_id)
                if story:
                    items.append({"label": "Story", "name": story.name,
                                  "url": str(request.url_for("sw:story", domain=last_domain, story_id=story.story_id)),
                                  "badge_class": "badge-warning"})
                else:
                    items.append({"label": "Phase", "name": last_phase.name,
                                  "url": str(request.url_for("pm:phase", domain=last_domain, phase_id=last_phase.phase_id)),
                                  "badge_class": "badge-warning"})
            else:
                items.append({"label": "Phase", "name": last_phase.name,
                              "url": str(request.url_for("pm:phase", domain=last_domain, phase_id=last_phase.phase_id)),
                              "badge_class": "badge-warning"})

        if last_task and last_task.task_id is not None:
            if is_sw:
                sw = domain_info.db.sw_model_db
                swtask = sw.get_swtask_for_task(last_task.task_id)
                if swtask:
                    items.append({"label": "Task", "name": swtask.name,
                                  "url": str(request.url_for("sw:task", domain=last_domain, swtask_id=swtask.swtask_id)),
                                  "badge_class": "badge-accent"})
                else:
                    items.append({"label": "Task", "name": last_task.name,
                                  "url": str(request.url_for("pm:task-detail", domain=last_domain, task_id=last_task.task_id)),
                                  "badge_class": "badge-accent"})
            else:
                items.append({"label": "Task", "name": last_task.name,
                              "url": str(request.url_for("pm:task-detail", domain=last_domain, task_id=last_task.task_id)),
                              "badge_class": "badge-accent"})

        return items

    def become_router(self) -> APIRouter:
        router = APIRouter()

        @router.get("/", response_class=HTMLResponse, name="ui:home")
        async def home(request: Request) -> Response:
            recent_items = self._build_recent_items(request)
            return self.templates.TemplateResponse(
                "home.html",
                {
                    "request": request,
                    "recent_items": recent_items,
                }
            )

        @router.get("/status-partial", response_class=HTMLResponse, name="ui:status-partial")
        async def status_partial(request: Request) -> Response:
            status_data = await self._get_status_data()
            return self.templates.TemplateResponse(
                "status_partial.html",
                {"request": request, "status": status_data}
            )

        return router
