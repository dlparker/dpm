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

from dpm.store.models import (ModelDB, TaskRecord, ProjectRecord, PhaseRecord,
                                FilterWrapper, Task, Project, Phase,
                                DPMManager, DomainCatalog)

from dpm.taxons import (DPMBase,
                        TaxoDef,
                        TaxoLevel,
                        TaxoLevelForDomain,
                        TaxoLevelForProject,
                        TaxoLevelForPhase,
                        TaxoLevelForTask
                        )

def make_sw_taxonomy():
    taxonomy = TaxoDef(
        covers_dpm = DPMBase.domain,
        name = "Software Project"
    )
    vision = TaxoDef(
        covers_dpm = DPMBase.project,
        name = "Vision",
        parent = taxonomy,
        allow_multiple = False
    )
    taxonomy.children.append(vision)
    deliverable = TaxoDef(
        covers_dpm = DPMBase.project,
        name = "Deliverable",
        parent = vision
    )
    vision.children.append(deliverable)
    epic = TaxoDef(
        covers_dpm = DPMBase.project,
        name = "Epic",
        parent = deliverable
    )
    deliverable.children.append(epic)
    story = TaxoDef(
        covers_dpm = DPMBase.phase,
        name = "Story",
        parent = epic
    )
    epic.children.append(story)
    task = TaxoDef(
        covers_dpm = DPMBase.task,
        name = "Task",
        parent = deliverable
    )
    story.children.append(task)
    return taxonomy


@pytest.fixture
def create_db():
    db_dir = Path("/tmp")
    target_db_name = "discard_test_model_db.sqlite"
    target_db_path = db_dir / target_db_name
    if target_db_path.exists():
        target_db_path.unlink()
    model_db = ModelDB(db_dir, name_override=target_db_name, autocreate=True)
    return [model_db, db_dir, target_db_name]

def test_auto_fill_exampe_1(create_db, tmp_path):
    db1 = ModelDB(tmp_path, name_override="test_domain.db", autocreate=True)
    config = {
        "databases": {
            "TestDomain": {
                "path": "./test_domain.db",
                "description": "Test domain 1"
            }
        }
    }
    config_path = tmp_path / "config.json"
    with open(config_path, "w") as f:
        json.dump(config, f)
    catalog = DomainCatalog.from_json_config(config_path)
    
    taxonomy_def = make_sw_taxonomy()
    from pprint import pprint
    pprint(taxonomy_def)
    top = TaxoLevelForDomain(catalog=catalog, taxo_def=taxonomy_def, name="TestDomain")
    # Okay,so you'd never really do this, just inferring a structure of inferences from
    # the structure of the taxonomy, but it is handy for testing
    def add_level(parent, level_index=0):
        for index, child_def in enumerate(parent.taxo_def.children):
            if child_def.covers_dpm == DPMBase.project:
                if isinstance(parent, TaxoLevelForDomain):
                    domain_level = parent
                    parent_level = None
                else:
                    domain_level = parent.domain_level
                    parent_level = parent
                level = TaxoLevelForProject(domain_level=domain_level,
                                            parent_level=parent_level,
                                            taxo_def=child_def,
                                            name=f"Level {level_index} item {index}")
            elif child_def.covers_dpm == DPMBase.phase:
                level = TaxoLevelForPhase(project_level=parent,taxo_def=child_def, name=f"Level {level_index} item {index}")
            elif child_def.covers_dpm == DPMBase.task:
                level = TaxoLevelForTask(parent_level=parent, taxo_def=child_def, name=f"Level {level_index} item {index}")
            else:
                raise Exception('')
            add_level(level, level_index+1)
    add_level(top, 0)

    breakpoint()
    pprint(top)


def footest_phase_tasks(create_db):
    model_db, db_dir, target_db_name = create_db

    proj_1 = ProjectRecord(model_db=model_db, project=Project(name="proj_1", name_lower="proj_1", description="some things"))
    proj_1.save()
    assert len(proj_1.get_tasks()) == 0

    phase_1 = PhaseRecord(model_db, Phase(name="phase_1", name_lower="phase_1", description=None, project_id=proj_1.project_id, position=1.0))
    assert len(phase_1.get_tasks()) == 0
    phase_1.save()
    assert len(phase_1.get_tasks()) == 0

    task1 = model_db.add_task('task1', 'foobar', 'ToDo')
    # don't do this in real code, use the add_to_phase method
    task1.phase_id = phase_1.phase_id
    task1.save()
    # change it back so we can do it right
    task1.phase_id = None
    task1.project_id = None
    task1.save()
    assert task1.phase is None
    task1.add_to_phase(phase_1)
    assert task1.phase is not None
    tlist = phase_1.get_tasks()
    assert len(tlist) == 1
    assert tlist[0].task_id == task1.task_id

    task1.phase_id = 888888888
    with pytest.raises(Exception):
        task1.save()
    task1.phase_id = phase_1.phase_id

    assert task1.project is not None
    tlist = proj_1.get_tasks()
    assert len(tlist) == 1
    assert tlist[0].task_id == task1.task_id

    task2 = model_db.add_task('task2', 'blarch', 'ToDo')
    assert task2.project is None
    assert task2.phase is None
    task2.add_to_phase(phase_1)
    assert task2.phase is not None
    tlist = phase_1.get_tasks()
    assert len(tlist) == 2
    assert tlist[1].task_id == task2.task_id

    with pytest.raises(Exception):
        model_db.replace_task_phase_refs(phase_1.phase_id, -1)

    # test that phase delete removes phase_id from tasks
    # and moves tasks to project
    phase_1.delete_from_db()
    task1 = model_db.get_task_by_name('task1')
    assert task1.phase_id is None
    assert task1.project_id is not None
    task2 = model_db.get_task_by_name('task2')
    assert task2.phase_id is None
    assert task2.project_id is not None


    proj_2 = ProjectRecord(model_db=model_db, project=Project(name="proj_2", name_lower="proj_2", description="some things"))
    proj_2.save()
    phase_2 = PhaseRecord(model_db, Phase(name="phase_2", name_lower="phase_2", description=None, project_id=proj_2.project_id, position=1.0))
    phase_2.save()

    task3 = model_db.add_task('task3', 'bebebeb', 'ToDo', project_id=proj_2.project_id,
                             phase_id=phase_2.phase_id)
    assert len(phase_2.get_tasks()) == 1

    proj_3 = ProjectRecord(model_db=model_db, project=Project(name="proj_3", name_lower="proj_3", description="some things"))
    proj_3.save()
    phase_3 = PhaseRecord(model_db, Phase(name="phase_3", name_lower="phase_3", description=None, project_id=proj_3.project_id, position=1.0))
    phase_3.save()

    with pytest.raises(Exception):
        # should fail because phase_3 is different project
        task3.add_to_phase(phase_3)

    with pytest.raises(Exception):
        # should fail because phase_3 is different project
        task3.phase = phase_3
        task3.save()
    # now tell it to move to project too
    task3.add_to_phase(phase_3, move_to_project=True)
    assert task3.project == proj_3
    assert len(phase_2.get_tasks()) == 0
    assert len(phase_3.get_tasks()) == 1
    assert len(proj_2.get_tasks()) == 0
    assert len(proj_3.get_tasks()) == 1

    model_db.replace_task_phase_refs(phase_3.phase_id, phase_2.phase_id)
    assert len(phase_2.get_tasks()) == 1
    assert len(phase_3.get_tasks()) == 0
    assert len(proj_2.get_tasks()) == 1
    assert len(proj_3.get_tasks()) == 0

    # should change nothing
    model_db.replace_task_phase_refs(phase_2.phase_id, phase_2.phase_id)
    assert len(phase_2.get_tasks()) == 1
    assert len(phase_3.get_tasks()) == 0
    assert len(proj_2.get_tasks()) == 1
    assert len(proj_3.get_tasks()) == 0

    proj_4 = ProjectRecord(model_db=model_db, project=Project(name="proj_4", name_lower="proj_4", description=None))
    proj_4.save()
    phase_4 = PhaseRecord(model_db, Phase(name="phase_4", name_lower="phase_4", description=None, project_id=proj_4.project_id, position=1.0))
    phase_4.save()
    assert len(phase_4.get_tasks()) == 0
    task4 = model_db.add_task('task4', 'bebebeb', 'ToDo', project_id=proj_4.project_id,
                             phase_id=phase_4.phase_id)
    assert len(phase_4.get_tasks()) == 1
    assert len(proj_4.get_tasks()) == 1

    proj_5 = ProjectRecord(model_db=model_db, project=Project(name="proj_5", name_lower="proj_5", description=None,
                           parent_id=proj_4.project_id))
    proj_5.save()
    phase_5 = PhaseRecord(model_db, Phase(name="phase_5", name_lower="phase_5", description=None, project_id=proj_5.project_id, position=1.0))
    phase_5.save()
    phase_6 = PhaseRecord(model_db, Phase(name="phase_6", name_lower="phase_6", description=None, project_id=proj_5.project_id, position=1.0))
    phase_6.save()
    assert len(phase_5.get_tasks()) == 0
    assert len(phase_6.get_tasks()) == 0
    assert len(proj_5.get_tasks()) == 0

    # now move phase_4 to project 5 and make sure the task 4 moves too
    phase_4.change_project(proj_5.project_id)
    # get updated copy, db has changed
    task4 = model_db.get_task_by_id(task4.task_id)
    assert task4.project == proj_5
    assert phase_4.follows_id == phase_6.phase_id
    assert len(phase_4.get_tasks()) == 1
    assert len(proj_4.get_tasks()) == 0
    assert len(proj_5.get_tasks()) == 1
    assert len(phase_5.get_tasks()) == 0
    assert len(phase_6.get_tasks()) == 0

    # now move it back and do some checks
    phase_4.change_project(proj_4.project_id)
    task4 = model_db.get_task_by_id(task4.task_id)
    assert task4.project == proj_4
    assert phase_4.follows_id is None  # should be first

    # now move it to project 5 again, then delete the project and do some checks
    phase_4.change_project(proj_5.project_id)
    assert len(proj_4.get_tasks()) == 0
    assert len(proj_5.get_tasks()) == 1
    proj_5.delete_from_db()
    phase_4 = model_db.get_phase_by_id(phase_4.phase_id)
    assert phase_4.project == proj_4
    assert len(proj_4.get_tasks()) == 1

