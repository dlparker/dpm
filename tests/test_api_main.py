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
from dpm.fastapi.dpm.api_router import BlockerCreate, BlockerResponse, PhaseUpdate, ProjectCreate, PhaseCreate, ProjectUpdate, TaskCreate, TaskUpdate


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

def test_projects_crud_1(full_app_create):
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
    
    db_proj_1 = db.get_project_by_id(project.id)
    assert db_proj_1.name == project.name
    
    project_2_create = ProjectCreate(name='level2_project',
                                     description="first child project",
                                     parent_id=project.id)
    create_2_response = client.post(project_create_url, json=project_2_create.model_dump())
    assert create_2_response.status_code == 201
    project_2_id = create_2_response.json()['project_id']
    assert project_2_id != project.id
    db_proj_2 = db.get_project_by_id(project_2_id)
    assert db_proj_2.parent_id == db_proj_1.project_id

    list_response = client.get(project_list_url)
    assert list_response.status_code == 200
    tmp = list_response.json()
    assert isinstance(tmp, list)
    assert len(tmp) == 2
    assert tmp[0]['project_id'] == project.id
    assert tmp[1]['project_id'] == project_2_id
    
    project_1_update = ProjectUpdate(name=project.name,
                                     description=db_proj_1.description + " updated") # type: ignore
    update_response = client.put(project_get_url, json=project_1_update.model_dump())
    assert update_response.status_code == 200
    db_proj_1_new = db.get_project_by_id(project.id)
    assert db_proj_1.description == db_proj_1.description

    db_proj_2_new = db.get_project_by_id(project_2_id)
    delete_response = client.delete(project_get_url)
    assert delete_response.status_code == 204

    assert db.get_project_by_id(db_proj_1.project_id) is None
    # we cascade (manually) on delete
    assert db.get_project_by_id(project_2_id) is None

def make_projects(setup_dict):
    db: ModelDB = setup_dict['db']
    domain_name = setup_dict['domain_name']
    client = TestClient(setup_dict['app'])

    project_create_url = f"/api/{domain_name}/projects/"
    p1_name = 'top_project'
    project_create = ProjectCreate(name=p1_name,
                                   description="project at top of tree")
    create_response = client.post(project_create_url, json=project_create.model_dump())
    assert create_response.status_code == 201
    proj_1_id = create_response.json()['project_id']
    db_proj_1 = db.get_project_by_id(proj_1_id)
    assert db_proj_1.name == p1_name
    
    project_2_create = ProjectCreate(name='level2_project',
                                     description="first child project",
                                     parent_id=proj_1_id)
    create_2_response = client.post(project_create_url, json=project_2_create.model_dump())
    assert create_2_response.status_code == 201
    proj_2_id = create_2_response.json()['project_id']
    db_proj_2 = db.get_project_by_id(proj_2_id)
    assert db_proj_2.parent_id == db_proj_1.project_id
    return proj_1_id, proj_2_id

def test_phase_crud_1(full_app_create):
    setup_dict = full_app_create
    proj_1_id, proj_2_id = make_projects(setup_dict)
    db: ModelDB = setup_dict['db']
    domain_name = setup_dict['domain_name']
    client = TestClient(setup_dict['app'])
    phase_create_url = f"/api/{domain_name}/phases/"
    phase_create = PhaseCreate(name='top_phase',
                               project_id=proj_2_id, # type: ignore
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
    assert update_response.status_code == 200
    db_phase = db.get_phase_by_id(phase.id)
    assert db_phase is not None
    assert db_phase.description == phase.description + " updated" # type: ignore

    # now delete the project phase is attached to, and make sure that it
    # gets adopted by parent project
    proj = db.get_project_by_id(db_phase.project_id)
    target_id = proj.parent_id
    proj.delete_from_db()
    get_response = client.get(phase_get_url)
    assert get_response.status_code == 200
    tmp = get_response.json()
    assert tmp['project_id'] == target_id

    # now delete the phase
    delete_response = client.delete(phase_get_url)
    assert delete_response.status_code == 204
    assert db.get_phase_by_id(phase.id) is None


def test_task_crud_1(full_app_create):
    setup_dict = full_app_create
    proj_1_id, proj_2_id = make_projects(setup_dict)
    db: ModelDB = setup_dict['db']
    domain_name = setup_dict['domain_name']
    client = TestClient(setup_dict['app'])
    phase_create_url = f"/api/{domain_name}/phases/"
    phase_create = PhaseCreate(name='test_phase',
                               project_id=proj_2_id, # type: ignore
                               description="phase at top of tree")
    create_response = client.post(phase_create_url, json=phase_create.model_dump())
    assert create_response.status_code == 201
    proj_2_record = db.get_project_by_id(proj_2_id)
    phase_record = db.get_phase_by_name("test_phase")
    phase = phase_record._phase
    
    task_create_url = f"/api/{domain_name}/tasks/"
    task_create = TaskCreate(name='top_task',
                               project_id=proj_1_id, # type: ignore
                               description="task at top of tree")
    create_response = client.post(task_create_url, json=task_create.model_dump())
    assert create_response.status_code == 201
    tmp = create_response.json()
    task_1_id = tmp['id'] = tmp['task_id']
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
    task_2_id = create_response.json()['task_id']
    
    list_response = client.get(task_list_url)
    assert list_response.status_code == 200
    tmp = list_response.json()
    assert isinstance(tmp, list)
    assert len(tmp) == 2
    assert tmp[0]['task_id'] == task.id
    assert tmp[1]['task_id'] == task_2_id

    proj_task_list_url = f"/api/{domain_name}/projects/{proj_2_id}/tasks"
    proj_list_response = client.get(proj_task_list_url)
    assert proj_list_response.status_code == 200
    tmp = proj_list_response.json()
    assert isinstance(tmp, list)
    assert len(tmp) == 1
    assert tmp[0]['task_id'] == task_2_id

    phase_task_list_url = f"/api/{domain_name}/phases/{phase.id}/tasks"
    phase_list_response = client.get(phase_task_list_url)
    assert phase_list_response.status_code == 200
    tmp = phase_list_response.json()
    assert isinstance(tmp, list)
    assert len(tmp) == 1
    assert tmp[0]['task_id'] == task_2_id

    task_2_record = db.get_task_by_id(task_2_id)
    assert task_2_record is not None
    task_2_get_url = f"/api/{domain_name}/tasks/{task_2_id}"

    task_2_update = TaskUpdate(name=task_2_record.name,
                               description=task_2_record.description + " updated") # type: ignore
    update_response = client.put(task_2_get_url, json=task_2_update.model_dump())
    assert update_response.status_code == 200
    task_2_new_record = db.get_task_by_id(task_2_id)
    assert task_2_new_record is not None
    assert task_2_new_record.description == task_2_record.description + " updated" # type: ignore

    blocker_get_url = f"/api/{domain_name}/tasks/{task_1_id}/blockers"
    blocker_list_response = client.get(blocker_get_url)
    assert len(blocker_list_response.json()) == 0
    
    blocker_create = BlockerCreate(blocked_task_id=task_1_id,
                                   blocking_task_id=task_2_id)      
    blocker_add_response = client.post(blocker_get_url, json=blocker_create.model_dump())
    assert blocker_add_response.status_code == 201
    
    blocker_list_response = client.get(blocker_get_url)
    assert len(blocker_list_response.json()) == 1
    br_1 = BlockerResponse(**blocker_list_response.json()[0])
    assert br_1.task_id == task_2_id

    blocked_by_url = f"/api/{domain_name}/tasks/{task_2_id}/blocks"
    blocked_by_list_response = client.get(blocked_by_url)
    assert len(blocked_by_list_response.json()) == 1
    bl_1 = BlockerResponse(**blocked_by_list_response.json()[0])
    assert bl_1.task_id == task_1_id

    blocker_delete_url = blocker_get_url + f"/{task_2_id}"
    blocker_delete_response = client.delete(blocker_delete_url)
    assert blocker_delete_response.status_code == 204
    
    blocker_list_response = client.get(blocker_get_url)
    assert len(blocker_list_response.json()) == 0

    # now make sure that task moves up to parent project if attached project is deleted
    
    proj_2_record.delete_from_db()
    
    reget_response = client.get(task_2_get_url)
    tmp = reget_response.json()
    assert tmp['project_id'] == proj_1_id
    assert tmp['phase_id'] == phase_record.phase_id

    delete_response = client.delete(task_2_get_url)
    assert delete_response.status_code == 204


def test_exceptions_1(full_app_create):
    setup_dict = full_app_create
    db: ModelDB = setup_dict['db']
    domain_name = setup_dict['domain_name']
    client = TestClient(setup_dict['app'])

    bad_project_url = f"/api/{domain_name}/projects/10"
    res = client.get(bad_project_url)
    assert res.status_code == 404

    project_create_url = f"/api/{domain_name}/projects/"
    bad_project_create = ProjectCreate(name='bad_project',
                                   description="",
                                   parent_id=10)
    bad_create_response = client.post(project_create_url, json=bad_project_create.model_dump())
    assert bad_create_response.status_code == 400
    
    bad_project_1_update = ProjectUpdate(name="bad_project",
                                     description="") # type: ignore
    update_response = client.put(bad_project_url, json=bad_project_1_update.model_dump())
    assert update_response.status_code == 404


    project_create_url = f"/api/{domain_name}/projects/"
    project_create = ProjectCreate(name='good',
                                   description="")
    create_response = client.post(project_create_url, json=project_create.model_dump())
    assert create_response.status_code == 201
    project_1 = db.get_project_by_id(create_response.json()['project_id'])
    good_project_url = f"/api/{domain_name}/projects/{project_1.project_id}"
    
    bad_project_1_update_2 = ProjectUpdate(parent_id=10) # type: ignore
    update_response = client.put(good_project_url, json=bad_project_1_update_2.model_dump())
    assert update_response.status_code == 400

    phase_create_url = f"/api/{domain_name}/phases/"
    phase_create = PhaseCreate(name='bad_phase',
                               project_id=10) # type: ignore
    create_response = client.post(phase_create_url, json=phase_create.model_dump())
    assert create_response.status_code == 400


    task_create_url = f"/api/{domain_name}/tasks/"
    bad_task_create = TaskCreate(name='top_task',
                               project_id=10) # type: ignore
    bad_task_create_response = client.post(task_create_url, json=bad_task_create.model_dump())
    assert bad_task_create_response.status_code == 400
    

    good_task_create = TaskCreate(name='top_task',
                               project_id=project_1.project_id) # type: ignore
    good_task_create_response = client.post(task_create_url, json=good_task_create.model_dump())
    assert good_task_create_response.status_code == 201

    task_record = db.get_task_by_id(good_task_create_response.json()['task_id'])
    bad_task_update = TaskUpdate(project_id=10)
    
    task_get_url = f"/api/{domain_name}/tasks/{task_record.task_id}" # type: ignore
    update_response = client.put(task_get_url, json=bad_task_update.model_dump())
    assert update_response.status_code == 400
    
    
    blocker_get_url = f"/api/{domain_name}/tasks/{task_record.task_id}/blockers" # type: ignore
    bad_blocker_create_1 = BlockerCreate(blocked_task_id=task_record.task_id,# type: ignore
                                       blocking_task_id=10)      
    bad_blocker_add_response = client.post(blocker_get_url, json=bad_blocker_create_1.model_dump())
    assert bad_blocker_add_response.status_code == 404


    bad_blocker_create_2 = BlockerCreate(blocked_task_id=0,# type: ignore
                                         blocking_task_id=task_record.task_id)      # type: ignore
    bad_blocker_add_response = client.post(blocker_get_url, json=bad_blocker_create_2.model_dump())
    assert bad_blocker_add_response.status_code == 400
    
    bad_blocker_create_3 = BlockerCreate(blocked_task_id=task_record.task_id,# type: ignore
                                         blocking_task_id=task_record.task_id)      # type: ignore
    bad_blocker_add_response = client.post(blocker_get_url, json=bad_blocker_create_3.model_dump())
    assert bad_blocker_add_response.status_code == 400
    
