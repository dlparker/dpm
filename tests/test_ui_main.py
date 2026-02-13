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

    # --- Read: project detail page ---
    detail_url = f"/{domain_name}/project/{proj_1.project_id}"
    detail_response = client.get(detail_url)
    assert detail_response.status_code == 200
    assert "top_project" in detail_response.text

    # --- Read: project children page (shows phases and direct tasks, not sub-projects) ---
    children_url = f"/{domain_name}/project/{proj_1.project_id}/children"
    children_response = client.get(children_url)
    assert children_response.status_code == 200
    # top_project has no phases or tasks yet, so expect the empty message
    assert "No phases or tasks" in children_response.text

    # --- Read: create form (GET) renders ---
    create_form_response = client.get(project_create_url)
    assert create_form_response.status_code == 200

    # --- Delete: confirmation page ---
    delete_confirm_url = f"/{domain_name}/project/{proj_1.project_id}/delete"
    delete_confirm_response = client.get(delete_confirm_url)
    assert delete_confirm_response.status_code == 200
    assert "top_project" in delete_confirm_response.text

    # --- Delete: submit ---
    delete_response = client.post(delete_confirm_url)
    assert delete_response.status_code == 200
    assert "alert-success" in delete_response.text
    assert "deleted" in delete_response.text.lower()

    # Verify project and child are both gone (cascade)
    assert db.get_project_by_id(proj_1.project_id) is None
    assert db.get_project_by_id(proj_2.project_id) is None
