#!/usr/bin/env python
import json
import pytest
from fastapi.testclient import TestClient

from dpm.fastapi.server import DPMServer
from dpm.store.wrappers import ModelDB

HTMX_HEADERS = {"HX-Request": "true"}


def assert_is_fragment(response):
    """Verify an HTMX response is a fragment (not a full HTML page)."""
    assert response.status_code == 200
    assert "<!DOCTYPE" not in response.text


@pytest.fixture
def sw_app(tmp_path):
    """Create a DPMServer with a SOFTWARE-mode domain and full hierarchy."""
    domain_name = "swdomain"
    db_path = tmp_path / f"{domain_name}.db"
    ModelDB(tmp_path, name_override=f"{domain_name}.db", autocreate=True)

    config = {
        "databases": {
            domain_name: {
                "path": str(db_path),
                "description": "SW test domain",
                "domain_mode": "software",
            }
        }
    }
    config_path = tmp_path / "config.json"
    with open(config_path, "w") as f:
        json.dump(config, f)

    server = DPMServer(config_path)
    domain = server.dpm_manager.domain_catalog.pmdb_domains[domain_name]
    sw = domain.db.sw_model_db

    # Build full hierarchy: vision > subsystem > deliverable > epic > story > task
    vision = sw.add_vision(domain, "Vision1", description="top vision")
    sub = sw.add_subsystem(domain, "Sub1", vision=vision)
    deli = sw.add_deliverable(domain, "Del1", subsystem=sub)
    epic = sw.add_epic(domain, "Epic1", deliverable=deli)
    story = sw.add_story(domain, "Story1", epic=epic)
    task = sw.add_task(domain, "Task1", story=story)

    # Also add an orphan epic (no parent)
    orphan_epic = sw.add_epic(domain, "OrphanEpic")

    return dict(
        app=server.app,
        server=server,
        domain_name=domain_name,
        db=domain.db,
        sw=sw,
        vision=vision,
        sub=sub,
        deli=deli,
        epic=epic,
        story=story,
        task=task,
        orphan_epic=orphan_epic,
    )


# ====================================================================
# PM Route → SW Redirect Tests
# ====================================================================


def test_pm_project_redirects_to_sw_vision(sw_app):
    """GET /{domain}/project/{project_id} on SW domain -> 307 redirect to SW vision."""
    client = TestClient(sw_app["app"], follow_redirects=False)
    d = sw_app["domain_name"]
    pid = sw_app["vision"].project_id
    response = client.get(f"/{d}/project/{pid}")
    assert response.status_code == 307
    assert f"/sw/{d}/vision/" in response.headers["location"]


def test_pm_project_redirects_to_sw_epic(sw_app):
    """GET /{domain}/project/{project_id} for epic -> 307 redirect to SW epic."""
    client = TestClient(sw_app["app"], follow_redirects=False)
    d = sw_app["domain_name"]
    pid = sw_app["epic"].project_id
    response = client.get(f"/{d}/project/{pid}")
    assert response.status_code == 307
    assert f"/sw/{d}/epic/" in response.headers["location"]


def test_pm_phase_redirects_to_sw_story(sw_app):
    """GET /{domain}/phase/{phase_id} for story -> 307 redirect to SW story."""
    client = TestClient(sw_app["app"], follow_redirects=False)
    d = sw_app["domain_name"]
    phase_id = sw_app["story"].phase_id
    response = client.get(f"/{d}/phase/{phase_id}")
    assert response.status_code == 307
    assert f"/sw/{d}/story/" in response.headers["location"]


def test_pm_task_redirects_to_sw_task(sw_app):
    """GET /{domain}/task/{task_id} for swtask -> 307 redirect to SW task."""
    client = TestClient(sw_app["app"], follow_redirects=False)
    d = sw_app["domain_name"]
    task_id = sw_app["task"].task_id
    response = client.get(f"/{d}/task/{task_id}")
    assert response.status_code == 307
    assert f"/sw/{d}/task/" in response.headers["location"]


def test_sw_home_page_recent_items(sw_app):
    """Home page shows SW type labels when last-accessed state is set on SW domain."""
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]
    mgr = sw_app["server"].dpm_manager

    # Set last-accessed state directly via the manager
    mgr.set_last_task(d, sw_app["task"])

    home = client.get("/")
    assert home.status_code == 200
    assert d in home.text
    # Should show SW-specific labels, not generic PM ones
    assert "Epic" in home.text  # last_project → Epic1's backing project
    assert "Story" in home.text  # last_phase → Story1's backing phase
    assert "Task" in home.text  # last_task → Task1
    # Should NOT show generic PM labels
    assert ">Project<" not in home.text
    assert ">Phase<" not in home.text


def test_sw_domain_redirect(sw_app):
    """GET /{domain} on SOFTWARE domain -> 307 redirect to /sw/{domain}."""
    client = TestClient(sw_app["app"], follow_redirects=False)
    domain = sw_app["domain_name"]
    response = client.get(f"/{domain}")
    assert response.status_code == 307
    assert f"/sw/{domain}" in response.headers["location"]


def test_sw_domain_landing(sw_app):
    """GET /sw/{domain} -> 200, contains Vision1 and OrphanEpic."""
    client = TestClient(sw_app["app"])
    domain = sw_app["domain_name"]
    response = client.get(f"/sw/{domain}")
    assert response.status_code == 200
    assert "Vision1" in response.text
    assert "OrphanEpic" in response.text


def test_sw_detail_views(sw_app):
    """GET each detail page -> 200."""
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]

    urls = [
        f"/sw/{d}/vision/{sw_app['vision'].vision_id}",
        f"/sw/{d}/subsystem/{sw_app['sub'].subsystem_id}",
        f"/sw/{d}/deliverable/{sw_app['deli'].deliverable_id}",
        f"/sw/{d}/epic/{sw_app['epic'].epic_id}",
        f"/sw/{d}/story/{sw_app['story'].story_id}",
        f"/sw/{d}/task/{sw_app['task'].swtask_id}",
    ]
    for url in urls:
        response = client.get(url)
        assert response.status_code == 200, f"Failed for {url}: {response.status_code}"


def test_sw_breadcrumbs(sw_app):
    """Detail pages show full ancestor breadcrumb chain.

    Fixture hierarchy: Vision1 > Sub1 > Del1 > Epic1 > Story1 > Task1
    """
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]

    # Vision: only domain in breadcrumbs (no project ancestors)
    r = client.get(f"/sw/{d}/vision/{sw_app['vision'].vision_id}")
    assert d in r.text
    # No ancestor badges before the heading
    assert "Vision1" in r.text

    # Subsystem: domain / Vision1
    r = client.get(f"/sw/{d}/subsystem/{sw_app['sub'].subsystem_id}")
    assert f"/sw/{d}/vision/" in r.text  # link to vision ancestor
    assert "Vision1" in r.text

    # Deliverable: domain / Vision1 / Sub1
    r = client.get(f"/sw/{d}/deliverable/{sw_app['deli'].deliverable_id}")
    assert f"/sw/{d}/vision/" in r.text
    assert "Vision1" in r.text
    assert f"/sw/{d}/subsystem/" in r.text
    assert "Sub1" in r.text

    # Epic: domain / Vision1 / Sub1 / Del1
    r = client.get(f"/sw/{d}/epic/{sw_app['epic'].epic_id}")
    assert "Vision1" in r.text
    assert "Sub1" in r.text
    assert "Del1" in r.text

    # Story: domain / Vision1 / Sub1 / Del1 / Epic1
    r = client.get(f"/sw/{d}/story/{sw_app['story'].story_id}")
    assert "Vision1" in r.text
    assert "Sub1" in r.text
    assert "Del1" in r.text
    assert "Epic1" in r.text

    # Task: domain / Vision1 / Sub1 / Del1 / Epic1 / Story1
    r = client.get(f"/sw/{d}/task/{sw_app['task'].swtask_id}")
    assert "Vision1" in r.text
    assert "Sub1" in r.text
    assert "Del1" in r.text
    assert "Epic1" in r.text
    assert "Story1" in r.text


def test_sw_detail_views_htmx(sw_app):
    """Same detail pages with HX-Request -> fragment (no DOCTYPE)."""
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]

    urls = [
        f"/sw/{d}",
        f"/sw/{d}/vision/{sw_app['vision'].vision_id}",
        f"/sw/{d}/subsystem/{sw_app['sub'].subsystem_id}",
        f"/sw/{d}/deliverable/{sw_app['deli'].deliverable_id}",
        f"/sw/{d}/epic/{sw_app['epic'].epic_id}",
        f"/sw/{d}/story/{sw_app['story'].story_id}",
        f"/sw/{d}/task/{sw_app['task'].swtask_id}",
    ]
    for url in urls:
        response = client.get(url, headers=HTMX_HEADERS)
        assert_is_fragment(response)


def test_sw_detail_views_404(sw_app):
    """Bad IDs -> 404."""
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]
    BAD_ID = 9999

    urls = [
        f"/sw/{d}/vision/{BAD_ID}",
        f"/sw/{d}/subsystem/{BAD_ID}",
        f"/sw/{d}/deliverable/{BAD_ID}",
        f"/sw/{d}/epic/{BAD_ID}",
        f"/sw/{d}/story/{BAD_ID}",
        f"/sw/{d}/task/{BAD_ID}",
    ]
    for url in urls:
        response = client.get(url)
        assert response.status_code == 404, f"Expected 404 for {url}, got {response.status_code}"


def test_sw_nav_tree(sw_app):
    """Nav tree routes return expected content."""
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]

    # Nav tree root
    response = client.get(f"/sw/nav/{d}/tree")
    assert response.status_code == 200
    assert "Vision1" in response.text

    # Nav domain items
    response = client.get(f"/sw/nav/{d}/items")
    assert response.status_code == 200
    assert "Vision1" in response.text
    assert "OrphanEpic" in response.text


def test_sw_nav_children(sw_app):
    """Nav expansion routes return children content."""
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]

    # Vision children -> subsystems + epics
    response = client.get(f"/sw/nav/{d}/vision/{sw_app['vision'].vision_id}/children")
    assert response.status_code == 200
    assert "Sub1" in response.text

    # Epic children -> stories
    response = client.get(f"/sw/nav/{d}/epic/{sw_app['epic'].epic_id}/children")
    assert response.status_code == 200
    assert "Story1" in response.text

    # Story tasks
    response = client.get(f"/sw/nav/{d}/story/{sw_app['story'].story_id}/tasks")
    assert response.status_code == 200
    assert "Task1" in response.text


def test_sw_nav_subsystem_children(sw_app):
    """Nav subsystem children -> 200, contains deliverable."""
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]
    response = client.get(f"/sw/nav/{d}/subsystem/{sw_app['sub'].subsystem_id}/children")
    assert response.status_code == 200
    assert "Del1" in response.text


def test_sw_nav_deliverable_children(sw_app):
    """Nav deliverable children -> 200, contains epic."""
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]
    response = client.get(f"/sw/nav/{d}/deliverable/{sw_app['deli'].deliverable_id}/children")
    assert response.status_code == 200
    assert "Epic1" in response.text


def test_sw_nav_vision_children_subsystems_expandable(sw_app):
    """Vision children template renders subsystems as expandable nodes."""
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]
    response = client.get(f"/sw/nav/{d}/vision/{sw_app['vision'].vision_id}/children")
    assert response.status_code == 200
    # Subsystem should have hx-get for expansion, not be a leaf node
    assert "sw:nav-subsystem-children" not in response.text  # url_for renders the path
    assert f"/sw/nav/{d}/subsystem/" in response.text
    assert "tree-toggle" in response.text


def test_sw_nav_404(sw_app):
    """Nav routes with bad IDs -> 404."""
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]
    BAD_ID = 9999

    assert client.get(f"/sw/nav/{d}/vision/{BAD_ID}/children").status_code == 404
    assert client.get(f"/sw/nav/{d}/subsystem/{BAD_ID}/children").status_code == 404
    assert client.get(f"/sw/nav/{d}/deliverable/{BAD_ID}/children").status_code == 404
    assert client.get(f"/sw/nav/{d}/epic/{BAD_ID}/children").status_code == 404
    assert client.get(f"/sw/nav/{d}/story/{BAD_ID}/tasks").status_code == 404


# ====================================================================
# Create Modal Tests
# ====================================================================


@pytest.fixture
def sw_empty_app(tmp_path):
    """Create a DPMServer with a SOFTWARE-mode domain and no items."""
    domain_name = "emptydomain"
    db_path = tmp_path / f"{domain_name}.db"
    ModelDB(tmp_path, name_override=f"{domain_name}.db", autocreate=True)

    config = {
        "databases": {
            domain_name: {
                "path": str(db_path),
                "description": "Empty SW domain",
                "domain_mode": "software",
            }
        }
    }
    config_path = tmp_path / "config.json"
    with open(config_path, "w") as f:
        json.dump(config, f)

    server = DPMServer(config_path)
    domain = server.dpm_manager.domain_catalog.pmdb_domains[domain_name]
    return dict(
        app=server.app,
        domain_name=domain_name,
        domain=domain,
        sw=domain.db.sw_model_db,
    )


def test_sw_create_modal(sw_app):
    """GET create modal -> 200, contains type picker, Vision NOT offered (already exists)."""
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]
    response = client.get(f"/sw/{d}/create")
    assert response.status_code == 200
    assert "sw-type-picker" in response.text
    assert "Subsystem" in response.text
    assert "Epic" in response.text
    # Vision should NOT be offered since one already exists
    assert "create-form/vision" not in response.text


def test_sw_create_modal_empty_domain(sw_empty_app):
    """GET create modal on empty domain -> Vision IS offered."""
    client = TestClient(sw_empty_app["app"])
    d = sw_empty_app["domain_name"]
    response = client.get(f"/sw/{d}/create")
    assert response.status_code == 200
    assert "create-form/vision" in response.text


def test_sw_create_form_fragments(sw_app):
    """GET each type's form fragment -> 200."""
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]
    for sw_type in ("subsystem", "deliverable", "epic"):
        response = client.get(f"/sw/{d}/create-form/{sw_type}")
        assert response.status_code == 200, f"Failed for {sw_type}"
        assert f'value="{sw_type}"' in response.text
    # Epic form should include guardrail_type select
    response = client.get(f"/sw/{d}/create-form/epic")
    assert "guardrail_type" in response.text
    assert "PRODUCTION" in response.text


def test_sw_create_form_vision(sw_empty_app):
    """GET vision form fragment -> 200."""
    client = TestClient(sw_empty_app["app"])
    d = sw_empty_app["domain_name"]
    response = client.get(f"/sw/{d}/create-form/vision")
    assert response.status_code == 200
    assert 'value="vision"' in response.text


def test_sw_create_submit(sw_empty_app):
    """POST create each type -> success message + item exists in DB."""
    client = TestClient(sw_empty_app["app"])
    d = sw_empty_app["domain_name"]
    sw = sw_empty_app["sw"]

    # Create vision
    response = client.post(f"/sw/{d}/create", data={"sw_type": "vision", "name": "MyVision", "description": "desc"})
    assert response.status_code == 200
    assert "Created vision" in response.text
    assert len(sw.get_visions()) == 1

    # Create subsystem
    response = client.post(f"/sw/{d}/create", data={"sw_type": "subsystem", "name": "MySub"})
    assert response.status_code == 200
    assert "Created subsystem" in response.text
    assert len(sw.get_subsystems()) == 1

    # Create deliverable
    response = client.post(f"/sw/{d}/create", data={"sw_type": "deliverable", "name": "MyDel"})
    assert response.status_code == 200
    assert "Created deliverable" in response.text
    assert len(sw.get_deliverables()) == 1

    # Create epic
    response = client.post(f"/sw/{d}/create", data={"sw_type": "epic", "name": "MyEpic"})
    assert response.status_code == 200
    assert "Created epic" in response.text
    assert len(sw.get_epics()) == 1


def test_sw_create_submit_epic_guardrail(sw_empty_app):
    """POST epic with guardrail_type=mvp -> persisted correctly."""
    client = TestClient(sw_empty_app["app"])
    d = sw_empty_app["domain_name"]
    sw = sw_empty_app["sw"]

    response = client.post(f"/sw/{d}/create", data={
        "sw_type": "epic",
        "name": "MvpEpic",
        "guardrail_type": "mvp",
    })
    assert response.status_code == 200
    assert "Created epic" in response.text
    epics = sw.get_epics()
    assert len(epics) == 1
    assert epics[0].guardrail_type.value == "mvp"


def test_sw_create_submit_duplicate(sw_app):
    """POST duplicate name -> error message."""
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]

    response = client.post(f"/sw/{d}/create", data={"sw_type": "subsystem", "name": "Vision1"})
    assert response.status_code == 200
    assert "alert-error" in response.text
    assert "Already have" in response.text


# ====================================================================
# Vision Create Modal Tests
# ====================================================================


def test_sw_vision_create_modal(sw_app):
    """GET vision create modal -> 200, offers Subsystem and Epic only."""
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]
    vid = sw_app["vision"].vision_id
    response = client.get(f"/sw/{d}/vision/{vid}/create")
    assert response.status_code == 200
    assert "sw-type-picker" in response.text
    assert "create-form/subsystem" in response.text
    assert "create-form/epic" in response.text
    # Vision and Deliverable should NOT be offered
    assert "create-form/vision" not in response.text
    assert "create-form/deliverable" not in response.text


def test_sw_vision_create_modal_404(sw_app):
    """GET vision create modal with bad ID -> 404."""
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]
    assert client.get(f"/sw/{d}/vision/9999/create").status_code == 404


def test_sw_vision_create_form_with_parent(sw_app):
    """GET form fragment via vision modal includes parent fields."""
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]
    vid = sw_app["vision"].vision_id
    response = client.get(f"/sw/{d}/create-form/subsystem?parent_type=vision&parent_id={vid}")
    assert response.status_code == 200
    assert f'value="vision"' in response.text
    assert f'value="{vid}"' in response.text


def test_sw_vision_create_submit_subsystem(sw_app):
    """POST subsystem under vision -> parented correctly."""
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]
    sw = sw_app["sw"]
    vid = sw_app["vision"].vision_id

    response = client.post(f"/sw/{d}/create", data={
        "sw_type": "subsystem",
        "name": "VisionSub",
        "parent_type": "vision",
        "parent_id": vid,
    })
    assert response.status_code == 200
    assert "Created subsystem" in response.text
    # Verify it's a child of the vision
    subs = sw.get_subsystems(vision=sw_app["vision"])
    sub_names = [s.name for s in subs]
    assert "VisionSub" in sub_names


def test_sw_vision_create_submit_epic(sw_app):
    """POST epic under vision -> parented correctly."""
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]
    sw = sw_app["sw"]
    vid = sw_app["vision"].vision_id

    response = client.post(f"/sw/{d}/create", data={
        "sw_type": "epic",
        "name": "VisionEpic",
        "guardrail_type": "prototype",
        "parent_type": "vision",
        "parent_id": vid,
    })
    assert response.status_code == 200
    assert "Created epic" in response.text
    # Verify it's a child of the vision
    epics = sw.get_epics(parent=sw_app["vision"])
    epic_names = [e.name for e in epics]
    assert "VisionEpic" in epic_names
    # Verify guardrail type
    vision_epic = [e for e in epics if e.name == "VisionEpic"][0]
    assert vision_epic.guardrail_type.value == "prototype"


# ====================================================================
# Subsystem Create Modal Tests
# ====================================================================


def test_sw_subsystem_create_modal(sw_app):
    """GET subsystem create modal -> 200, offers Deliverable and Epic only."""
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]
    sid = sw_app["sub"].subsystem_id
    response = client.get(f"/sw/{d}/subsystem/{sid}/create")
    assert response.status_code == 200
    assert "sw-type-picker" in response.text
    assert "create-form/deliverable" in response.text
    assert "create-form/epic" in response.text
    assert "create-form/vision" not in response.text
    assert "create-form/subsystem" not in response.text


def test_sw_subsystem_create_modal_404(sw_app):
    """GET subsystem create modal with bad ID -> 404."""
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]
    assert client.get(f"/sw/{d}/subsystem/9999/create").status_code == 404


def test_sw_subsystem_create_submit_deliverable(sw_app):
    """POST deliverable under subsystem -> parented correctly."""
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]
    sw = sw_app["sw"]
    sid = sw_app["sub"].subsystem_id

    response = client.post(f"/sw/{d}/create", data={
        "sw_type": "deliverable",
        "name": "SubDel",
        "parent_type": "subsystem",
        "parent_id": sid,
    })
    assert response.status_code == 200
    assert "Created deliverable" in response.text
    delis = sw.get_deliverables(parent=sw_app["sub"])
    deli_names = [d.name for d in delis]
    assert "SubDel" in deli_names


def test_sw_subsystem_create_submit_epic(sw_app):
    """POST epic under subsystem -> parented correctly."""
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]
    sw = sw_app["sw"]
    sid = sw_app["sub"].subsystem_id

    response = client.post(f"/sw/{d}/create", data={
        "sw_type": "epic",
        "name": "SubEpic",
        "guardrail_type": "mvp",
        "parent_type": "subsystem",
        "parent_id": sid,
    })
    assert response.status_code == 200
    assert "Created epic" in response.text
    epics = sw.get_epics(parent=sw_app["sub"])
    epic_names = [e.name for e in epics]
    assert "SubEpic" in epic_names
    sub_epic = [e for e in epics if e.name == "SubEpic"][0]
    assert sub_epic.guardrail_type.value == "mvp"


# ====================================================================
# Deliverable Create Modal Tests
# ====================================================================


def test_sw_deliverable_create_modal(sw_app):
    """GET deliverable create modal -> 200, offers Epic only."""
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]
    did = sw_app["deli"].deliverable_id
    response = client.get(f"/sw/{d}/deliverable/{did}/create")
    assert response.status_code == 200
    assert "sw-type-picker" in response.text
    assert "create-form/epic" in response.text
    assert "create-form/vision" not in response.text
    assert "create-form/subsystem" not in response.text
    assert "create-form/deliverable" not in response.text


def test_sw_deliverable_create_modal_404(sw_app):
    """GET deliverable create modal with bad ID -> 404."""
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]
    assert client.get(f"/sw/{d}/deliverable/9999/create").status_code == 404


def test_sw_deliverable_create_submit_epic(sw_app):
    """POST epic under deliverable -> parented correctly."""
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]
    sw = sw_app["sw"]
    did = sw_app["deli"].deliverable_id

    response = client.post(f"/sw/{d}/create", data={
        "sw_type": "epic",
        "name": "DelEpic",
        "guardrail_type": "poc",
        "parent_type": "deliverable",
        "parent_id": did,
    })
    assert response.status_code == 200
    assert "Created epic" in response.text
    epics = sw.get_epics(parent=sw_app["deli"])
    epic_names = [e.name for e in epics]
    assert "DelEpic" in epic_names
    del_epic = [e for e in epics if e.name == "DelEpic"][0]
    assert del_epic.guardrail_type.value == "poc"


# ====================================================================
# Epic Create Modal Tests
# ====================================================================


def test_sw_epic_create_modal(sw_app):
    """GET epic create modal -> 200, offers Story and Task only."""
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]
    eid = sw_app["epic"].epic_id
    response = client.get(f"/sw/{d}/epic/{eid}/create")
    assert response.status_code == 200
    assert "sw-type-picker" in response.text
    assert "create-form/story" in response.text
    assert "create-form/task" in response.text
    assert "create-form/vision" not in response.text
    assert "create-form/epic" not in response.text


def test_sw_epic_create_modal_404(sw_app):
    """GET epic create modal with bad ID -> 404."""
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]
    assert client.get(f"/sw/{d}/epic/9999/create").status_code == 404


def test_sw_epic_create_form_story(sw_app):
    """GET story form fragment -> 200, includes guardrail_type select."""
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]
    eid = sw_app["epic"].epic_id
    response = client.get(f"/sw/{d}/create-form/story?parent_type=epic&parent_id={eid}")
    assert response.status_code == 200
    assert 'value="story"' in response.text
    assert "guardrail_type" in response.text


def test_sw_epic_create_form_task(sw_app):
    """GET task form fragment -> 200, includes guardrail_type select."""
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]
    eid = sw_app["epic"].epic_id
    response = client.get(f"/sw/{d}/create-form/task?parent_type=epic&parent_id={eid}")
    assert response.status_code == 200
    assert 'value="task"' in response.text
    assert "guardrail_type" in response.text


def test_sw_epic_create_submit_story(sw_app):
    """POST story under epic -> parented correctly."""
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]
    sw = sw_app["sw"]
    eid = sw_app["epic"].epic_id

    response = client.post(f"/sw/{d}/create", data={
        "sw_type": "story",
        "name": "EpicStory",
        "parent_type": "epic",
        "parent_id": eid,
    })
    assert response.status_code == 200
    assert "Created story" in response.text
    stories = sw.get_stories(epic=sw_app["epic"])
    story_names = [s.name for s in stories]
    assert "EpicStory" in story_names


def test_sw_epic_create_submit_story_guardrail(sw_app):
    """POST story under epic with guardrail_type -> persisted."""
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]
    sw = sw_app["sw"]
    eid = sw_app["epic"].epic_id

    response = client.post(f"/sw/{d}/create", data={
        "sw_type": "story",
        "name": "MvpStory",
        "guardrail_type": "mvp",
        "parent_type": "epic",
        "parent_id": eid,
    })
    assert response.status_code == 200
    assert "Created story" in response.text
    stories = sw.get_stories(epic=sw_app["epic"])
    mvp_story = [s for s in stories if s.name == "MvpStory"][0]
    assert mvp_story.guardrail_type.value == "mvp"


def test_sw_epic_create_submit_task(sw_app):
    """POST task under epic -> parented correctly (direct task, no story)."""
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]
    sw = sw_app["sw"]
    eid = sw_app["epic"].epic_id

    response = client.post(f"/sw/{d}/create", data={
        "sw_type": "task",
        "name": "EpicTask",
        "parent_type": "epic",
        "parent_id": eid,
    })
    assert response.status_code == 200
    assert "Created task" in response.text
    tasks = sw.get_swtasks(epic=sw_app["epic"])
    task_names = [t.name for t in tasks]
    assert "EpicTask" in task_names


def test_sw_epic_create_submit_task_guardrail(sw_app):
    """POST task under epic with guardrail_type -> persisted."""
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]
    sw = sw_app["sw"]
    eid = sw_app["epic"].epic_id

    response = client.post(f"/sw/{d}/create", data={
        "sw_type": "task",
        "name": "PocTask",
        "guardrail_type": "poc",
        "parent_type": "epic",
        "parent_id": eid,
    })
    assert response.status_code == 200
    assert "Created task" in response.text
    tasks = sw.get_swtasks(epic=sw_app["epic"])
    poc_task = [t for t in tasks if t.name == "PocTask"][0]
    assert poc_task.guardrail_type.value == "poc"


# ====================================================================
# Story Create Modal Tests
# ====================================================================


def test_sw_story_create_modal(sw_app):
    """GET story create modal -> 200, offers Task only."""
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]
    sid = sw_app["story"].story_id
    response = client.get(f"/sw/{d}/story/{sid}/create")
    assert response.status_code == 200
    assert "sw-type-picker" in response.text
    assert "create-form/task" in response.text
    assert "create-form/story" not in response.text
    assert "create-form/epic" not in response.text


def test_sw_story_create_modal_404(sw_app):
    """GET story create modal with bad ID -> 404."""
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]
    assert client.get(f"/sw/{d}/story/9999/create").status_code == 404


def test_sw_story_create_submit_task(sw_app):
    """POST task under story -> parented correctly."""
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]
    sw = sw_app["sw"]
    sid = sw_app["story"].story_id

    response = client.post(f"/sw/{d}/create", data={
        "sw_type": "task",
        "name": "StoryTask",
        "parent_type": "story",
        "parent_id": sid,
    })
    assert response.status_code == 200
    assert "Created task" in response.text
    tasks = sw.get_swtasks(story=sw_app["story"])
    task_names = [t.name for t in tasks]
    assert "StoryTask" in task_names


# ====================================================================
# Edit Modal Tests
# ====================================================================


def test_sw_edit_modal(sw_app):
    """GET edit modal for each type -> 200, form fields present."""
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]

    cases = [
        ("vision", sw_app["vision"].vision_id),
        ("subsystem", sw_app["sub"].subsystem_id),
        ("deliverable", sw_app["deli"].deliverable_id),
        ("epic", sw_app["epic"].epic_id),
        ("story", sw_app["story"].story_id),
        ("task", sw_app["task"].swtask_id),
    ]
    for sw_type, item_id in cases:
        response = client.get(f"/sw/{d}/edit/{sw_type}/{item_id}")
        assert response.status_code == 200, f"Failed for {sw_type}"
        assert 'name="name"' in response.text
        assert 'name="description"' in response.text

    # Epic/story/task should have guardrail_type select
    for sw_type, item_id in cases[3:]:
        response = client.get(f"/sw/{d}/edit/{sw_type}/{item_id}")
        assert "guardrail_type" in response.text, f"No guardrail_type for {sw_type}"

    # Only task should have status select
    response = client.get(f"/sw/{d}/edit/task/{sw_app['task'].swtask_id}")
    assert 'name="status"' in response.text

    # Vision should NOT have guardrail_type
    response = client.get(f"/sw/{d}/edit/vision/{sw_app['vision'].vision_id}")
    assert "guardrail_type" not in response.text


def test_sw_edit_modal_404(sw_app):
    """GET edit modal with bad ID -> 404."""
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]
    assert client.get(f"/sw/{d}/edit/vision/9999").status_code == 404


def test_sw_edit_submit(sw_app):
    """POST edit for vision -> name/description updated in DB."""
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]
    sw = sw_app["sw"]
    vid = sw_app["vision"].vision_id

    response = client.post(f"/sw/{d}/edit/vision/{vid}", data={
        "name": "Vision1-Edited",
        "description": "new desc",
    })
    assert response.status_code == 200
    assert "close-modal" in response.headers.get("hx-trigger", "")

    updated = sw.get_vision_by_id(vid)
    assert updated.name == "Vision1-Edited"
    assert updated.description == "new desc"


def test_sw_edit_guardrail(sw_app):
    """Edit epic guardrail_type -> persisted."""
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]
    sw = sw_app["sw"]
    eid = sw_app["epic"].epic_id

    response = client.post(f"/sw/{d}/edit/epic/{eid}", data={
        "name": "Epic1",
        "description": "",
        "guardrail_type": "mvp",
    })
    assert response.status_code == 200
    updated = sw.get_epic_by_id(eid)
    assert updated.guardrail_type.value == "mvp"


def test_sw_edit_task_status(sw_app):
    """Edit task status -> persisted."""
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]
    sw = sw_app["sw"]
    tid = sw_app["task"].swtask_id

    response = client.post(f"/sw/{d}/edit/task/{tid}", data={
        "name": "Task1",
        "description": "",
        "guardrail_type": "production",
        "status": "Doing",
    })
    assert response.status_code == 200
    updated = sw.get_swtask_by_id(tid)
    assert updated.status == "Doing"


# ====================================================================
# Delete Modal Tests
# ====================================================================


def test_sw_delete_modal(sw_app):
    """GET delete modal -> 200, warning text present."""
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]

    cases = [
        ("vision", sw_app["vision"].vision_id, "Vision1"),
        ("subsystem", sw_app["sub"].subsystem_id, "Sub1"),
        ("epic", sw_app["epic"].epic_id, "Epic1"),
        ("story", sw_app["story"].story_id, "Story1"),
        ("task", sw_app["task"].swtask_id, "Task1"),
    ]
    for sw_type, item_id, name in cases:
        response = client.get(f"/sw/{d}/delete/{sw_type}/{item_id}")
        assert response.status_code == 200, f"Failed for {sw_type}"
        assert name in response.text
        assert "Are you sure" in response.text


def test_sw_delete_modal_404(sw_app):
    """GET delete modal with bad ID -> 404."""
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]
    assert client.get(f"/sw/{d}/delete/vision/9999").status_code == 404


def test_sw_delete_with_children(sw_app):
    """Delete modal for vision with children shows impact info."""
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]
    vid = sw_app["vision"].vision_id

    response = client.get(f"/sw/{d}/delete/vision/{vid}")
    assert response.status_code == 200
    # Vision has 1 subsystem child (epic is under deliverable, not directly under vision)
    assert "subsystem" in response.text
    assert "This item has children" in response.text

    # Epic has stories + tasks
    eid = sw_app["epic"].epic_id
    response = client.get(f"/sw/{d}/delete/epic/{eid}")
    assert response.status_code == 200
    assert "story" in response.text
    assert "task" in response.text


def test_sw_delete_submit(sw_app):
    """POST delete for task -> removed from DB, redirects to parent."""
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]
    sw = sw_app["sw"]
    tid = sw_app["task"].swtask_id

    response = client.post(f"/sw/{d}/delete/task/{tid}")
    assert response.status_code == 200
    assert "Deleted task" in response.text
    assert sw.get_swtask_by_id(tid) is None


def test_sw_delete_submit_story(sw_app):
    """POST delete story -> removed from DB."""
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]
    sw = sw_app["sw"]
    sid = sw_app["story"].story_id

    response = client.post(f"/sw/{d}/delete/story/{sid}")
    assert response.status_code == 200
    assert "Deleted story" in response.text
    assert sw.get_story_by_id(sid) is None


def test_sw_delete_submit_vision(sw_empty_app):
    """POST delete vision on empty-ish domain -> removed, redirects to domain."""
    client = TestClient(sw_empty_app["app"])
    d = sw_empty_app["domain_name"]
    sw = sw_empty_app["sw"]
    domain = sw_empty_app["domain"]

    vision = sw.add_vision(domain, "TempVision")
    vid = vision.vision_id
    response = client.post(f"/sw/{d}/delete/vision/{vid}")
    assert response.status_code == 200
    assert "Deleted vision" in response.text
    assert sw.get_vision_by_id(vid) is None


# ====================================================================
# Reparent Tests
# ====================================================================


def test_sw_edit_modal_parent_options_epic(sw_app):
    """Epic edit modal shows parent selector with orphan option."""
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]
    eid = sw_app["epic"].epic_id
    response = client.get(f"/sw/{d}/edit/epic/{eid}")
    assert response.status_code == 200
    assert 'name="parent_id"' in response.text
    assert "No parent" in response.text
    assert "Vision: Vision1" in response.text


def test_sw_edit_no_parent_for_vision(sw_app):
    """Vision edit modal has no parent selector."""
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]
    vid = sw_app["vision"].vision_id
    response = client.get(f"/sw/{d}/edit/vision/{vid}")
    assert response.status_code == 200
    assert 'name="parent_id"' not in response.text


def test_sw_edit_reparent_epic(sw_app):
    """POST moves epic to a different parent."""
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]
    sw = sw_app["sw"]
    # OrphanEpic has no parent; reparent it under the vision
    eid = sw_app["orphan_epic"].epic_id
    vid_project_id = sw_app["vision"].project_id
    response = client.post(f"/sw/{d}/edit/epic/{eid}", data={
        "name": "OrphanEpic",
        "description": "",
        "guardrail_type": "production",
        "parent_id": str(vid_project_id),
    })
    assert response.status_code == 200
    updated = sw.get_epic_by_id(eid)
    assert updated.parent_id == vid_project_id


def test_sw_edit_reparent_story(sw_app):
    """POST moves story to a different epic."""
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]
    sw = sw_app["sw"]
    domain = sw_app["server"].dpm_manager.domain_catalog.pmdb_domains[d]

    # Create a second epic and move Story1 to it
    epic2 = sw.add_epic(domain, "Epic2")
    sid = sw_app["story"].story_id
    response = client.post(f"/sw/{d}/edit/story/{sid}", data={
        "name": "Story1",
        "description": "",
        "guardrail_type": "production",
        "parent_id": str(epic2.project_id),
    })
    assert response.status_code == 200
    updated = sw.get_story_by_id(sid)
    assert updated.project_id == epic2.project_id


def test_pm_nav_tree_sw_domain(sw_app):
    """Nav tree fires sw:nav-domain-items for SW domains, not pm:nav-domain-projects."""
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]

    # Sidebar nav tree
    response = client.get("/nav_tree")
    assert response.status_code == 200
    assert f"/sw/nav/{d}/items" in response.text
    # Should NOT use pm:nav-domain-projects for this SW domain
    assert f"/nav/{d}/projects" not in response.text
    # Should show SW badge
    assert "SW" in response.text

    # Domains tree (main content)
    response = client.get("/domains")
    assert response.status_code == 200
    assert f"/sw/nav/{d}/items" in response.text


def test_sw_story_create_submit_task_guardrail(sw_app):
    """POST task under story with guardrail_type -> persisted."""
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]
    sw = sw_app["sw"]
    sid = sw_app["story"].story_id

    response = client.post(f"/sw/{d}/create", data={
        "sw_type": "task",
        "name": "ResearchTask",
        "guardrail_type": "research",
        "parent_type": "story",
        "parent_id": sid,
    })
    assert response.status_code == 200
    assert "Created task" in response.text
    tasks = sw.get_swtasks(story=sw_app["story"])
    research_task = [t for t in tasks if t.name == "ResearchTask"][0]
    assert research_task.guardrail_type.value == "research"
