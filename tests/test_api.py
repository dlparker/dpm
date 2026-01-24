#!/usr/bin/env python
"""Tests for the FastAPI REST API."""
from pathlib import Path
import json
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from dpm.store.models import ModelDB, DomainCatalog
from dpm.fastapi.cantons.pm.api_router import PMDBAPIService


@pytest.fixture
def client():
    """Create a test client with a temporary database."""
    config_dir = Path("/tmp/test_api_config")
    db_name = "test_api_db.sqlite"
    db_path = config_dir / db_name
    if db_path.exists():
        db_path.unlink()

    # Create the database
    db = ModelDB(store_dir=str(config_dir), name_override=db_name, autocreate=True)
    config_path = config_dir / "config.json"
    config_dir.mkdir(exist_ok=True)
    cdict = {
        "databases": {
            "default": {
                "path": f"./{db_name}",
                "description": "test database one"
            }
        }
    }

    with open(config_path, 'w') as f:
        f.write(json.dumps(cdict))

    class FakeServer:

        def __init__(self, config_path):
            self.domain_catalog = DomainCatalog.from_json_config(config_path)
            
    service = PMDBAPIService(FakeServer(config_path))

    # Create app with service router
    app = FastAPI()
    app.include_router(service.become_router(), prefix="/pm/api")

    with TestClient(app) as client:
        yield client

    # Cleanup
    db.close()
    if db_path.exists():
        db_path.unlink()


# ============================================================================
# Project tests
# ============================================================================

def test_create_project(client):
    response = client.post("/pm/api/default/projects", json={
        "name": "Test Project",
        "description": "A test project"
    })
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Project"
    assert data["description"] == "A test project"
    assert data["project_id"] is not None


def test_list_projects(client):
    # Create some projects
    client.post("/pm/api/default/projects", json={"name": "Project 1"})
    client.post("/pm/api/default/projects", json={"name": "Project 2"})

    response = client.get("/pm/api/default/projects")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


def test_get_project(client):
    # Create a project
    create_resp = client.post("/pm/api/default/projects", json={
        "name": "Test Project",
        "description": "Description"
    })
    project_id = create_resp.json()["project_id"]

    # Get it
    response = client.get(f"/pm/api/default/projects/{project_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Project"


def test_get_project_not_found(client):
    response = client.get("/pm/api/default/projects/9999")
    assert response.status_code == 404


def test_update_project(client):
    # Create a project
    create_resp = client.post("/pm/api/default/projects", json={"name": "Original"})
    project_id = create_resp.json()["project_id"]

    # Update it
    response = client.put(f"/pm/api/default/projects/{project_id}", json={
        "name": "Updated",
        "description": "New description"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated"
    assert data["description"] == "New description"


def test_delete_project(client):
    # Create a project
    create_resp = client.post("/pm/api/default/projects", json={"name": "To Delete"})
    project_id = create_resp.json()["project_id"]

    # Delete it
    response = client.delete(f"/pm/api/default/projects/{project_id}")
    assert response.status_code == 204

    # Verify it's gone
    response = client.get(f"/pm/api/default/projects/{project_id}")
    assert response.status_code == 404


def test_project_with_parent(client):
    # Create parent
    parent_resp = client.post("/pm/api/default/projects", json={"name": "Parent"})
    parent_id = parent_resp.json()["project_id"]

    # Create child
    child_resp = client.post("/pm/api/default/projects", json={
        "name": "Child",
        "parent_id": parent_id
    })
    assert child_resp.status_code == 201
    assert child_resp.json()["parent_id"] == parent_id

    # List children
    response = client.get(f"/pm/api/default/projects?parent_id={parent_id}")
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_create_duplicate_project(client):
    client.post("/pm/api/default/projects", json={"name": "Duplicate"})
    response = client.post("/pm/api/default/projects", json={"name": "Duplicate"})
    assert response.status_code == 400


# ============================================================================
# Phase tests
# ============================================================================

def test_create_phase(client):
    # Create a project first
    proj_resp = client.post("/pm/api/default/projects", json={"name": "Project"})
    project_id = proj_resp.json()["project_id"]

    # Create a phase
    response = client.post("/pm/api/default/phases", json={
        "name": "Phase 1",
        "description": "First phase",
        "project_id": project_id
    })
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Phase 1"
    assert data["project_id"] == project_id


def test_list_phases(client):
    # Create a project and phases
    proj_resp = client.post("/pm/api/default/projects", json={"name": "Project"})
    project_id = proj_resp.json()["project_id"]

    client.post("/pm/api/default/phases", json={"name": "Phase 1", "project_id": project_id})
    client.post("/pm/api/default/phases", json={"name": "Phase 2", "project_id": project_id})

    response = client.get(f"/pm/api/default/phases?project_id={project_id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


def test_phase_ordering(client):
    # Create a project and phases
    proj_resp = client.post("/pm/api/default/projects", json={"name": "Project"})
    project_id = proj_resp.json()["project_id"]

    phase1_resp = client.post("/pm/api/default/phases", json={
        "name": "Phase 1",
        "project_id": project_id
    })
    phase1_id = phase1_resp.json()["phase_id"]

    phase2_resp = client.post("/pm/api/default/phases", json={
        "name": "Phase 2",
        "project_id": project_id,
        "follows_id": phase1_id
    })
    phase2_id = phase2_resp.json()["phase_id"]

    # Verify ordering via project phases endpoint
    response = client.get(f"/pm/api/default/projects/{project_id}/phases")
    assert response.status_code == 200
    phases = response.json()
    assert phases[0]["name"] == "Phase 1"
    assert phases[1]["name"] == "Phase 2"
    assert phases[1]["follows_id"] == phase1_id


def test_get_phase(client):
    proj_resp = client.post("/pm/api/default/projects", json={"name": "Project"})
    project_id = proj_resp.json()["project_id"]

    phase_resp = client.post("/pm/api/default/phases", json={
        "name": "Phase 1",
        "project_id": project_id
    })
    phase_id = phase_resp.json()["phase_id"]

    response = client.get(f"/pm/api/default/phases/{phase_id}")
    assert response.status_code == 200
    assert response.json()["name"] == "Phase 1"


def test_update_phase(client):
    proj_resp = client.post("/pm/api/default/projects", json={"name": "Project"})
    project_id = proj_resp.json()["project_id"]

    phase_resp = client.post("/pm/api/default/phases", json={
        "name": "Original",
        "project_id": project_id
    })
    phase_id = phase_resp.json()["phase_id"]

    response = client.put(f"/pm/api/default/phases/{phase_id}", json={
        "name": "Updated",
        "description": "New description"
    })
    assert response.status_code == 200
    assert response.json()["name"] == "Updated"


def test_delete_phase(client):
    proj_resp = client.post("/pm/api/default/projects", json={"name": "Project"})
    project_id = proj_resp.json()["project_id"]

    phase_resp = client.post("/pm/api/default/phases", json={
        "name": "To Delete",
        "project_id": project_id
    })
    phase_id = phase_resp.json()["phase_id"]

    response = client.delete(f"/pm/api/default/phases/{phase_id}")
    assert response.status_code == 204

    response = client.get(f"/pm/api/default/phases/{phase_id}")
    assert response.status_code == 404


# ============================================================================
# Task tests
# ============================================================================

def test_create_task(client):
    response = client.post("/pm/api/default/tasks", json={
        "name": "Task 1",
        "description": "First task",
        "status": "ToDo"
    })
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Task 1"
    assert data["status"] == "ToDo"


def test_create_task_with_project_and_phase(client):
    proj_resp = client.post("/pm/api/default/projects", json={"name": "Project"})
    project_id = proj_resp.json()["project_id"]

    phase_resp = client.post("/pm/api/default/phases", json={
        "name": "Phase 1",
        "project_id": project_id
    })
    phase_id = phase_resp.json()["phase_id"]

    response = client.post("/pm/api/default/tasks", json={
        "name": "Task 1",
        "status": "ToDo",
        "project_id": project_id,
        "phase_id": phase_id
    })
    assert response.status_code == 201
    data = response.json()
    assert data["project_id"] == project_id
    assert data["phase_id"] == phase_id


def test_list_tasks(client):
    client.post("/pm/api/default/tasks", json={"name": "Task 1", "status": "ToDo"})
    client.post("/pm/api/default/tasks", json={"name": "Task 2", "status": "Doing"})
    client.post("/pm/api/default/tasks", json={"name": "Task 3", "status": "Done"})

    # List all
    response = client.get("/pm/api/default/tasks")
    assert response.status_code == 200
    assert len(response.json()) == 3

    # Filter by status
    response = client.get("/pm/api/default/tasks?status=ToDo")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["name"] == "Task 1"


def test_get_task(client):
    create_resp = client.post("/pm/api/default/tasks", json={
        "name": "Task 1",
        "status": "ToDo"
    })
    task_id = create_resp.json()["task_id"]

    response = client.get(f"/pm/api/default/tasks/{task_id}")
    assert response.status_code == 200
    assert response.json()["name"] == "Task 1"


def test_update_task(client):
    create_resp = client.post("/pm/api/default/tasks", json={
        "name": "Original",
        "status": "ToDo"
    })
    task_id = create_resp.json()["task_id"]

    response = client.put(f"/pm/api/default/tasks/{task_id}", json={
        "name": "Updated",
        "status": "Doing",
        "description": "In progress"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated"
    assert data["status"] == "Doing"


def test_delete_task(client):
    create_resp = client.post("/pm/api/default/tasks", json={
        "name": "To Delete",
        "status": "ToDo"
    })
    task_id = create_resp.json()["task_id"]

    response = client.delete(f"/pm/api/default/tasks/{task_id}")
    assert response.status_code == 204

    response = client.get(f"/pm/api/default/tasks/{task_id}")
    assert response.status_code == 404


def test_list_project_tasks(client):
    proj_resp = client.post("/pm/api/default/projects", json={"name": "Project"})
    project_id = proj_resp.json()["project_id"]

    client.post("/pm/api/default/tasks", json={
        "name": "Task 1",
        "status": "ToDo",
        "project_id": project_id
    })
    client.post("/pm/api/default/tasks", json={
        "name": "Task 2",
        "status": "ToDo",
        "project_id": project_id
    })
    client.post("/pm/api/default/tasks", json={
        "name": "Other Task",
        "status": "ToDo"
    })

    response = client.get(f"/pm/api/default/projects/{project_id}/tasks")
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_list_phase_tasks(client):
    proj_resp = client.post("/pm/api/default/projects", json={"name": "Project"})
    project_id = proj_resp.json()["project_id"]

    phase_resp = client.post("/pm/api/default/phases", json={
        "name": "Phase 1",
        "project_id": project_id
    })
    phase_id = phase_resp.json()["phase_id"]

    client.post("/pm/api/default/tasks", json={
        "name": "Task 1",
        "status": "ToDo",
        "project_id": project_id,
        "phase_id": phase_id
    })

    response = client.get(f"/pm/api/default/phases/{phase_id}/tasks")
    assert response.status_code == 200
    assert len(response.json()) == 1


# ============================================================================
# Blocker tests
# ============================================================================

def test_add_blocker(client):
    task1_resp = client.post("/pm/api/default/tasks", json={
        "name": "Blocker Task",
        "status": "ToDo"
    })
    blocker_id = task1_resp.json()["task_id"]

    task2_resp = client.post("/pm/api/default/tasks", json={
        "name": "Blocked Task",
        "status": "ToDo"
    })
    blocked_id = task2_resp.json()["task_id"]

    response = client.post(f"/pm/api/default/tasks/{blocked_id}/blockers", json={
        "blocked_task_id": blocked_id,
        "blocking_task_id": blocker_id
    })
    assert response.status_code == 201


def test_list_blockers(client):
    task1_resp = client.post("/pm/api/default/tasks", json={
        "name": "Blocker Task",
        "status": "ToDo"
    })
    blocker_id = task1_resp.json()["task_id"]

    task2_resp = client.post("/pm/api/default/tasks", json={
        "name": "Blocked Task",
        "status": "ToDo"
    })
    blocked_id = task2_resp.json()["task_id"]

    client.post(f"/pm/api/default/tasks/{blocked_id}/blockers", json={
        "blocked_task_id": blocked_id,
        "blocking_task_id": blocker_id
    })

    response = client.get(f"/pm/api/default/tasks/{blocked_id}/blockers")
    assert response.status_code == 200
    blockers = response.json()
    assert len(blockers) == 1
    assert blockers[0]["task_id"] == blocker_id


def test_remove_blocker(client):
    task1_resp = client.post("/pm/api/default/tasks", json={
        "name": "Blocker Task",
        "status": "ToDo"
    })
    blocker_id = task1_resp.json()["task_id"]

    task2_resp = client.post("/pm/api/default/tasks", json={
        "name": "Blocked Task",
        "status": "ToDo"
    })
    blocked_id = task2_resp.json()["task_id"]

    client.post(f"/pm/api/default/tasks/{blocked_id}/blockers", json={
        "blocked_task_id": blocked_id,
        "blocking_task_id": blocker_id
    })

    response = client.delete(f"/pm/api/default/tasks/{blocked_id}/blockers/{blocker_id}")
    assert response.status_code == 204

    response = client.get(f"/pm/api/default/tasks/{blocked_id}/blockers")
    assert len(response.json()) == 0


def test_list_tasks_blocked_by(client):
    task1_resp = client.post("/pm/api/default/tasks", json={
        "name": "Blocker Task",
        "status": "ToDo"
    })
    blocker_id = task1_resp.json()["task_id"]

    task2_resp = client.post("/pm/api/default/tasks", json={
        "name": "Blocked Task 1",
        "status": "ToDo"
    })
    blocked1_id = task2_resp.json()["task_id"]

    task3_resp = client.post("/pm/api/default/tasks", json={
        "name": "Blocked Task 2",
        "status": "ToDo"
    })
    blocked2_id = task3_resp.json()["task_id"]

    client.post(f"/pm/api/default/tasks/{blocked1_id}/blockers", json={
        "blocked_task_id": blocked1_id,
        "blocking_task_id": blocker_id
    })
    client.post(f"/pm/api/default/tasks/{blocked2_id}/blockers", json={
        "blocked_task_id": blocked2_id,
        "blocking_task_id": blocker_id
    })

    response = client.get(f"/pm/api/default/tasks/{blocker_id}/blocks")
    assert response.status_code == 200
    blocked = response.json()
    assert len(blocked) == 2


def test_blocker_done_filtering(client):
    task1_resp = client.post("/pm/api/default/tasks", json={
        "name": "Blocker Task",
        "status": "Done"
    })
    blocker_id = task1_resp.json()["task_id"]

    task2_resp = client.post("/pm/api/default/tasks", json={
        "name": "Blocked Task",
        "status": "ToDo"
    })
    blocked_id = task2_resp.json()["task_id"]

    client.post(f"/pm/api/default/tasks/{blocked_id}/blockers", json={
        "blocked_task_id": blocked_id,
        "blocking_task_id": blocker_id
    })

    # By default, done blockers are filtered out
    response = client.get(f"/pm/api/default/tasks/{blocked_id}/blockers")
    assert len(response.json()) == 0

    # Include done blockers
    response = client.get(f"/pm/api/default/tasks/{blocked_id}/blockers?include_done=true")
    assert len(response.json()) == 1
