from pathlib import Path
from dataclasses import dataclass, field
import uuid
import time
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI

from jinja2_fragments.fastapi import Jinja2Blocks
from jinja2 import Environment, ChoiceLoader, FileSystemLoader  # For multiple directories
from jinja2 import Environment, FileSystemLoader, select_autoescape

from vboss.store.models import ModelDB, DomainCatalog
from vboss.fastapi.cantons.pm.api_router import PMDBAPIService
from vboss.fastapi.cantons.pm.ui_router import PMUIRouter
from vboss.fastapi.shared.api_router import TAPAPIService
from vboss.fastapi.shared.ui_router import UIRouter

@dataclass
class TAPFocus:
    state: dict = field(default_factory=dict)
    focus_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    create_time: float = field(default_factory=time.time)

class VBossServer:

    def __init__(self, config_path: str):
        self.domain_catalog = DomainCatalog.from_json_config(config_path)
        # Set up Jinja2 templates
        app_root = Path(__file__).parent.resolve()

        env = Environment(
            loader=ChoiceLoader([
                FileSystemLoader(str(app_root / "shared" / "templates")),  # Shared base.html, etc.
                FileSystemLoader(str(app_root / "cantons" / "pm"/ "templates")),  # Shared base.html, etc.
            ]),
            autoescape=select_autoescape("html", "jinja2"),
            # Optional: add other env settings like trim_blocks=True, lstrip_blocks=True
        )
        #self.templates = Jinja2Templates(env=env)
        self.templates = Jinja2Blocks(env=env)
        self.pmdb_service = PMDBAPIService(self)
        self.pmui_router = PMUIRouter(self)
        self.tap_service = TAPAPIService(self)
        self.ui_router = UIRouter(self)
        self.title = "VBoss API"
        self.description = "Task management REST API"
        self.api_version =  "0.1.0"
        self.app = FastAPI(title=self.title,
                           description=self.description,
                           version=self.api_version,
                           lifespan=self.lifespan)
        self.app.include_router(self.pmdb_service.become_router(), prefix="/pm/api")
        self.app.include_router(self.pmui_router.become_router(), prefix="/pm")
        self.app.include_router(self.tap_service.become_router(), prefix="/tap/api")
        self.app.include_router(self.ui_router.become_router(), prefix="/tap")
        self.tap_focus = None

    def add_router(self, router):
        self.app.include_router(router)

    async def shutdown(self):
        for rec in self.domain_catalog.pmdb_domains.values():
            rec.db.close()
        
    @asynccontextmanager
    async def lifespan(self, app: FastAPI):
        """Application lifespan handler for startup/shutdown."""
        # Startup
        yield
        # Shutdown
        await self.shutdown()
