from pathlib import Path
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


class TAPFocusResponse(BaseModel):
    task_id: Optional[int] = None
    uuid: str

class TAPAPIService:

    def __init__(self, server, prefix_tag="tap_api"):
        self.server = server
        self.prefix_tag = prefix_tag
        self.domain_catalog = server.domain_catalog
        self._router = APIRouter(tags=[prefix_tag])

    def become_router(self) -> APIRouter:
        """Return a router with all routes bound to this instance."""
        self._router.add_api_route("/tap_focus/set_task", self.set_tap_task, methods=["GET"], response_model=TAPFocusResponse)
        self._router.add_api_route("/tap_focus", self.get_tap_focus, methods=["GET"], response_model=TAPFocusResponse)
        return self._router

    async def get_tap_focus(self):
        from vboss.fastapi.server import TAPFocus
        if self.server.tap_focus is None:
            domain = next(iter(self.domain_catalog.pmdb_domains))
            db = self.domain_catalog.pmdb_domains[domain].db
            f_dict = dict(domain=domain, url_name="pm:", task_id=1)
            focus = self.server.tap_focus = TAPFocus(state=f_dict)
        else:
            focus = self.server.tap_focus
            db = self.domain_catalog.pmdb_domains[focus.state['domain']].db
        return TAPFocusResponse(task_id=self.server.tap_focus.state['task_id'],
                                uuid=self.server.tap_focus.focus_id)

    async def set_tap_task(self, task_id:int):
        from vboss.fastapi.server import TAPFocus
        if self.server.tap_focus is None:
            db = self.domain_catalog.pmdb_domains[domain].db
            f_dict = dict(domain=domain, url_name="pm:", task_id=task_id)
            focus = self.server.tap_focus = TAPFocus(state=f_dict)
        else:
            focus = self.server.tap_focus
            focus.state['task_id'] = task_id
            db = self.domain_catalog.pmdb_domains[focus.state['domain']].db
        return TAPFocusResponse(task_id=self.server.tap_focus.state['task_id'],
                                uuid=self.server.tap_focus.focus_id)

