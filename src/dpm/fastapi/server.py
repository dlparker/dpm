from pathlib import Path
from dataclasses import dataclass, field
import os
import uuid
import time
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from jinja2_fragments.fastapi import Jinja2Blocks
from jinja2 import Environment, ChoiceLoader, FileSystemLoader  # For multiple directories
from jinja2 import Environment, FileSystemLoader, select_autoescape

from dpm.store.domains import DPMManager
from dpm.top_error import TopLevelCallback

from dpm.fastapi.ops import ServerOps
from dpm.fastapi.dpm.api_router import PMDBAPIService
from dpm.fastapi.dpm.ui_router import PMDBUIRouter
from dpm.fastapi.dpm.ui_crud_router import PMDBCrudRouter
from dpm.fastapi.dpm.ui_kanban_router import PMDBKanbanRouter
from dpm.fastapi.standalone.ui_router import UIRouter

logger = logging.getLogger("dpm fastapi server")

app_root = Path(__file__).parent.resolve()
template_paths = {
    'standalone': str(app_root / "standalone" / "templates"),
    'dpm': str(app_root / "dpm"/ "templates")
}

class DPMServer(ServerOps):

    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.dpm_manager = DPMManager(config_path)
        self.background_error_dict = None
        self.error_callback = None

        # Set up Jinja2 templates
        env = Environment(
            loader=ChoiceLoader([
                FileSystemLoader(template_paths['standalone']),  # Standalone base.html, etc.
                FileSystemLoader(template_paths['dpm']),
            ]),
            autoescape=select_autoescape("html", "jinja2"),
            # Optional: add other env settings like trim_blocks=True, lstrip_blocks=True
        )
        #self.templates = Jinja2Templates(env=env)
        self.templates = Jinja2Blocks(env=env)
        self.pmdb_service = PMDBAPIService(self, self.dpm_manager)
        self.pmui_router = PMDBUIRouter(self, self.dpm_manager)
        self.pmui_crud_router = PMDBCrudRouter(self, self.dpm_manager)
        self.pmui_kanban_router = PMDBKanbanRouter(self, self.dpm_manager)
        self.main_router = UIRouter(self, self.dpm_manager)
        self.title = "DPM"
        self.description = "Task management "
        self.api_version =  "0.1.0"
        self.app = FastAPI(title=self.title,
                           description=self.description,
                           version=self.api_version,
                           lifespan=self.lifespan)
        self.app.include_router(self.main_router.become_router())
        self.app.include_router(self.pmui_crud_router.become_router())
        self.app.include_router(self.pmui_kanban_router.become_router())
        self.app.include_router(self.pmui_router.become_router())
        self.app.include_router(self.pmdb_service.become_router(), prefix="/api")
        self.tap_focus = None

    async def shutdown(self):
        await self.dpm_manager.shutdown()
        
    @asynccontextmanager
    async def lifespan(self, app: FastAPI):
        """Application lifespan handler for startup/shutdown."""
        # Startup
        yield
        # Shutdown
        await self.shutdown()

    def get_error_callback(self):
        if not self.error_callback:
            self.error_callback = ErrorCallback(self)
        return self.error_callback

            
class ErrorCallback(TopLevelCallback):

    def __init__(self, server):
        self.server = server
        
    async def on_error(self, error_dict: dict):
        self.server.background_error_dict = error_dict
        
