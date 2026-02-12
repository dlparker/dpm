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
from dpm.fastapi.dpm.api_router import ProjectCreate


from dpm.store.models import Task, Project, Phase, Task
from dpm.store.wrappers import ModelDB, TaskRecord, ProjectRecord, PhaseRecord

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

def test_read_root(full_app_create):
    setup_dict = full_app_create
    client = TestClient(setup_dict['app'])
    domain_name = setup_dict['domain_name']
    response = client.get("/api/domains")
    assert response.status_code == 200
    res = response.json()
    assert len(res) == 1
    assert res[0]['name'] == domain_name


def test_projects_1(full_app_create):
    setup_dict = full_app_create
    domain_name = setup_dict['domain_name']
    client = TestClient(setup_dict['app'])

    url = f"/api/{domain_name}/projects/"
    project_create = ProjectCreate(name='top_project',
                                   description="project at top of tree")
    response = client.post(url, json=project_create.model_dump())
    assert response.status_code == 201
    
