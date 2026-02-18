#!/usr/bin/env python
import json
import pytest
from fastapi.testclient import TestClient

from dpm.fastapi.server import DPMServer
from dpm.store.wrappers import ModelDB

HTMX_HEADERS = {"HX-Request": "true"}


@pytest.fixture
def sw_kanban_app(tmp_path):
    """Create a DPMServer with an SW domain, epic, 2 stories, 3 tasks."""
    domain_name = "kanban_sw"
    db_path = tmp_path / f"{domain_name}.db"
    ModelDB(tmp_path, name_override=f"{domain_name}.db", autocreate=True)

    config = {
        "databases": {
            domain_name: {
                "path": str(db_path),
                "description": "Kanban SW domain",
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

    epic = sw.add_epic(domain, "BoardEpic")
    story1 = sw.add_story(domain, "Story1", epic=epic)
    story2 = sw.add_story(domain, "Story2", epic=epic)
    task1 = sw.add_task(domain, "Task1", story=story1)
    task2 = sw.add_task(domain, "Task2", story=story2)
    task3 = sw.add_task(domain, "DirectTask", epic=epic)  # direct on epic

    return dict(
        app=server.app,
        server=server,
        domain_name=domain_name,
        sw=sw,
        domain=domain,
        epic=epic,
        story1=story1,
        story2=story2,
        task1=task1,
        task2=task2,
        task3=task3,
    )


# ====================================================================
# Board Page Tests
# ====================================================================


def test_sw_board_page(sw_kanban_app):
    """GET board page -> 200, full HTML."""
    client = TestClient(sw_kanban_app["app"])
    d = sw_kanban_app["domain_name"]
    response = client.get(f"/sw/{d}/board")
    assert response.status_code == 200
    assert "SW Kanban Board" in response.text
    assert "BoardEpic" in response.text


def test_sw_board_page_htmx(sw_kanban_app):
    """GET board page with HX-Request -> fragment."""
    client = TestClient(sw_kanban_app["app"])
    d = sw_kanban_app["domain_name"]
    response = client.get(f"/sw/{d}/board", headers=HTMX_HEADERS)
    assert response.status_code == 200
    assert "<!DOCTYPE" not in response.text


# ====================================================================
# Columns Tests
# ====================================================================


def test_sw_board_columns_unfiltered(sw_kanban_app):
    """GET columns with no filter -> all 3 tasks."""
    client = TestClient(sw_kanban_app["app"])
    d = sw_kanban_app["domain_name"]
    response = client.get(f"/sw/{d}/board/columns")
    assert response.status_code == 200
    assert "Task1" in response.text
    assert "Task2" in response.text
    assert "DirectTask" in response.text


def test_sw_board_columns_epic_filtered(sw_kanban_app):
    """GET columns filtered by epic -> all 3 tasks (all belong to same epic)."""
    client = TestClient(sw_kanban_app["app"])
    d = sw_kanban_app["domain_name"]
    eid = sw_kanban_app["epic"].epic_id
    response = client.get(f"/sw/{d}/board/columns?epic_id={eid}")
    assert response.status_code == 200
    assert "Task1" in response.text
    assert "Task2" in response.text
    assert "DirectTask" in response.text


def test_sw_board_columns_story_filtered(sw_kanban_app):
    """GET columns filtered by story -> only that story's task."""
    client = TestClient(sw_kanban_app["app"])
    d = sw_kanban_app["domain_name"]
    sid = sw_kanban_app["story1"].story_id
    response = client.get(f"/sw/{d}/board/columns?story_id={sid}")
    assert response.status_code == 200
    assert "Task1" in response.text
    assert "Task2" not in response.text
    assert "DirectTask" not in response.text


# ====================================================================
# Story Options Tests
# ====================================================================


def test_sw_board_story_options(sw_kanban_app):
    """GET story-options -> lists stories for the epic."""
    client = TestClient(sw_kanban_app["app"])
    d = sw_kanban_app["domain_name"]
    eid = sw_kanban_app["epic"].epic_id
    response = client.get(f"/sw/{d}/board/story-options?epic_id={eid}")
    assert response.status_code == 200
    assert "Story1" in response.text
    assert "Story2" in response.text
    assert "All Stories" in response.text


def test_sw_board_story_options_bad_epic(sw_kanban_app):
    """GET story-options with bad epic -> graceful message."""
    client = TestClient(sw_kanban_app["app"])
    d = sw_kanban_app["domain_name"]
    response = client.get(f"/sw/{d}/board/story-options?epic_id=9999")
    assert response.status_code == 200
    assert "No stories found" in response.text


# ====================================================================
# Move Task Tests
# ====================================================================


def test_sw_board_move_task(sw_kanban_app):
    """POST move-task -> success, status updated."""
    client = TestClient(sw_kanban_app["app"])
    d = sw_kanban_app["domain_name"]
    sw = sw_kanban_app["sw"]
    tid = sw_kanban_app["task1"].swtask_id

    response = client.post(f"/sw/{d}/board/move-task", data={
        "task_id": tid,
        "new_status": "Doing",
    })
    assert response.status_code == 200
    assert "Task moved" in response.text
    assert response.headers.get("hx-trigger") == "refresh-board"
    updated = sw.get_swtask_by_id(tid)
    assert updated.status == "Doing"


def test_sw_board_move_task_blocked(sw_kanban_app):
    """POST move-task on blocked task -> rejection."""
    client = TestClient(sw_kanban_app["app"])
    d = sw_kanban_app["domain_name"]
    sw = sw_kanban_app["sw"]

    # Add a blocker: task2 blocks task1
    task1 = sw.get_swtask_by_id(sw_kanban_app["task1"].swtask_id)
    task2 = sw.get_swtask_by_id(sw_kanban_app["task2"].swtask_id)
    task1.add_blocker(task2)

    response = client.post(f"/sw/{d}/board/move-task", data={
        "task_id": task1.swtask_id,
        "new_status": "Doing",
    })
    assert response.status_code == 200
    assert "Cannot move" in response.text
    assert "Task2" in response.text


def test_sw_board_move_task_not_found(sw_kanban_app):
    """POST move-task with bad ID -> not found."""
    client = TestClient(sw_kanban_app["app"])
    d = sw_kanban_app["domain_name"]
    response = client.post(f"/sw/{d}/board/move-task", data={
        "task_id": 9999,
        "new_status": "Doing",
    })
    assert response.status_code == 200
    assert "not found" in response.text


# ====================================================================
# Delete Task Tests
# ====================================================================


def test_sw_board_delete_task(sw_kanban_app):
    """POST delete-task -> success, task gone."""
    client = TestClient(sw_kanban_app["app"])
    d = sw_kanban_app["domain_name"]
    sw = sw_kanban_app["sw"]
    tid = sw_kanban_app["task1"].swtask_id

    response = client.post(f"/sw/{d}/board/delete-task", data={"task_id": tid})
    assert response.status_code == 200
    assert "deleted" in response.text
    assert response.headers.get("hx-trigger") == "refresh-board"
    assert sw.get_swtask_by_id(tid) is None


def test_sw_board_delete_task_not_found(sw_kanban_app):
    """POST delete-task with bad ID -> not found."""
    client = TestClient(sw_kanban_app["app"])
    d = sw_kanban_app["domain_name"]
    response = client.post(f"/sw/{d}/board/delete-task", data={"task_id": 9999})
    assert response.status_code == 200
    assert "not found" in response.text


# ====================================================================
# Card Content Tests
# ====================================================================


def test_sw_board_card_content(sw_kanban_app):
    """Cards show guardrail badge and story name."""
    client = TestClient(sw_kanban_app["app"])
    d = sw_kanban_app["domain_name"]
    response = client.get(f"/sw/{d}/board/columns")
    assert response.status_code == 200
    # Guardrail badge — tasks inherit PRODUCTION from epic
    assert "PRODUCTION" in response.text
    # Story name on story-assigned task
    assert "Story1" in response.text
    # Direct-on-epic indicator
    assert "Direct on epic" in response.text
