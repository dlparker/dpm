from __future__ import annotations

import logging
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, Response

from dpm.fastapi.ops import ServerOps
from dpm.store.domains import DPMManager, PMDBDomain
from dpm.store.sw_models import GuardrailType
from dpm.store.sw_wrappers import (
    SWModelDB, VisionRecord, SubsystemRecord, DeliverableRecord,
    EpicRecord, StoryRecord, SWTaskRecord,
)

logger = logging.getLogger("SWUIRouter")


class SWUIRouter:
    """Router for Software taxonomy UI views."""

    def __init__(self, server: ServerOps, dpm_manager: DPMManager) -> None:
        self.server = server
        self.dpm_manager = dpm_manager
        self.templates = server.templates

    def _get_sw_db(self, domain: str) -> SWModelDB:
        return self.dpm_manager.get_db_for_domain(domain).sw_model_db

    def _get_domain(self, domain_name: str) -> PMDBDomain:
        return self.dpm_manager.get_domains()[domain_name]

    @staticmethod
    def _sw_record_crumb(record) -> dict:
        """Return breadcrumb dict for a wrapped SW record."""
        if isinstance(record, VisionRecord):
            return {"type": "Vision", "name": record.name, "route": "sw:vision", "id_param": "vision_id", "id_value": record.vision_id, "badge_class": "badge-primary"}
        if isinstance(record, SubsystemRecord):
            return {"type": "Subsystem", "name": record.name, "route": "sw:subsystem", "id_param": "subsystem_id", "id_value": record.subsystem_id, "badge_class": "badge-secondary"}
        if isinstance(record, DeliverableRecord):
            return {"type": "Deliverable", "name": record.name, "route": "sw:deliverable", "id_param": "deliverable_id", "id_value": record.deliverable_id, "badge_class": "badge-accent"}
        if isinstance(record, EpicRecord):
            return {"type": "Epic", "name": record.name, "route": "sw:epic", "id_param": "epic_id", "id_value": record.epic_id, "badge_class": "badge-info"}
        if isinstance(record, StoryRecord):
            return {"type": "Story", "name": record.name, "route": "sw:story", "id_param": "story_id", "id_value": record.story_id, "badge_class": "badge-warning"}
        # Shouldn't reach here for normal SW types
        return {"type": "Project", "name": record.name, "route": "sw:domain", "id_param": None, "id_value": None, "badge_class": "badge-ghost"}

    def _build_ancestors(self, domain: str, record) -> list[dict]:
        """Build ancestor breadcrumb list from an SW record up to domain root.

        For project-based records (Vision, Subsystem, Deliverable, Epic),
        walks up Project.parent. For Story, starts from its owning project.
        For SWTask, starts from its story (if any) then its project.
        Returns list ordered root-first: [domain, grandparent, parent, ...].
        """
        sw = self._get_sw_db(domain)
        crumbs: list[dict] = []

        def _walk_project_chain(project):
            """Walk up the project parent chain, wrapping each as SW type."""
            chain = []
            while project:
                chain.append(self._sw_record_crumb(sw.wrap_project(project)))
                project = project.parent
            chain.reverse()
            return chain

        if isinstance(record, SWTaskRecord):
            # If task belongs to a story, include the story + its project chain
            if record.phase_id:
                story = sw.get_story_for_phase(record.phase_id)
                if story:
                    crumbs = _walk_project_chain(story.project)
                    crumbs.append(self._sw_record_crumb(story))
                    return crumbs
            # Direct task on a project — walk up from its project
            if record.project:
                return _walk_project_chain(record.project)
            return []

        if isinstance(record, StoryRecord):
            return _walk_project_chain(record.project)

        # Project-based records: walk up parent chain (skip self)
        if record.parent:
            return _walk_project_chain(record.parent)
        return []

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
            ancestors = self._build_ancestors(domain, vision)
            context = {
                "request": request,
                "domain": domain,
                "vision": vision,
                "subsystems": subsystems,
                "epics": epics,
                "ancestors": ancestors,
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
            ancestors = self._build_ancestors(domain, subsystem)
            context = {
                "request": request,
                "domain": domain,
                "subsystem": subsystem,
                "deliverables": deliverables,
                "epics": epics,
                "ancestors": ancestors,
            }
            return self._render(request, "sw_subsystem.html", context)

        @router.get("/{domain}/deliverable/{deliverable_id}", response_class=HTMLResponse, name="sw:deliverable")
        async def sw_deliverable(request: Request, domain: str, deliverable_id: int) -> Response:
            sw = self._get_sw_db(domain)
            deliverable = sw.get_deliverable_by_id(deliverable_id)
            if not deliverable:
                raise HTTPException(status_code=404, detail="Deliverable not found")
            epics = sw.get_epics(parent=deliverable)
            ancestors = self._build_ancestors(domain, deliverable)
            context = {
                "request": request,
                "domain": domain,
                "deliverable": deliverable,
                "epics": epics,
                "ancestors": ancestors,
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
            ancestors = self._build_ancestors(domain, epic)
            context = {
                "request": request,
                "domain": domain,
                "epic": epic,
                "stories": stories,
                "tasks": direct_tasks,
                "ancestors": ancestors,
            }
            return self._render(request, "sw_epic.html", context)

        @router.get("/{domain}/story/{story_id}", response_class=HTMLResponse, name="sw:story")
        async def sw_story(request: Request, domain: str, story_id: int) -> Response:
            sw = self._get_sw_db(domain)
            story = sw.get_story_by_id(story_id)
            if not story:
                raise HTTPException(status_code=404, detail="Story not found")
            tasks = sw.get_swtasks(story=story)
            ancestors = self._build_ancestors(domain, story)
            context = {
                "request": request,
                "domain": domain,
                "story": story,
                "tasks": tasks,
                "ancestors": ancestors,
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
            ancestors = self._build_ancestors(domain, task)
            context = {
                "request": request,
                "domain": domain,
                "task": task,
                "blockers": blockers,
                "blocks": blocks,
                "ancestors": ancestors,
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

        @router.get("/nav/{domain}/subsystem/{subsystem_id}/children", response_class=HTMLResponse, name="sw:nav-subsystem-children")
        async def sw_nav_subsystem_children(request: Request, domain: str, subsystem_id: int) -> Response:
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
            return self.templates.TemplateResponse(
                "sw_nav_subsystem_children.html", context, block_name="sb_main_content"
            )

        @router.get("/nav/{domain}/deliverable/{deliverable_id}/children", response_class=HTMLResponse, name="sw:nav-deliverable-children")
        async def sw_nav_deliverable_children(request: Request, domain: str, deliverable_id: int) -> Response:
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
            return self.templates.TemplateResponse(
                "sw_nav_deliverable_children.html", context, block_name="sb_main_content"
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

        # ====================================================================
        # Edit & Delete Routes
        # ====================================================================

        def _resolve_sw_record(sw: SWModelDB, sw_type: str, item_id: int):
            """Dispatch to appropriate get_*_by_id. Returns record or raises 404."""
            getters = {
                "vision": sw.get_vision_by_id,
                "subsystem": sw.get_subsystem_by_id,
                "deliverable": sw.get_deliverable_by_id,
                "epic": sw.get_epic_by_id,
                "story": sw.get_story_by_id,
                "task": sw.get_swtask_by_id,
            }
            getter = getters.get(sw_type)
            if not getter:
                raise HTTPException(status_code=400, detail=f"Invalid type: {sw_type}")
            record = getter(item_id)
            if not record:
                raise HTTPException(status_code=404, detail=f"{sw_type} {item_id} not found")
            return record

        def _build_parent_options(sw: SWModelDB, sw_type: str, record) -> list[dict] | None:
            """Build parent selector options for reparent support."""
            if sw_type == "vision":
                return None
            if sw_type == "subsystem":
                visions = sw.get_visions()
                return [{"id": v.project_id, "label": f"Vision: {v.name}",
                         "selected": record.parent_id == v.project_id} for v in visions]
            if sw_type == "deliverable":
                options = []
                for v in sw.get_visions():
                    options.append({"id": v.project_id, "label": f"Vision: {v.name}",
                                    "selected": record.parent_id == v.project_id})
                for s in sw.get_subsystems():
                    options.append({"id": s.project_id, "label": f"Subsystem: {s.name}",
                                    "selected": record.parent_id == s.project_id})
                return options
            if sw_type == "epic":
                options = [{"id": 0, "label": "(No parent / orphan)",
                            "selected": record.parent_id is None}]
                for v in sw.get_visions():
                    options.append({"id": v.project_id, "label": f"Vision: {v.name}",
                                    "selected": record.parent_id == v.project_id})
                for s in sw.get_subsystems():
                    options.append({"id": s.project_id, "label": f"Subsystem: {s.name}",
                                    "selected": record.parent_id == s.project_id})
                for d in sw.get_deliverables():
                    options.append({"id": d.project_id, "label": f"Deliverable: {d.name}",
                                    "selected": record.parent_id == d.project_id})
                return options
            if sw_type == "story":
                epics = sw.get_epics()
                return [{"id": e.project_id, "label": f"Epic: {e.name}",
                         "selected": record.project_id == e.project_id} for e in epics]
            if sw_type == "task":
                options = []
                for e in sw.get_epics():
                    options.append({"id": f"epic:{e.project_id}", "label": f"Epic: {e.name} (direct)",
                                    "selected": record.project_id == e.project_id and record.phase_id is None})
                    for s in sw.get_stories(epic=e):
                        options.append({"id": f"story:{s.phase_id}", "label": f"  Story: {s.name}",
                                        "selected": record.phase_id == s.phase_id})
                return options
            return None

        @router.get("/{domain}/edit/{sw_type}/{item_id}", response_class=HTMLResponse, name="sw:edit-modal")
        async def sw_edit_modal(request: Request, domain: str, sw_type: str, item_id: int) -> Response:
            sw = self._get_sw_db(domain)
            record = _resolve_sw_record(sw, sw_type, item_id)
            context = {
                "request": request,
                "domain": domain,
                "sw_type": sw_type,
                "item_id": item_id,
                "item_name": record.name,
                "item_description": record.description or "",
            }
            if sw_type in ("epic", "story", "task"):
                context["guardrail_types"] = list(GuardrailType)
                context["guardrail_type"] = record.guardrail_type.value
            if sw_type == "task":
                context["statuses"] = ["ToDo", "Doing", "Done"]
                context["status"] = record.status
            parent_options = _build_parent_options(sw, sw_type, record)
            if parent_options is not None:
                context["parent_options"] = parent_options
            return self.templates.TemplateResponse("sw_edit_modal.html", context)

        @router.post("/{domain}/edit/{sw_type}/{item_id}", response_class=HTMLResponse, name="sw:edit-submit")
        async def sw_edit_submit(
            request: Request,
            domain: str,
            sw_type: str,
            item_id: int,
            name: str = Form(...),
            description: str = Form(""),
            guardrail_type: str = Form(""),
            status: str = Form(""),
            parent_id: str = Form(""),
        ) -> Response:
            sw = self._get_sw_db(domain)
            record = _resolve_sw_record(sw, sw_type, item_id)
            record.name = name
            record.description = description if description else None
            if guardrail_type and sw_type in ("epic", "story", "task"):
                record.guardrail_type = GuardrailType(guardrail_type)
            if status and sw_type == "task":
                record.status = status

            # Handle reparent
            if parent_id and sw_type in ("subsystem", "deliverable", "epic"):
                new_parent = int(parent_id) if parent_id != "0" else None
                record.parent_id = new_parent
            elif parent_id and sw_type == "story":
                new_project_id = int(parent_id)
                if new_project_id != record.project_id:
                    record.project_id = new_project_id
            elif parent_id and sw_type == "task":
                if parent_id.startswith("epic:"):
                    new_project_id = int(parent_id.split(":")[1])
                    record.project_id = new_project_id
                    record.phase_id = None
                elif parent_id.startswith("story:"):
                    new_phase_id = int(parent_id.split(":")[1])
                    # Look up the story's project_id
                    story = sw.get_story_for_phase(new_phase_id)
                    if story:
                        record.project_id = story.project_id
                        record.phase_id = new_phase_id

            record.save()
            return HTMLResponse("", headers={"HX-Trigger": '{"close-modal": true, "refresh-board": true}'})

        @router.get("/{domain}/delete/{sw_type}/{item_id}", response_class=HTMLResponse, name="sw:delete-modal")
        async def sw_delete_modal(request: Request, domain: str, sw_type: str, item_id: int) -> Response:
            sw = self._get_sw_db(domain)
            record = _resolve_sw_record(sw, sw_type, item_id)
            # Compute child counts for impact info
            children = []
            if sw_type == "vision":
                subs = sw.get_subsystems(vision=record)
                epics = sw.get_epics(parent=record)
                if subs:
                    children.append(f"{len(subs)} subsystem(s)")
                if epics:
                    children.append(f"{len(epics)} epic(s)")
            elif sw_type == "subsystem":
                delis = sw.get_deliverables(parent=record)
                epics = sw.get_epics(parent=record)
                if delis:
                    children.append(f"{len(delis)} deliverable(s)")
                if epics:
                    children.append(f"{len(epics)} epic(s)")
            elif sw_type == "deliverable":
                epics = sw.get_epics(parent=record)
                if epics:
                    children.append(f"{len(epics)} epic(s)")
            elif sw_type == "epic":
                stories = sw.get_stories(epic=record)
                tasks = sw.get_swtasks(epic=record)
                if stories:
                    children.append(f"{len(stories)} story/stories")
                if tasks:
                    children.append(f"{len(tasks)} task(s)")
            elif sw_type == "story":
                tasks = sw.get_swtasks(story=record)
                if tasks:
                    children.append(f"{len(tasks)} task(s)")

            context = {
                "request": request,
                "domain": domain,
                "sw_type": sw_type,
                "item_id": item_id,
                "item_name": record.name,
                "children": children,
            }
            return self.templates.TemplateResponse("sw_delete_modal.html", context)

        @router.post("/{domain}/delete/{sw_type}/{item_id}", response_class=HTMLResponse, name="sw:delete-submit")
        async def sw_delete_submit(request: Request, domain: str, sw_type: str, item_id: int) -> Response:
            sw = self._get_sw_db(domain)
            record = _resolve_sw_record(sw, sw_type, item_id)
            item_name = record.name

            # Compute redirect URL before deleting
            redirect_url = str(request.url_for("sw:domain", domain=domain))
            if isinstance(record, SWTaskRecord):
                # Redirect to story or epic
                if record.phase_id:
                    story = sw.get_story_for_phase(record.phase_id)
                    if story:
                        redirect_url = str(request.url_for("sw:story", domain=domain, story_id=story.story_id))
                elif record.project_id:
                    epic = sw.get_epic_for_project(record.project_id)
                    if epic:
                        redirect_url = str(request.url_for("sw:epic", domain=domain, epic_id=epic.epic_id))
            elif isinstance(record, StoryRecord):
                epic = sw.get_epic_for_project(record.project_id)
                if epic:
                    redirect_url = str(request.url_for("sw:epic", domain=domain, epic_id=epic.epic_id))
            elif hasattr(record, 'parent') and record.parent:
                parent_wrapped = sw.wrap_project(record.parent)
                crumb = self._sw_record_crumb(parent_wrapped)
                if crumb["id_param"] and crumb["id_value"]:
                    redirect_url = str(request.url_for(crumb["route"], domain=domain, **{crumb["id_param"]: crumb["id_value"]}))

            record.delete_from_db()
            context = {
                "request": request,
                "success": True,
                "message": f"Deleted {sw_type} '{item_name}'",
                "redirect_url": redirect_url,
            }
            return self.templates.TemplateResponse("pm_form_result.html", context)

        # ====================================================================
        # Create Item Routes
        # ====================================================================

        ALLOWED_SW_TYPES = ("vision", "subsystem", "deliverable", "epic", "story", "task")

        @router.get("/{domain}/create", response_class=HTMLResponse, name="sw:create-modal")
        async def sw_create_modal(request: Request, domain: str) -> Response:
            sw = self._get_sw_db(domain)
            allow_vision = len(sw.get_visions()) == 0
            context = {
                "request": request,
                "domain": domain,
                "allow_vision": allow_vision,
                "sw_types": ["subsystem", "deliverable", "epic"],
            }
            if allow_vision:
                context["sw_types"] = ["vision", "subsystem", "deliverable", "epic"]
            return self.templates.TemplateResponse("sw_create_modal.html", context)

        @router.get("/{domain}/vision/{vision_id}/create", response_class=HTMLResponse, name="sw:vision-create-modal")
        async def sw_vision_create_modal(request: Request, domain: str, vision_id: int) -> Response:
            sw = self._get_sw_db(domain)
            vision = sw.get_vision_by_id(vision_id)
            if not vision:
                raise HTTPException(status_code=404, detail="Vision not found")
            context = {
                "request": request,
                "domain": domain,
                "sw_types": ["subsystem", "epic"],
                "parent_type": "vision",
                "parent_id": vision_id,
            }
            return self.templates.TemplateResponse("sw_create_modal.html", context)

        @router.get("/{domain}/subsystem/{subsystem_id}/create", response_class=HTMLResponse, name="sw:subsystem-create-modal")
        async def sw_subsystem_create_modal(request: Request, domain: str, subsystem_id: int) -> Response:
            sw = self._get_sw_db(domain)
            subsystem = sw.get_subsystem_by_id(subsystem_id)
            if not subsystem:
                raise HTTPException(status_code=404, detail="Subsystem not found")
            context = {
                "request": request,
                "domain": domain,
                "sw_types": ["deliverable", "epic"],
                "parent_type": "subsystem",
                "parent_id": subsystem_id,
            }
            return self.templates.TemplateResponse("sw_create_modal.html", context)

        @router.get("/{domain}/deliverable/{deliverable_id}/create", response_class=HTMLResponse, name="sw:deliverable-create-modal")
        async def sw_deliverable_create_modal(request: Request, domain: str, deliverable_id: int) -> Response:
            sw = self._get_sw_db(domain)
            deliverable = sw.get_deliverable_by_id(deliverable_id)
            if not deliverable:
                raise HTTPException(status_code=404, detail="Deliverable not found")
            context = {
                "request": request,
                "domain": domain,
                "sw_types": ["epic"],
                "parent_type": "deliverable",
                "parent_id": deliverable_id,
            }
            return self.templates.TemplateResponse("sw_create_modal.html", context)

        @router.get("/{domain}/epic/{epic_id}/create", response_class=HTMLResponse, name="sw:epic-create-modal")
        async def sw_epic_create_modal(request: Request, domain: str, epic_id: int) -> Response:
            sw = self._get_sw_db(domain)
            epic = sw.get_epic_by_id(epic_id)
            if not epic:
                raise HTTPException(status_code=404, detail="Epic not found")
            context = {
                "request": request,
                "domain": domain,
                "sw_types": ["story", "task"],
                "parent_type": "epic",
                "parent_id": epic_id,
            }
            return self.templates.TemplateResponse("sw_create_modal.html", context)

        @router.get("/{domain}/story/{story_id}/create", response_class=HTMLResponse, name="sw:story-create-modal")
        async def sw_story_create_modal(request: Request, domain: str, story_id: int) -> Response:
            sw = self._get_sw_db(domain)
            story = sw.get_story_by_id(story_id)
            if not story:
                raise HTTPException(status_code=404, detail="Story not found")
            context = {
                "request": request,
                "domain": domain,
                "sw_types": ["task"],
                "parent_type": "story",
                "parent_id": story_id,
            }
            return self.templates.TemplateResponse("sw_create_modal.html", context)

        @router.get("/{domain}/create-form/{sw_type}", response_class=HTMLResponse, name="sw:create-form")
        async def sw_create_form(request: Request, domain: str, sw_type: str,
                                 parent_type: str = "", parent_id: int = 0) -> Response:
            if sw_type not in ALLOWED_SW_TYPES:
                raise HTTPException(status_code=400, detail=f"Invalid type: {sw_type}")
            guardrail_types = list(GuardrailType) if sw_type in ("epic", "story", "task") else []
            context = {
                "request": request,
                "domain": domain,
                "sw_type": sw_type,
                "guardrail_types": guardrail_types,
                "parent_type": parent_type,
                "parent_id": parent_id,
            }
            return self.templates.TemplateResponse("sw_create_form.html", context)

        @router.post("/{domain}/create", response_class=HTMLResponse, name="sw:create-submit")
        async def sw_create_submit(
            request: Request,
            domain: str,
            sw_type: str = Form(...),
            name: str = Form(...),
            description: str = Form(""),
            guardrail_type: str = Form(""),
            parent_type: str = Form(""),
            parent_id: int = Form(0),
        ) -> Response:
            if sw_type not in ALLOWED_SW_TYPES:
                raise HTTPException(status_code=400, detail=f"Invalid type: {sw_type}")

            sw = self._get_sw_db(domain)
            pmdb_domain = self._get_domain(domain)
            desc = description if description else None

            # Resolve parent object if specified
            parent_vision = None
            parent_subsystem = None
            parent_deliverable = None
            parent_epic = None
            parent_story = None
            if parent_type == "vision" and parent_id:
                parent_vision = sw.get_vision_by_id(parent_id)
                if not parent_vision:
                    raise HTTPException(status_code=404, detail="Parent vision not found")
            elif parent_type == "subsystem" and parent_id:
                parent_subsystem = sw.get_subsystem_by_id(parent_id)
                if not parent_subsystem:
                    raise HTTPException(status_code=404, detail="Parent subsystem not found")
            elif parent_type == "deliverable" and parent_id:
                parent_deliverable = sw.get_deliverable_by_id(parent_id)
                if not parent_deliverable:
                    raise HTTPException(status_code=404, detail="Parent deliverable not found")
            elif parent_type == "epic" and parent_id:
                parent_epic = sw.get_epic_by_id(parent_id)
                if not parent_epic:
                    raise HTTPException(status_code=404, detail="Parent epic not found")
            elif parent_type == "story" and parent_id:
                parent_story = sw.get_story_by_id(parent_id)
                if not parent_story:
                    raise HTTPException(status_code=404, detail="Parent story not found")

            gt = GuardrailType(guardrail_type) if guardrail_type else None

            try:
                if sw_type == "vision":
                    item = sw.add_vision(pmdb_domain, name, description=desc)
                    redirect_url = request.url_for("sw:vision", domain=domain, vision_id=item.vision_id)
                elif sw_type == "subsystem":
                    item = sw.add_subsystem(pmdb_domain, name, description=desc, vision=parent_vision)
                    redirect_url = request.url_for("sw:subsystem", domain=domain, subsystem_id=item.subsystem_id)
                elif sw_type == "deliverable":
                    item = sw.add_deliverable(pmdb_domain, name, description=desc,
                                              vision=parent_vision, subsystem=parent_subsystem)
                    redirect_url = request.url_for("sw:deliverable", domain=domain, deliverable_id=item.deliverable_id)
                elif sw_type == "epic":
                    item = sw.add_epic(pmdb_domain, name, description=desc,
                                       vision=parent_vision, subsystem=parent_subsystem,
                                       deliverable=parent_deliverable, guardrail_type=gt)
                    redirect_url = request.url_for("sw:epic", domain=domain, epic_id=item.epic_id)
                elif sw_type == "story":
                    item = sw.add_story(pmdb_domain, name, description=desc,
                                        epic=parent_epic, guardrail_type=gt)
                    redirect_url = request.url_for("sw:story", domain=domain, story_id=item.story_id)
                elif sw_type == "task":
                    item = sw.add_task(pmdb_domain, name, description=desc,
                                       epic=parent_epic, story=parent_story, guardrail_type=gt)
                    redirect_url = request.url_for("sw:task", domain=domain, swtask_id=item.swtask_id)
            except Exception as e:
                context = {
                    "request": request,
                    "success": False,
                    "message": str(e),
                }
                return self.templates.TemplateResponse("pm_form_result.html", context)

            context = {
                "request": request,
                "success": True,
                "message": f"Created {sw_type} '{name}'",
                "redirect_url": str(redirect_url),
            }
            return self.templates.TemplateResponse("pm_form_result.html", context)

        return router
