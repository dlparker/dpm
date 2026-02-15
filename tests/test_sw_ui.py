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


def test_sw_nav_404(sw_app):
    """Nav routes with bad IDs -> 404."""
    client = TestClient(sw_app["app"])
    d = sw_app["domain_name"]
    BAD_ID = 9999

    assert client.get(f"/sw/nav/{d}/vision/{BAD_ID}/children").status_code == 404
    assert client.get(f"/sw/nav/{d}/epic/{BAD_ID}/children").status_code == 404
    assert client.get(f"/sw/nav/{d}/story/{BAD_ID}/tasks").status_code == 404
