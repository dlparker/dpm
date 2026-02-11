from __future__ import annotations

import logging
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response

from dpm.fastapi.ops import ServerOps
from dpm.store.domains import DPMManager

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

    def become_router(self) -> APIRouter:
        router = APIRouter()

        @router.get("/", response_class=HTMLResponse, name="ui:home")
        async def home(request: Request) -> Response:
            last_domain = self.dpm_manager.get_last_domain()
            last_project = self.dpm_manager.get_last_project()
            last_phase = self.dpm_manager.get_last_phase()
            last_task = self.dpm_manager.get_last_task()
            return self.templates.TemplateResponse(
                "home.html",
                {
                    "request": request,
                    "last_domain": last_domain,
                    "last_project": last_project,
                    "last_phase": last_phase,
                    "last_task": last_task,
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
