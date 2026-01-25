from pathlib import Path
from dataclasses import dataclass, field
import os
import uuid
import time
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI

from jinja2_fragments.fastapi import Jinja2Blocks
from jinja2 import Environment, ChoiceLoader, FileSystemLoader  # For multiple directories
from jinja2 import Environment, FileSystemLoader, select_autoescape

from dpm.store.models import ModelDB, DomainCatalog
from dpm.fastapi.dpm.api_router import PMDBAPIService
from dpm.fastapi.dpm.ui_router import PMDBUIRouter
from dpm.fastapi.shared.ui_router import UIRouter

app_root = Path(__file__).parent.resolve()
template_paths = {
    'shared': str(app_root / "shared" / "templates"),
    'dpm': str(app_root / "dpm"/ "templates")
}

class DPMManager:

    def __init__(self, config_path: str):
        self.domain_catalog = DomainCatalog.from_json_config(config_path)

    def get_db_for_domain(self, domain):
        return self.domain_catalog.pmdb_domains[domain].db
        
    def get_default_domain(self):
        domain = next(iter(self.domain_catalog.pmdb_domains))
        return domain
        
    async def shutdown(self):
        for rec in self.domain_catalog.pmdb_domains.values():
            rec.db.close()

    def get_domains(self):
        return self.domain_catalog.pmdb_domains

class DPMServer:

    def __init__(self, config_path: os.PathLike):
        self.dpm_manager = DPMManager(config_path)

        # Set up Jinja2 templates
        env = Environment(
            loader=ChoiceLoader([
                FileSystemLoader(template_paths['shared']),  # Shared base.html, etc.
                FileSystemLoader(template_paths['dpm']),  # Shared base.html, etc.
            ]),
            autoescape=select_autoescape("html", "jinja2"),
            # Optional: add other env settings like trim_blocks=True, lstrip_blocks=True
        )
        #self.templates = Jinja2Templates(env=env)
        self.templates = Jinja2Blocks(env=env)
        self.pmdb_service = PMDBAPIService(self, self.dpm_manager)
        self.pmui_router = PMDBUIRouter(self, self.dpm_manager)
        self.main_router = UIRouter(self, self.dpm_manager)
        self.title = "DPM"
        self.description = "Task management "
        self.api_version =  "0.1.0"
        self.app = FastAPI(title=self.title,
                           description=self.description,
                           version=self.api_version,
                           lifespan=self.lifespan)
        self.app.include_router(self.main_router.become_router())
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
