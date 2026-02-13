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
from dpm.fastapi.dpm.api_router import PhaseUpdate, ProjectCreate, PhaseCreate, ProjectUpdate, TaskCreate


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


def test_main_objects_crud_1(full_app_create):
    setup_dict = full_app_create
    db: ModelDB = setup_dict['db']
    domain_name = setup_dict['domain_name']
    client = TestClient(setup_dict['app'])

    project_create_url = f"/api/{domain_name}/projects/"
    project_create = ProjectCreate(name='top_project',
                                   description="project at top of tree")
    create_response = client.post(project_create_url, json=project_create.model_dump())
    assert create_response.status_code == 201
    res_dict = create_response.json()
    res_dict['id'] = res_dict['project_id']
    del res_dict['project_id']
    # just make sure it works, no blow up
    project = Project(**res_dict)
    
    project_get_url = f"/api/{domain_name}/projects/{project.id}"
    get_response = client.get(project_get_url)
    assert get_response.status_code == 200
    tmp = get_response.json()
    assert tmp['project_id'] == project.id

    project_list_url = f"/api/{domain_name}/projects"
    list_response = client.get(project_list_url)
    assert list_response.status_code == 200
    tmp = list_response.json()
    assert isinstance(tmp, list)
    assert len(tmp) == 1
    assert tmp[0]['project_id'] == project.id
    
    project_2_create = ProjectCreate(name='level2_project',
                                     description="first child project",
                                     parent_id=project.id)
    create_2_response = client.post(project_create_url, json=project_2_create.model_dump())
    assert create_2_response.status_code == 201
    tmp = create_2_response.json()
    tmp['id'] = tmp['project_id']
    assert tmp['id'] != project.id
    del tmp['project_id']
    project_2 = Project(**tmp)
    assert project_2.parent_id == project.id
    
    list_response = client.get(project_list_url)
    assert list_response.status_code == 200
    tmp = list_response.json()
    assert isinstance(tmp, list)
    assert len(tmp) == 2
    assert tmp[0]['project_id'] == project.id
    assert tmp[1]['project_id'] == project_2.id

    # get, update and delete use same url
    project_1_update = ProjectUpdate(name=project.name,
                                     description=project.description + " updated") # type: ignore
    update_response = client.put(project_get_url, json=project_1_update.model_dump())
    assert list_response.status_code == 200

    db_proj_1 = db.get_project_by_id(project.id)
    assert db_proj_1.description == project.description + " updated" # type: ignore

    phase_create_url = f"/api/{domain_name}/phases/"
    phase_create = PhaseCreate(name='top_phase',
                               project_id=project_2.id, # type: ignore
                               description="phase at top of tree")
    create_response = client.post(phase_create_url, json=phase_create.model_dump())
    assert create_response.status_code == 201
    tmp = create_response.json()
    tmp['id'] = tmp['phase_id']
    del tmp['phase_id']
    # just make sure it works, no blow up
    phase = Phase(**tmp)
    
    phase_get_url = f"/api/{domain_name}/phases/{phase.id}"
    get_response = client.get(phase_get_url)
    assert get_response.status_code == 200
    tmp = get_response.json()
    assert tmp['phase_id'] == phase.id

    phase_list_url = f"/api/{domain_name}/phases"
    list_response = client.get(phase_list_url)
    assert list_response.status_code == 200
    tmp = list_response.json()
    assert isinstance(tmp, list)
    assert len(tmp) == 1
    assert tmp[0]['phase_id'] == phase.id

    phase_1_update = PhaseUpdate(name=phase.name,
                                     description=phase.description + " updated") # type: ignore
    update_response = client.put(phase_get_url, json=phase_1_update.model_dump())
    assert list_response.status_code == 200
    
    
    task_create_url = f"/api/{domain_name}/tasks/"
    task_create = TaskCreate(name='top_task',
                               project_id=project.id, # type: ignore
                               description="task at top of tree")
    create_response = client.post(task_create_url, json=task_create.model_dump())
    assert create_response.status_code == 201
    tmp = create_response.json()
    tmp['id'] = tmp['task_id']
    del tmp['task_id']
    # just make sure it works, no blow up
    task = Task(**tmp)
    
    task_get_url = f"/api/{domain_name}/tasks/{task.id}"
    get_response = client.get(task_get_url)
    assert get_response.status_code == 200
    tmp = get_response.json()
    assert tmp['task_id'] == task.id

    task_list_url = f"/api/{domain_name}/tasks"
    list_response = client.get(task_list_url)
    assert list_response.status_code == 200
    tmp = list_response.json()
    assert isinstance(tmp, list)
    assert len(tmp) == 1
    assert tmp[0]['task_id'] == task.id
    
    task_2_create = TaskCreate(name='level2_task',
                               phase_id=phase.id, # type: ignore
                               description="task at second level of tree")
    create_response = client.post(task_create_url, json=task_2_create.model_dump())
    assert create_response.status_code == 201
    tmp = create_response.json()
    tmp['id'] = tmp['task_id']
    del tmp['task_id']
    # just make sure it works, no blow up
    task_2 = Task(**tmp)

    list_response = client.get(task_list_url)
    assert list_response.status_code == 200
    tmp = list_response.json()
    assert isinstance(tmp, list)
    assert len(tmp) == 2
    assert tmp[0]['task_id'] == task.id
    assert tmp[1]['task_id'] == task_2.id
    


    
