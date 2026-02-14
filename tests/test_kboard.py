#!/usr/bin/env python
"""Tests for kanban board routes."""
from pathlib import Path
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
def full_app_create(tmp_path):
    domain_name = "domain1"
    domain_db_name = f"{domain_name}.db"
    db_path = Path(tmp_path) / domain_db_name
    ModelDB(tmp_path, name_override=domain_db_name, autocreate=True)
    config = {
        "databases": {
            domain_name: {
                "path": str(db_path),
                "description": "Test domain 1"
            }
        }
    }
    config_path = tmp_path / "config.json"
    with open(config_path, "w") as f:
        json.dump(config, f)

    server = DPMServer(config_path)
    dpm_manager = server.dpm_manager
    domain = dpm_manager.domain_catalog.pmdb_domains[domain_name]
    return dict(app=server.app,
                domain_name=domain_name,
                db=domain.db,
                dpm_manager=dpm_manager)


def _create_project(client, domain, name, description=""):
    return client.post(f"/{domain}/project/new",
                       data={'name': name, 'description': description})


def _create_phase(client, domain, project_id, name, description=""):
    return client.post(f"/{domain}/project/{project_id}/phase/new",
                       data={'name': name, 'description': description})


def _create_task(client, domain, phase_id, name, status="ToDo", description=""):
    return client.post(f"/{domain}/phase/{phase_id}/task/new",
                       data={'name': name, 'status': status, 'description': description})


def _create_project_task(client, domain, project_id, name, status="ToDo", description=""):
    return client.post(f"/{domain}/project/{project_id}/task/new",
                       data={'name': name, 'status': status, 'description': description})


# ====================================================================
# /board auto-redirect
# ====================================================================

def test_board_auto_redirect_no_context(full_app_create):
    """GET /board with no last-accessed state redirects to domain board."""
    setup = full_app_create
    domain = setup['domain_name']
    client = TestClient(setup['app'], follow_redirects=False)

    resp = client.get("/board")
    assert resp.status_code == 307
    assert f"/{domain}/board" in resp.headers["location"]


def test_board_auto_redirect_with_project(full_app_create):
    """GET /board after visiting a project redirects with project_id param."""
    setup = full_app_create
    db: ModelDB = setup['db']
    domain = setup['domain_name']
    client = TestClient(setup['app'], follow_redirects=False)

    # Create and visit a project to set last-accessed state
    _create_project(client, domain, "board_proj")
    project = db.get_project_by_name("board_proj")
    # Visit the project detail to set last_project
    TestClient(setup['app']).get(f"/{domain}/project/{project.project_id}")

    resp = client.get("/board")
    assert resp.status_code == 307
    assert f"project_id={project.project_id}" in resp.headers["location"]


def test_board_auto_redirect_with_phase(full_app_create):
    """GET /board after visiting a phase redirects with project_id and phase_id."""
    setup = full_app_create
    db: ModelDB = setup['db']
    domain = setup['domain_name']
    client = TestClient(setup['app'], follow_redirects=False)

    _create_project(client, domain, "board_proj2")
    project = db.get_project_by_name("board_proj2")
    _create_phase(client, domain, project.project_id, "board_phase")
    phase = db.get_phase_by_name("board_phase")
    # Visit the phase detail to set last_phase
    TestClient(setup['app']).get(f"/{domain}/phase/{phase.phase_id}")

    resp = client.get("/board")
    assert resp.status_code == 307
    loc = resp.headers["location"]
    assert f"project_id={project.project_id}" in loc
    assert f"phase_id={phase.phase_id}" in loc


# ====================================================================
# /{domain}/board
# ====================================================================

def test_board_page_no_filter(full_app_create):
    """GET /{domain}/board renders the board page (full and HTMX fragment)."""
    setup = full_app_create
    domain = setup['domain_name']
    client = TestClient(setup['app'])

    resp = client.get(f"/{domain}/board")
    assert resp.status_code == 200

    htmx_resp = client.get(f"/{domain}/board", headers=HTMX_HEADERS)
    assert_is_fragment(htmx_resp)


def test_board_page_with_project_filter(full_app_create):
    """GET /{domain}/board?project_id=X renders filtered board."""
    setup = full_app_create
    db: ModelDB = setup['db']
    domain = setup['domain_name']
    client = TestClient(setup['app'])

    _create_project(client, domain, "filter_proj")
    project = db.get_project_by_name("filter_proj")

    resp = client.get(f"/{domain}/board?project_id={project.project_id}")
    assert resp.status_code == 200

    htmx_resp = client.get(f"/{domain}/board?project_id={project.project_id}",
                           headers=HTMX_HEADERS)
    assert_is_fragment(htmx_resp)


def test_board_page_with_phase_filter(full_app_create):
    """GET /{domain}/board?project_id=X&phase_id=Y renders phase-filtered board."""
    setup = full_app_create
    db: ModelDB = setup['db']
    domain = setup['domain_name']
    client = TestClient(setup['app'])

    _create_project(client, domain, "pf_proj")
    project = db.get_project_by_name("pf_proj")
    _create_phase(client, domain, project.project_id, "pf_phase")
    phase = db.get_phase_by_name("pf_phase")

    resp = client.get(f"/{domain}/board?project_id={project.project_id}&phase_id={phase.phase_id}")
    assert resp.status_code == 200

    htmx_resp = client.get(
        f"/{domain}/board?project_id={project.project_id}&phase_id={phase.phase_id}",
        headers=HTMX_HEADERS)
    assert_is_fragment(htmx_resp)


# ====================================================================
# /{domain}/board/columns
# ====================================================================

def test_board_columns_all_tasks(full_app_create):
    """GET /{domain}/board/columns with no filter returns all tasks split by status."""
    setup = full_app_create
    db: ModelDB = setup['db']
    domain = setup['domain_name']
    client = TestClient(setup['app'])

    _create_project(client, domain, "col_proj")
    project = db.get_project_by_name("col_proj")
    _create_phase(client, domain, project.project_id, "col_phase")
    phase = db.get_phase_by_name("col_phase")

    _create_task(client, domain, phase.phase_id, "todo_task")
    _create_task(client, domain, phase.phase_id, "doing_task")
    _create_task(client, domain, phase.phase_id, "done_task")

    # Move tasks to different statuses via move-task
    doing = db.get_task_by_name("doing_task")
    done = db.get_task_by_name("done_task")
    client.post(f"/{domain}/board/move-task",
                data={'task_id': str(doing.task_id), 'new_status': 'InProgress'})
    client.post(f"/{domain}/board/move-task",
                data={'task_id': str(done.task_id), 'new_status': 'Done'})

    resp = client.get(f"/{domain}/board/columns")
    assert resp.status_code == 200
    assert "todo_task" in resp.text
    assert "doing_task" in resp.text
    assert "done_task" in resp.text


def test_board_columns_project_filter(full_app_create):
    """GET /{domain}/board/columns?project_id=X returns only that project's tasks."""
    setup = full_app_create
    db: ModelDB = setup['db']
    domain = setup['domain_name']
    client = TestClient(setup['app'])

    # Project A with a task
    _create_project(client, domain, "col_projA")
    projA = db.get_project_by_name("col_projA")
    _create_phase(client, domain, projA.project_id, "col_phaseA")
    phaseA = db.get_phase_by_name("col_phaseA")
    _create_task(client, domain, phaseA.phase_id, "taskA")

    # Project B with a task
    _create_project(client, domain, "col_projB")
    projB = db.get_project_by_name("col_projB")
    _create_project_task(client, domain, projB.project_id, "taskB")

    resp = client.get(f"/{domain}/board/columns?project_id={projA.project_id}")
    assert resp.status_code == 200
    assert "taskA" in resp.text
    assert "taskB" not in resp.text


def test_board_columns_phase_filter(full_app_create):
    """GET /{domain}/board/columns?phase_id=X returns only that phase's tasks."""
    setup = full_app_create
    db: ModelDB = setup['db']
    domain = setup['domain_name']
    client = TestClient(setup['app'])

    _create_project(client, domain, "col_ph_proj")
    project = db.get_project_by_name("col_ph_proj")
    _create_phase(client, domain, project.project_id, "phaseX")
    _create_phase(client, domain, project.project_id, "phaseY")
    phaseX = db.get_phase_by_name("phaseX")
    phaseY = db.get_phase_by_name("phaseY")

    _create_task(client, domain, phaseX.phase_id, "taskX")
    _create_task(client, domain, phaseY.phase_id, "taskY")

    resp = client.get(f"/{domain}/board/columns?phase_id={phaseX.phase_id}")
    assert resp.status_code == 200
    assert "taskX" in resp.text
    assert "taskY" not in resp.text


def test_board_columns_empty(full_app_create):
    """GET /{domain}/board/columns with no tasks returns 200."""
    setup = full_app_create
    domain = setup['domain_name']
    client = TestClient(setup['app'])

    resp = client.get(f"/{domain}/board/columns")
    assert resp.status_code == 200


# ====================================================================
# /{domain}/board/phase-options
# ====================================================================

def test_board_phase_options_with_phases(full_app_create):
    """GET /{domain}/board/phase-options returns phase list items."""
    setup = full_app_create
    db: ModelDB = setup['db']
    domain = setup['domain_name']
    client = TestClient(setup['app'])

    _create_project(client, domain, "po_proj")
    project = db.get_project_by_name("po_proj")
    _create_phase(client, domain, project.project_id, "po_phase1")
    _create_phase(client, domain, project.project_id, "po_phase2")

    resp = client.get(f"/{domain}/board/phase-options?project_id={project.project_id}")
    assert resp.status_code == 200
    assert "All Phases" in resp.text
    assert "po_phase1" in resp.text
    assert "po_phase2" in resp.text


def test_board_phase_options_no_phases(full_app_create):
    """GET /{domain}/board/phase-options for project with no phases."""
    setup = full_app_create
    db: ModelDB = setup['db']
    domain = setup['domain_name']
    client = TestClient(setup['app'])

    _create_project(client, domain, "nophase_proj")
    project = db.get_project_by_name("nophase_proj")

    resp = client.get(f"/{domain}/board/phase-options?project_id={project.project_id}")
    assert resp.status_code == 200
    assert "No phases" in resp.text


def test_board_phase_options_bad_project(full_app_create):
    """GET /{domain}/board/phase-options with nonexistent project_id."""
    setup = full_app_create
    domain = setup['domain_name']
    client = TestClient(setup['app'])

    resp = client.get(f"/{domain}/board/phase-options?project_id=9999")
    assert resp.status_code == 200
    assert "No phases found" in resp.text


# ====================================================================
# /{domain}/board/move-task
# ====================================================================

def test_move_task_success(full_app_create):
    """POST move-task changes task status and returns refresh-board trigger."""
    setup = full_app_create
    db: ModelDB = setup['db']
    domain = setup['domain_name']
    client = TestClient(setup['app'])

    _create_project(client, domain, "mv_proj")
    project = db.get_project_by_name("mv_proj")
    _create_phase(client, domain, project.project_id, "mv_phase")
    phase = db.get_phase_by_name("mv_phase")
    _create_task(client, domain, phase.phase_id, "mv_task", status="ToDo")
    task = db.get_task_by_name("mv_task")

    # Move ToDo -> InProgress
    resp = client.post(f"/{domain}/board/move-task",
                       data={'task_id': str(task.task_id), 'new_status': 'InProgress'})
    assert resp.status_code == 200
    assert "refresh-board" in resp.headers.get("HX-Trigger", "")

    updated = db.get_task_by_id(task.task_id)
    assert updated.status == "InProgress"

    # Move InProgress -> Done
    resp2 = client.post(f"/{domain}/board/move-task",
                        data={'task_id': str(task.task_id), 'new_status': 'Done'})
    assert resp2.status_code == 200
    assert "refresh-board" in resp2.headers.get("HX-Trigger", "")

    updated2 = db.get_task_by_id(task.task_id)
    assert updated2.status == "Done"

    # Move Done -> ToDo
    resp3 = client.post(f"/{domain}/board/move-task",
                        data={'task_id': str(task.task_id), 'new_status': 'ToDo'})
    assert resp3.status_code == 200
    updated3 = db.get_task_by_id(task.task_id)
    assert updated3.status == "ToDo"


def test_move_task_blocked(full_app_create):
    """POST move-task to InProgress/Done is rejected when task has active blockers."""
    setup = full_app_create
    db: ModelDB = setup['db']
    domain = setup['domain_name']
    client = TestClient(setup['app'])

    _create_project(client, domain, "blk_proj")
    project = db.get_project_by_name("blk_proj")
    _create_phase(client, domain, project.project_id, "blk_phase")
    phase = db.get_phase_by_name("blk_phase")

    _create_task(client, domain, phase.phase_id, "blocked_task", status="ToDo")
    _create_task(client, domain, phase.phase_id, "blocker_task", status="ToDo")
    blocked = db.get_task_by_name("blocked_task")
    blocker = db.get_task_by_name("blocker_task")

    # Add blocker relationship
    blocked.add_blocker(blocker)

    # Try to move blocked task to InProgress — should be rejected
    resp = client.post(f"/{domain}/board/move-task",
                       data={'task_id': str(blocked.task_id), 'new_status': 'InProgress'})
    assert resp.status_code == 200
    assert "Cannot move" in resp.text
    assert "blocker_task" in resp.text
    assert "HX-Trigger" not in resp.headers

    # Verify status unchanged
    still_blocked = db.get_task_by_id(blocked.task_id)
    assert still_blocked.status == "ToDo"

    # Try to move to Done — also rejected
    resp2 = client.post(f"/{domain}/board/move-task",
                        data={'task_id': str(blocked.task_id), 'new_status': 'Done'})
    assert resp2.status_code == 200
    assert "Cannot move" in resp2.text

    # Complete the blocker, then moving should succeed
    blocker.status = "Done"
    blocker.save()

    resp3 = client.post(f"/{domain}/board/move-task",
                        data={'task_id': str(blocked.task_id), 'new_status': 'InProgress'})
    assert resp3.status_code == 200
    assert "refresh-board" in resp3.headers.get("HX-Trigger", "")
    assert db.get_task_by_id(blocked.task_id).status == "InProgress"


def test_move_task_not_found(full_app_create):
    """POST move-task with nonexistent task_id returns failure message."""
    setup = full_app_create
    domain = setup['domain_name']
    client = TestClient(setup['app'])

    resp = client.post(f"/{domain}/board/move-task",
                       data={'task_id': '9999', 'new_status': 'InProgress'})
    assert resp.status_code == 200
    assert "Task not found" in resp.text


# ====================================================================
# /{domain}/task/{id}/delete-board
# ====================================================================

def test_delete_board_success(full_app_create):
    """POST delete-board removes task and returns refresh-board trigger."""
    setup = full_app_create
    db: ModelDB = setup['db']
    domain = setup['domain_name']
    client = TestClient(setup['app'])

    _create_project(client, domain, "del_proj")
    project = db.get_project_by_name("del_proj")
    _create_phase(client, domain, project.project_id, "del_phase")
    phase = db.get_phase_by_name("del_phase")
    _create_task(client, domain, phase.phase_id, "del_task")
    task = db.get_task_by_name("del_task")

    resp = client.post(f"/{domain}/task/{task.task_id}/delete-board")
    assert resp.status_code == 200
    assert "deleted" in resp.text.lower()
    assert "refresh-board" in resp.headers.get("HX-Trigger", "")

    assert db.get_task_by_id(task.task_id) is None


def test_delete_board_not_found(full_app_create):
    """POST delete-board with nonexistent task_id returns failure message."""
    setup = full_app_create
    domain = setup['domain_name']
    client = TestClient(setup['app'])

    resp = client.post(f"/{domain}/task/9999/delete-board")
    assert resp.status_code == 200
    assert "Task not found" in resp.text


# ====================================================================
# /{domain}/project/{id}/phases-options (HTMX helper)
# ====================================================================

def test_phases_options_with_phases(full_app_create):
    """GET phases-options returns option elements for each phase."""
    setup = full_app_create
    db: ModelDB = setup['db']
    domain = setup['domain_name']
    client = TestClient(setup['app'])

    _create_project(client, domain, "opt_proj")
    project = db.get_project_by_name("opt_proj")
    _create_phase(client, domain, project.project_id, "opt_phase1")
    _create_phase(client, domain, project.project_id, "opt_phase2")

    resp = client.get(f"/{domain}/project/{project.project_id}/phases-options")
    assert resp.status_code == 200
    assert "opt_phase1" in resp.text
    assert "opt_phase2" in resp.text
    assert "None (directly under project)" in resp.text


def test_phases_options_selected(full_app_create):
    """GET phases-options with selected_phase_id marks the correct option."""
    setup = full_app_create
    db: ModelDB = setup['db']
    domain = setup['domain_name']
    client = TestClient(setup['app'])

    _create_project(client, domain, "sel_proj")
    project = db.get_project_by_name("sel_proj")
    _create_phase(client, domain, project.project_id, "sel_phase")
    phase = db.get_phase_by_name("sel_phase")

    resp = client.get(
        f"/{domain}/project/{project.project_id}/phases-options"
        f"?selected_phase_id={phase.phase_id}")
    assert resp.status_code == 200
    assert "selected" in resp.text


def test_phases_options_no_phases(full_app_create):
    """GET phases-options for project with no phases returns only the None option."""
    setup = full_app_create
    db: ModelDB = setup['db']
    domain = setup['domain_name']
    client = TestClient(setup['app'])

    _create_project(client, domain, "empty_proj")
    project = db.get_project_by_name("empty_proj")

    resp = client.get(f"/{domain}/project/{project.project_id}/phases-options")
    assert resp.status_code == 200
    assert "None (directly under project)" in resp.text


def test_phases_options_bad_project(full_app_create):
    """GET phases-options with nonexistent project returns the None option."""
    setup = full_app_create
    domain = setup['domain_name']
    client = TestClient(setup['app'])

    resp = client.get(f"/{domain}/project/9999/phases-options")
    assert resp.status_code == 200
    assert "None (directly under project)" in resp.text


# ====================================================================
# Error path coverage — force exceptions via DB-level manipulation
# ====================================================================

def test_edit_modal_save_error(full_app_create):
    """POST edit-modal returns error when save fails due to name conflict."""
    setup = full_app_create
    db: ModelDB = setup['db']
    domain = setup['domain_name']
    client = TestClient(setup['app'])

    _create_project(client, domain, "ed_err_proj")
    project = db.get_project_by_name("ed_err_proj")
    _create_phase(client, domain, project.project_id, "ed_err_phase")
    phase = db.get_phase_by_name("ed_err_phase")
    _create_task(client, domain, phase.phase_id, "ed_task_a")
    _create_task(client, domain, phase.phase_id, "ed_task_b")
    task_a = db.get_task_by_name("ed_task_a")

    # Submit edit-modal with task_a's name changed to "ed_task_b" — dup name
    resp = client.post(
        f"/{domain}/task/{task_a.task_id}/edit-modal",
        data={
            'name': 'ed_task_b',
            'status': 'ToDo',
            'description': '',
            'project_id': str(project.project_id),
            'phase_id': str(phase.phase_id),
        })
    assert resp.status_code == 200
    assert "Failed to update task" in resp.text
