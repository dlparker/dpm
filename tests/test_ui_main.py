#!/usr/bin/env python
import sys
import os
from pathlib import Path
import asyncio
import shutil
import time
import datetime
from collections import defaultdict
import shutil
import json
import pytest
# test_main.py
from fastapi.testclient import TestClient
from dpm.fastapi.server import DPMServer

from dpm.store.models import Task, Project, Phase, Task
from dpm.store.wrappers import ModelDB

HTMX_HEADERS = {"HX-Request": "true"}


def assert_is_fragment(response):
    """Verify an HTMX response is a fragment (not a full HTML page)."""
    assert response.status_code == 200
    assert "<!DOCTYPE" not in response.text


@pytest.fixture
def full_app_create(tmp_path):
    # Create domain1 with test data
    domain_name = "domain1"
    domain_db_name = f"{domain_name}.db"
    db_path = Path(tmp_path) / domain_db_name
    db1 = ModelDB(tmp_path, name_override=domain_db_name, autocreate=True)
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
                db_dir=domain.db_path.parent,
                target_db_name=domain.db_path.name)

def test_project_create_read_delete(full_app_create):
    setup_dict = full_app_create
    db: ModelDB = setup_dict['db']
    domain_name = setup_dict['domain_name']
    client = TestClient(setup_dict['app'])

    # --- Create top-level project ---
    project_create_url = f"/{domain_name}/project/new"
    create_response = client.post(project_create_url,
                                  data={
                                      'name': "top_project",
                                      'description': "top project"
                                  })
    assert create_response.status_code == 200
    assert "alert-success" in create_response.text
    assert "top_project" in create_response.text

    proj_1 = db.get_project_by_name("top_project")
    assert proj_1 is not None
    assert proj_1.description == "top project"
    assert proj_1.parent_id is None

    # --- Create child project under top_project ---
    create_child_response = client.post(project_create_url,
                                        data={
                                            'name': "child_project",
                                            'description': "child of top",
                                            'parent_id': str(proj_1.project_id)
                                        })
    assert create_child_response.status_code == 200
    assert "alert-success" in create_child_response.text

    proj_2 = db.get_project_by_name("child_project")
    assert proj_2 is not None
    assert proj_2.parent_id == proj_1.project_id

    # --- Read: project list page ---
    list_url = f"/{domain_name}/projects"
    list_response = client.get(list_url)
    assert list_response.status_code == 200
    assert "top_project" in list_response.text
    assert "child_project" in list_response.text

    # HTMX: project list returns fragment
    htmx_list = client.get(list_url, headers=HTMX_HEADERS)
    assert_is_fragment(htmx_list)
    assert "top_project" in htmx_list.text

    # --- Read: project detail page ---
    detail_url = f"/{domain_name}/project/{proj_1.project_id}"
    detail_response = client.get(detail_url)
    assert detail_response.status_code == 200
    assert "top_project" in detail_response.text

    # HTMX: project detail returns fragment
    htmx_detail = client.get(detail_url, headers=HTMX_HEADERS)
    assert_is_fragment(htmx_detail)
    assert "top_project" in htmx_detail.text

    # --- Read: project children page (shows phases and direct tasks, not sub-projects) ---
    children_url = f"/{domain_name}/project/{proj_1.project_id}/children"
    children_response = client.get(children_url)
    assert children_response.status_code == 200
    # top_project has no phases or tasks yet, so expect the empty message
    assert "No phases or tasks" in children_response.text

    # HTMX: project children returns fragment
    htmx_children = client.get(children_url, headers=HTMX_HEADERS)
    assert_is_fragment(htmx_children)

    # --- Read: create form (GET) renders ---
    create_form_response = client.get(project_create_url)
    assert create_form_response.status_code == 200

    # HTMX: create form returns fragment
    htmx_create = client.get(project_create_url, headers=HTMX_HEADERS)
    assert_is_fragment(htmx_create)

    # --- Delete: confirmation page ---
    delete_confirm_url = f"/{domain_name}/project/{proj_1.project_id}/delete"
    delete_confirm_response = client.get(delete_confirm_url)
    assert delete_confirm_response.status_code == 200
    assert "top_project" in delete_confirm_response.text

    # HTMX: delete confirmation returns fragment
    htmx_delete = client.get(delete_confirm_url, headers=HTMX_HEADERS)
    assert_is_fragment(htmx_delete)
    assert "top_project" in htmx_delete.text

    # --- Delete: submit ---
    delete_response = client.post(delete_confirm_url)
    assert delete_response.status_code == 200
    assert "alert-success" in delete_response.text
    assert "deleted" in delete_response.text.lower()

    # Verify project and child are both gone (cascade)
    assert db.get_project_by_id(proj_1.project_id) is None
    assert db.get_project_by_id(proj_2.project_id) is None


# ====================================================================
# Stage 2: Phase Create, Read, Delete
# ====================================================================

def test_phase_create_read_delete(full_app_create):
    setup_dict = full_app_create
    db: ModelDB = setup_dict['db']
    domain_name = setup_dict['domain_name']
    client = TestClient(setup_dict['app'])

    # --- Create a project first ---
    client.post(f"/{domain_name}/project/new",
                data={'name': "phase_test_project", 'description': "for phase tests"})
    project = db.get_project_by_name("phase_test_project")
    assert project is not None

    # --- Create phase ---
    phase_create_url = f"/{domain_name}/project/{project.project_id}/phase/new"
    create_response = client.post(phase_create_url,
                                  data={'name': "test_phase", 'description': "a test phase"})
    assert create_response.status_code == 200
    assert "alert-success" in create_response.text

    phase = db.get_phase_by_name("test_phase")
    assert phase is not None
    assert phase.description == "a test phase"
    assert phase.project_id == project.project_id

    # --- Read: phase detail page ---
    detail_url = f"/{domain_name}/phase/{phase.phase_id}"
    detail_response = client.get(detail_url)
    assert detail_response.status_code == 200
    assert "test_phase" in detail_response.text

    # HTMX: phase detail returns fragment
    htmx_detail = client.get(detail_url, headers=HTMX_HEADERS)
    assert_is_fragment(htmx_detail)
    assert "test_phase" in htmx_detail.text

    # --- Read: project children page shows the phase ---
    children_url = f"/{domain_name}/project/{project.project_id}/children"
    children_response = client.get(children_url)
    assert children_response.status_code == 200
    assert "test_phase" in children_response.text

    # HTMX: project children returns fragment
    htmx_children = client.get(children_url, headers=HTMX_HEADERS)
    assert_is_fragment(htmx_children)
    assert "test_phase" in htmx_children.text

    # --- Read: phase tasks page (empty) ---
    tasks_url = f"/{domain_name}/phase/{phase.phase_id}/tasks"
    tasks_response = client.get(tasks_url)
    assert tasks_response.status_code == 200

    # HTMX: phase tasks returns fragment
    htmx_tasks = client.get(tasks_url, headers=HTMX_HEADERS)
    assert_is_fragment(htmx_tasks)

    # --- Read: create form (GET) renders ---
    create_form_response = client.get(phase_create_url)
    assert create_form_response.status_code == 200

    # HTMX: create form returns fragment
    htmx_create = client.get(phase_create_url, headers=HTMX_HEADERS)
    assert_is_fragment(htmx_create)

    # --- Delete: confirmation page ---
    delete_confirm_url = f"/{domain_name}/phase/{phase.phase_id}/delete"
    delete_confirm_response = client.get(delete_confirm_url)
    assert delete_confirm_response.status_code == 200
    assert "test_phase" in delete_confirm_response.text

    # HTMX: delete confirmation returns fragment
    htmx_delete = client.get(delete_confirm_url, headers=HTMX_HEADERS)
    assert_is_fragment(htmx_delete)
    assert "test_phase" in htmx_delete.text

    # --- Delete: submit ---
    delete_response = client.post(delete_confirm_url)
    assert delete_response.status_code == 200
    assert "alert-success" in delete_response.text
    assert "deleted" in delete_response.text.lower()

    assert db.get_phase_by_id(phase.phase_id) is None


# ====================================================================
# Stage 3: Task Create, Read, Delete
# ====================================================================

def test_task_create_read_delete_in_project(full_app_create):
    setup_dict = full_app_create
    db: ModelDB = setup_dict['db']
    domain_name = setup_dict['domain_name']
    client = TestClient(setup_dict['app'])

    # --- Create a project ---
    client.post(f"/{domain_name}/project/new",
                data={'name': "task_proj", 'description': "for task tests"})
    project = db.get_project_by_name("task_proj")
    assert project is not None

    # --- Create task directly under project (no phase) ---
    task_create_url = f"/{domain_name}/project/{project.project_id}/task/new"
    create_response = client.post(task_create_url,
                                  data={
                                      'name': "proj_task",
                                      'status': "ToDo",
                                      'description': "a direct task"
                                  })
    assert create_response.status_code == 200
    assert "alert-success" in create_response.text

    task = db.get_task_by_name("proj_task")
    assert task is not None
    assert task.project_id == project.project_id
    assert task.phase_id is None
    assert task.description == "a direct task"

    # --- Read: task detail page ---
    detail_url = f"/{domain_name}/task/{task.task_id}"
    detail_response = client.get(detail_url)
    assert detail_response.status_code == 200
    assert "proj_task" in detail_response.text

    # HTMX: task detail returns fragment
    htmx_detail = client.get(detail_url, headers=HTMX_HEADERS)
    assert_is_fragment(htmx_detail)
    assert "proj_task" in htmx_detail.text

    # --- Read: create form (GET) renders ---
    create_form_response = client.get(task_create_url)
    assert create_form_response.status_code == 200

    # HTMX: task create form returns fragment
    htmx_create = client.get(task_create_url, headers=HTMX_HEADERS)
    assert_is_fragment(htmx_create)

    # --- Delete: confirmation page ---
    delete_confirm_url = f"/{domain_name}/task/{task.task_id}/delete"
    delete_confirm_response = client.get(delete_confirm_url)
    assert delete_confirm_response.status_code == 200
    assert "proj_task" in delete_confirm_response.text

    # HTMX: delete confirmation returns fragment
    htmx_delete = client.get(delete_confirm_url, headers=HTMX_HEADERS)
    assert_is_fragment(htmx_delete)
    assert "proj_task" in htmx_delete.text

    # --- Delete: submit ---
    delete_response = client.post(delete_confirm_url)
    assert delete_response.status_code == 200
    assert "alert-success" in delete_response.text
    assert "deleted" in delete_response.text.lower()

    assert db.get_task_by_id(task.task_id) is None


def test_task_create_read_delete_in_phase(full_app_create):
    setup_dict = full_app_create
    db: ModelDB = setup_dict['db']
    domain_name = setup_dict['domain_name']
    client = TestClient(setup_dict['app'])

    # --- Create project + phase ---
    client.post(f"/{domain_name}/project/new",
                data={'name': "phase_task_proj", 'description': ""})
    project = db.get_project_by_name("phase_task_proj")
    assert project is not None

    client.post(f"/{domain_name}/project/{project.project_id}/phase/new",
                data={'name': "task_phase", 'description': ""})
    phase = db.get_phase_by_name("task_phase")
    assert phase is not None

    # --- Create task under phase ---
    task_create_url = f"/{domain_name}/phase/{phase.phase_id}/task/new"
    create_response = client.post(task_create_url,
                                  data={
                                      'name': "phase_task",
                                      'status': "ToDo",
                                      'description': "task in phase"
                                  })
    assert create_response.status_code == 200
    assert "alert-success" in create_response.text

    task = db.get_task_by_name("phase_task")
    assert task is not None
    assert task.project_id == project.project_id
    assert task.phase_id == phase.phase_id

    # --- Read: phase tasks page shows the task ---
    tasks_url = f"/{domain_name}/phase/{phase.phase_id}/tasks"
    tasks_response = client.get(tasks_url)
    assert tasks_response.status_code == 200
    assert "phase_task" in tasks_response.text

    # HTMX: phase tasks returns fragment with task
    htmx_tasks = client.get(tasks_url, headers=HTMX_HEADERS)
    assert_is_fragment(htmx_tasks)
    assert "phase_task" in htmx_tasks.text

    # --- Read: task detail page ---
    detail_url = f"/{domain_name}/task/{task.task_id}"
    detail_response = client.get(detail_url)
    assert detail_response.status_code == 200
    assert "phase_task" in detail_response.text

    # HTMX: task detail returns fragment
    htmx_detail = client.get(detail_url, headers=HTMX_HEADERS)
    assert_is_fragment(htmx_detail)
    assert "phase_task" in htmx_detail.text

    # --- Delete: submit ---
    delete_url = f"/{domain_name}/task/{task.task_id}/delete"
    delete_response = client.post(delete_url)
    assert delete_response.status_code == 200
    assert "alert-success" in delete_response.text

    assert db.get_task_by_id(task.task_id) is None


# ====================================================================
# Stage 4: Project Update (page + modal)
# ====================================================================

def test_project_edit_page(full_app_create):
    setup_dict = full_app_create
    db: ModelDB = setup_dict['db']
    domain_name = setup_dict['domain_name']
    client = TestClient(setup_dict['app'])

    # --- Create project ---
    client.post(f"/{domain_name}/project/new",
                data={'name': "edit_proj", 'description': "original desc"})
    project = db.get_project_by_name("edit_proj")
    assert project is not None

    # --- GET edit page (form pre-populated) ---
    edit_url = f"/{domain_name}/project/{project.project_id}/edit"
    edit_response = client.get(edit_url)
    assert edit_response.status_code == 200
    assert "edit_proj" in edit_response.text

    # HTMX: project edit returns fragment
    htmx_edit = client.get(edit_url, headers=HTMX_HEADERS)
    assert_is_fragment(htmx_edit)
    assert "edit_proj" in htmx_edit.text

    # --- POST edit with modified name/description ---
    edit_submit_response = client.post(edit_url,
                                       data={
                                           'name': "renamed_proj",
                                           'description': "updated desc",
                                           'parent_id': ""
                                       })
    assert edit_submit_response.status_code == 200
    assert "alert-success" in edit_submit_response.text

    updated = db.get_project_by_id(project.project_id)
    assert updated is not None
    assert updated.name == "renamed_proj"
    assert updated.description == "updated desc"

    # --- Test self-referential parent rejection ---
    self_parent_response = client.post(edit_url,
                                        data={
                                            'name': "renamed_proj",
                                            'description': "updated desc",
                                            'parent_id': str(project.project_id)
                                        })
    assert self_parent_response.status_code == 200
    assert "cannot be its own parent" in self_parent_response.text.lower()


def test_project_edit_modal(full_app_create):
    setup_dict = full_app_create
    db: ModelDB = setup_dict['db']
    domain_name = setup_dict['domain_name']
    client = TestClient(setup_dict['app'])

    # --- Create project ---
    client.post(f"/{domain_name}/project/new",
                data={'name': "modal_proj", 'description': "modal desc"})
    project = db.get_project_by_name("modal_proj")
    assert project is not None

    # --- GET edit-modal page ---
    modal_url = f"/{domain_name}/project/{project.project_id}/edit-modal"
    modal_response = client.get(modal_url)
    assert modal_response.status_code == 200

    # --- POST edit-modal with changes ---
    modal_submit_response = client.post(modal_url,
                                         data={
                                             'name': "modal_renamed",
                                             'description': "modal updated",
                                             'parent_id': ""
                                         })
    assert modal_submit_response.status_code == 200
    assert "close-modal" in modal_submit_response.headers.get("HX-Trigger", "")

    updated = db.get_project_by_id(project.project_id)
    assert updated is not None
    assert updated.name == "modal_renamed"
    assert updated.description == "modal updated"


# ====================================================================
# Stage 5: Phase Update (page + modal)
# ====================================================================

def test_phase_edit_page(full_app_create):
    setup_dict = full_app_create
    db: ModelDB = setup_dict['db']
    domain_name = setup_dict['domain_name']
    client = TestClient(setup_dict['app'])

    # --- Create project + phase ---
    client.post(f"/{domain_name}/project/new",
                data={'name': "phase_edit_proj", 'description': ""})
    project = db.get_project_by_name("phase_edit_proj")
    assert project is not None

    client.post(f"/{domain_name}/project/{project.project_id}/phase/new",
                data={'name': "edit_phase", 'description': "original phase desc"})
    phase = db.get_phase_by_name("edit_phase")
    assert phase is not None

    # --- GET edit page ---
    edit_url = f"/{domain_name}/phase/{phase.phase_id}/edit"
    edit_response = client.get(edit_url)
    assert edit_response.status_code == 200
    assert "edit_phase" in edit_response.text

    # HTMX: phase edit returns fragment
    htmx_edit = client.get(edit_url, headers=HTMX_HEADERS)
    assert_is_fragment(htmx_edit)
    assert "edit_phase" in htmx_edit.text

    # --- POST edit with modified fields ---
    edit_submit_response = client.post(edit_url,
                                       data={
                                           'name': "renamed_phase",
                                           'description': "updated phase desc",
                                           'project_id': str(project.project_id)
                                       })
    assert edit_submit_response.status_code == 200
    assert "alert-success" in edit_submit_response.text

    updated = db.get_phase_by_id(phase.phase_id)
    assert updated is not None
    assert updated.name == "renamed_phase"
    assert updated.description == "updated phase desc"

    # --- Move phase to a different project ---
    client.post(f"/{domain_name}/project/new",
                data={'name': "phase_edit_proj_2", 'description': ""})
    project_2 = db.get_project_by_name("phase_edit_proj_2")
    assert project_2 is not None

    move_response = client.post(edit_url,
                                data={
                                    'name': "renamed_phase",
                                    'description': "updated phase desc",
                                    'project_id': str(project_2.project_id)
                                })
    assert move_response.status_code == 200
    assert "alert-success" in move_response.text

    moved = db.get_phase_by_id(phase.phase_id)
    assert moved is not None
    assert moved.project_id == project_2.project_id


def test_phase_edit_modal(full_app_create):
    setup_dict = full_app_create
    db: ModelDB = setup_dict['db']
    domain_name = setup_dict['domain_name']
    client = TestClient(setup_dict['app'])

    # --- Create project + phase ---
    client.post(f"/{domain_name}/project/new",
                data={'name': "modal_phase_proj", 'description': ""})
    project = db.get_project_by_name("modal_phase_proj")
    assert project is not None

    client.post(f"/{domain_name}/project/{project.project_id}/phase/new",
                data={'name': "modal_phase", 'description': "modal phase desc"})
    phase = db.get_phase_by_name("modal_phase")
    assert phase is not None

    # --- GET edit-modal page ---
    modal_url = f"/{domain_name}/phase/{phase.phase_id}/edit-modal"
    modal_response = client.get(modal_url)
    assert modal_response.status_code == 200

    # --- POST edit-modal with changes ---
    modal_submit_response = client.post(modal_url,
                                         data={
                                             'name': "modal_phase_renamed",
                                             'description': "modal phase updated",
                                             'project_id': str(project.project_id)
                                         })
    assert modal_submit_response.status_code == 200
    assert "close-modal" in modal_submit_response.headers.get("HX-Trigger", "")

    updated = db.get_phase_by_id(phase.phase_id)
    assert updated is not None
    assert updated.name == "modal_phase_renamed"
    assert updated.description == "modal phase updated"


# ====================================================================
# Stage 6: Task Update (page + modal)
# ====================================================================

def test_task_edit_page(full_app_create):
    setup_dict = full_app_create
    db: ModelDB = setup_dict['db']
    domain_name = setup_dict['domain_name']
    client = TestClient(setup_dict['app'])

    # --- Create project + phase + two tasks ---
    client.post(f"/{domain_name}/project/new",
                data={'name': "task_edit_proj", 'description': ""})
    project = db.get_project_by_name("task_edit_proj")
    assert project is not None

    client.post(f"/{domain_name}/project/{project.project_id}/phase/new",
                data={'name': "task_edit_phase", 'description': ""})
    phase = db.get_phase_by_name("task_edit_phase")
    assert phase is not None

    client.post(f"/{domain_name}/phase/{phase.phase_id}/task/new",
                data={'name': "edit_task_1", 'status': "ToDo", 'description': "first task"})
    task_1 = db.get_task_by_name("edit_task_1")
    assert task_1 is not None

    client.post(f"/{domain_name}/phase/{phase.phase_id}/task/new",
                data={'name': "edit_task_2", 'status': "ToDo", 'description': "second task"})
    task_2 = db.get_task_by_name("edit_task_2")
    assert task_2 is not None

    # --- GET edit page ---
    edit_url = f"/{domain_name}/task/{task_1.task_id}/edit"
    edit_response = client.get(edit_url)
    assert edit_response.status_code == 200
    assert "edit_task_1" in edit_response.text

    # HTMX: task edit returns fragment
    htmx_edit = client.get(edit_url, headers=HTMX_HEADERS)
    assert_is_fragment(htmx_edit)
    assert "edit_task_1" in htmx_edit.text

    # --- POST edit changing name, status, description ---
    edit_submit_response = client.post(edit_url,
                                       data={
                                           'name': "renamed_task_1",
                                           'status': "InProgress",
                                           'description': "updated task desc",
                                           'project_id': str(project.project_id),
                                           'phase_id': str(phase.phase_id)
                                       })
    assert edit_submit_response.status_code == 200
    assert "alert-success" in edit_submit_response.text

    updated = db.get_task_by_id(task_1.task_id)
    assert updated is not None
    assert updated.name == "renamed_task_1"
    assert updated.status == "InProgress"
    assert updated.description == "updated task desc"

    # --- POST edit adding blocker_ids ---
    blocker_response = client.post(edit_url,
                                   data={
                                       'name': "renamed_task_1",
                                       'status': "InProgress",
                                       'description': "updated task desc",
                                       'project_id': str(project.project_id),
                                       'phase_id': str(phase.phase_id),
                                       'blocker_ids': str(task_2.task_id)
                                   })
    assert blocker_response.status_code == 200
    assert "alert-success" in blocker_response.text

    blockers = updated.get_blockers(only_not_done=False)
    assert len(blockers) == 1
    assert blockers[0].task_id == task_2.task_id

    # --- POST edit removing blockers (submit without blocker_ids) ---
    remove_blocker_response = client.post(edit_url,
                                          data={
                                              'name': "renamed_task_1",
                                              'status': "InProgress",
                                              'description': "updated task desc",
                                              'project_id': str(project.project_id),
                                              'phase_id': str(phase.phase_id)
                                          })
    assert remove_blocker_response.status_code == 200
    assert "alert-success" in remove_blocker_response.text

    blockers_after = updated.get_blockers(only_not_done=False)
    assert len(blockers_after) == 0


def test_task_edit_modal(full_app_create):
    setup_dict = full_app_create
    db: ModelDB = setup_dict['db']
    domain_name = setup_dict['domain_name']
    client = TestClient(setup_dict['app'])

    # --- Create project + phase + two tasks ---
    client.post(f"/{domain_name}/project/new",
                data={'name': "modal_task_proj", 'description': ""})
    project = db.get_project_by_name("modal_task_proj")
    assert project is not None

    client.post(f"/{domain_name}/project/{project.project_id}/phase/new",
                data={'name': "modal_task_phase", 'description': ""})
    phase = db.get_phase_by_name("modal_task_phase")
    assert phase is not None

    client.post(f"/{domain_name}/phase/{phase.phase_id}/task/new",
                data={'name': "modal_task_1", 'status': "ToDo", 'description': "first"})
    task_1 = db.get_task_by_name("modal_task_1")
    assert task_1 is not None

    client.post(f"/{domain_name}/phase/{phase.phase_id}/task/new",
                data={'name': "modal_task_2", 'status': "ToDo", 'description': "second"})
    task_2 = db.get_task_by_name("modal_task_2")
    assert task_2 is not None

    # --- GET edit-modal page ---
    modal_url = f"/{domain_name}/task/{task_1.task_id}/edit-modal"
    modal_response = client.get(modal_url)
    assert modal_response.status_code == 200

    # --- POST edit-modal with changes including blocker ---
    modal_submit_response = client.post(modal_url,
                                         data={
                                             'name': "modal_renamed_task",
                                             'status': "InProgress",
                                             'description': "modal updated",
                                             'project_id': str(project.project_id),
                                             'phase_id': str(phase.phase_id),
                                             'blocker_ids': str(task_2.task_id)
                                         })
    assert modal_submit_response.status_code == 200
    hx_trigger = modal_submit_response.headers.get("HX-Trigger", "")
    assert "refresh-board" in hx_trigger
    assert "close-modal" in hx_trigger

    updated = db.get_task_by_id(task_1.task_id)
    assert updated is not None
    assert updated.name == "modal_renamed_task"
    assert updated.status == "InProgress"

    blockers = updated.get_blockers(only_not_done=False)
    assert len(blockers) == 1
    assert blockers[0].task_id == task_2.task_id
