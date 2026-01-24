import logging
from pathlib import Path
from datetime import datetime
import time
import asyncio
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

logger = logging.getLogger("UIRouter")


class UIRouter:

    def __init__(self, server, dpm_manager):
        self.server = server
        self.dpm_manager = dpm_manager
        self.domain_catalog = dpm_manager.domain_catalog
        self.templates = server.templates

    async def _get_status_data(self):
        return {
            "status": "running",
        }

    def become_router(self):
        router = APIRouter()

        @router.get("/", response_class=HTMLResponse, name="ui:home")
        async def home(request: Request):
            return self.templates.TemplateResponse(
                "home.html",
                {"request": request}
            )

        @router.get("/status-partial", response_class=HTMLResponse, name="ui:status-partial")
        async def status_partial(request: Request):
            status_data = await self._get_status_data()
            return self.templates.TemplateResponse(
                "status_partial.html",
                {"request": request, "status": status_data}
            )

        return router
