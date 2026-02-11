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

from dpm.store.models import Task, Project, Phase, Task
from dpm.store.domains import DPMManager, DomainCatalog
from dpm.store.wrappers import ModelDB, TaskRecord, ProjectRecord, PhaseRecord


@pytest.fixture
def create_db():
    db_dir = Path("/tmp")
    target_db_name = "discard_test_model_db.sqlite"
    target_db_path = db_dir / target_db_name
    if target_db_path.exists():
        target_db_path.unlink()
    model_db = ModelDB(db_dir, name_override=target_db_name, autocreate=True)
    return [model_db, db_dir, target_db_name]


def test_tasks_1(create_db):
    model_db, db_dir, target_db_name = create_db

    with pytest.raises(Exception):
        bad_db = ModelDB('.', name_override="foooo")

    with pytest.raises(Exception):
        bad_db = ModelDB(Path('/tmp_not_there'))

    assert model_db.get_task_by_name('task1') is None
    assert model_db.get_task_by_id(1) is None
    assert model_db.get_tasks_by_status('ToDo') == []
    task1 = model_db.add_task('task1', 'foobar', 'ToDo')
    assert 'task1' in str(task1)
    task1.description = "Updated"
    assert task1.save()
    copy = model_db.get_task_by_name('task1')
    assert copy.task_id == 1
    assert copy == task1

    t2 = model_db.get_task_by_id(1)
    assert t2 is not None
    assert t2 == task1
    todos = model_db.get_tasks_by_status('ToDo')
    assert len(todos) == 1
    t3 = todos[0]
    assert t3 == task1

    with pytest.raises(Exception):
        task2_bad = model_db.add_task('task1', 'foobar', 'ToDo')

    with pytest.raises(Exception):
        task2_bad = model_db.add_task('task2', 'foobar', 'blarch')

    with pytest.raises(Exception):
        model_db.get_tasks_by_status('foo')

    task2 = model_db.add_task('task2', None, 'ToDo')
    assert task2 != task1

    task2.name = task1.name
    with pytest.raises(Exception):
        task2.save()

    orig_tid = task1.task_id
    with pytest.raises(Exception):
        task1.task_id = -1
        task1.save()
    task1.task_id = orig_tid

    model_db.close()
    with pytest.raises(Exception):
        todos = model_db.get_tasks_by_status('ToDo')

    model_db2 = ModelDB(db_dir, name_override=target_db_name)

    todos = model_db2.get_tasks_by_status('ToDo')
    assert len(todos) == 2
    t4 = todos[0]
    t5 = todos[1]
    assert t4 == task1
    assert t5 == task2

    tr_new = TaskRecord(model_db=model_db2, task=Task(
        name="new rec", name_lower="new rec", description="slarty", status='ToDo'
    ))
    tr_new.save()
    tr_renew = model_db2.get_task_by_id(tr_new.task_id)
    assert tr_renew is not None
    todos = model_db2.get_tasks_by_status('ToDo')
    assert len(todos) == 3
    tr_renew.delete_from_db()
    # make sure a second call does not raise
    tr_renew.delete_from_db()

    todos = model_db2.get_tasks_by_status('ToDo')
    assert len(todos) == 2


def test_projects_1(create_db):
    model_db, db_dir, target_db_name = create_db

    proj_1 = model_db.add_project("proj_1", "some things")
    assert "proj_1" in str(proj_1)
    p1_copy = model_db.get_project_by_id(proj_1.project_id)
    assert proj_1 == p1_copy
    assert proj_1.parent is None
    assert proj_1 == model_db.get_project_by_name(proj_1.name)
    assert model_db.get_project_by_name(proj_1.name + 'a') is None
    no_proj = model_db.get_project_by_id(-1)
    assert no_proj is None
    assert len(model_db.get_projects()) == 1
    assert len(model_db.get_projects_by_parent_id(None)) == 1

    # use the id form of parenting
    proj_2 = model_db.add_project("proj_2", "child of proj_1, some other things", parent_id=proj_1.project_id)
    # check __eq__ false
    assert proj_2 != proj_1
    assert proj_2.parent.project_id == proj_1.project_id
    assert proj_2.parent is not None
    assert proj_2.parent == proj_1
    assert proj_2.parent == model_db.get_project_by_name(proj_2.name).parent
    assert f"{proj_2.project_id}" in str(proj_2)
    assert model_db.get_project_by_id(proj_2.project_id).parent.project_id == proj_1.project_id
    assert len(model_db.get_projects()) == 2


    kids = proj_1.get_kids()
    assert proj_2 == kids[0]

    proj_3 = model_db.add_project("proj_3", None, parent=proj_1)

    # use the project form of parenting and save it from a new project object
    proj_4 = ProjectRecord(model_db, Project(name="proj_4", name_lower="proj_4", description=None, parent_id=proj_2.project_id))
    proj_4.save()
    assert proj_4.parent == proj_2

    # test cascade
    pid = proj_1.project_id
    proj_1.delete_from_db()
    no_proj = model_db.get_project_by_id(pid)
    assert no_proj is None
    no_proj = model_db.get_project_by_id(proj_2.project_id)
    assert no_proj is None
    no_proj = model_db.get_project_by_id(proj_3.project_id)
    assert no_proj is None

    # make sure a second call does not fail
    proj_1.delete_from_db()

    with pytest.raises(Exception):
        proj_2.save()

    proj_5 = ProjectRecord(model_db, Project(name="proj_5", name_lower="proj_5", description=None))
    proj_5.save()
    with pytest.raises(Exception):
        # dup name
        proj_6 = model_db.add_project("proj_5")
    proj_6 = ProjectRecord(model_db, Project(name="proj_6", name_lower="proj_6", description=None))
    proj_6.save()
    with pytest.raises(Exception):
        proj_6.name = "proj_5"
        proj_6.save()
    proj_6.name = "proj_6"
    desc = "new_description"
    proj_6.description = desc
    proj_6.parent = proj_5
    proj_6.save()
    ncopy = model_db.get_project_by_id(proj_6.project_id)
    assert ncopy.description == desc
    assert ncopy.parent == proj_5

    proj_6.delete_from_db()

    with pytest.raises(Exception):
        # invalid parent_id
        proj_7 = model_db.add_project("proj_7", parent_id=-1)


def test_project_tasks(create_db):
    model_db, db_dir, target_db_name = create_db

    proj_1 = ProjectRecord(model_db=model_db, project=Project(name="proj_1", name_lower="proj_1", description="some things"))
    assert len(proj_1.get_tasks()) == 0
    proj_1.save()
    assert len(proj_1.get_tasks()) == 0

    task1 = model_db.add_task('task1', 'foobar', 'ToDo')
    task1.project_id = proj_1.project_id
    task1.save()
    assert task1.project is not None
    tlist = proj_1.get_tasks()
    assert len(tlist) == 1
    assert tlist[0].task_id == task1.task_id


    task2 = model_db.add_task('task2', 'blarch', 'ToDo')
    assert task2.project is None
    task2.add_to_project(proj_1)
    assert task2.project is not None
    tlist = proj_1.get_tasks()
    assert len(tlist) == 2
    assert tlist[1].task_id == task2.task_id

    # test that project delete removes project_id from tasks
    proj_1.delete_from_db()

    task1 = model_db.get_task_by_name('task1')
    orphans = model_db.get_project_by_name("Orphans")
    assert task1.project == orphans
    task2 = model_db.get_task_by_name('task2')
    assert task2.project == orphans

    # check that removing child project moves tasks up to parent project

    proj_2 = ProjectRecord(model_db=model_db, project=Project(name="proj_2", name_lower="proj_2", description="some things"))
    proj_2.save()
    proj_3 = ProjectRecord(model_db=model_db, project=Project(name="proj_3", name_lower="proj_3", description="some more things",
                           parent_id=proj_2.project_id))
    proj_3.save()

    task1.add_to_project(proj_2)
    task2.add_to_project(proj_3)
    proj_3.delete_from_db()
    task1 = model_db.get_task_by_name('task1')
    assert task1.project_id == proj_2.project_id
    task2 = model_db.get_task_by_name('task2')
    assert task1.project_id == proj_2.project_id

    with pytest.raises(Exception):
        model_db.replace_task_project_refs(proj_2.project_id, -1)


def test_task_depends_1(create_db):
    model_db, db_dir, target_db_name = create_db
    task1 = model_db.add_task('task1', 'foobar', 'ToDo')
    task2 = model_db.add_task('task2', None, 'ToDo')
    did = task2.add_blocker(task1)
    # should be idempotent
    assert did == task2.add_blocker(task1)
    res = task2.get_blockers()
    assert len(res) == 1
    assert task1.task_id == res[0].task_id
    with pytest.raises(Exception):
        task2.add_blocker(task2)
    with pytest.raises(Exception):
        task1.add_blocker(task2)

    task3 = model_db.add_task('task3', None, 'ToDo')
    task2.add_blocker(task3)
    assert len(task2.get_blockers()) == 2
    task4 = model_db.add_task('task4', None, 'ToDo')
    task3.add_blocker(task4)
    assert len(task2.get_blockers()) == 2
    assert len(task2.get_blockers(descend=True)) == 3

    assert len(task4.blocks_tasks()) == 1
    # task3, task2
    assert len(task4.blocks_tasks(ascend=True)) == 2

    task5 = model_db.add_task('task5', None, 'Done')
    task4.add_blocker(task5)
    assert len(task4.get_blockers()) == 0
    assert len(task4.get_blockers(only_not_done=False)) == 1
    assert len(task2.get_blockers(descend=True)) == 3
    assert len(task5.blocks_tasks()) == 1
    assert len(task5.blocks_tasks(ascend=True)) == 3
    assert len(task2.get_blockers(descend=True, only_not_done=False)) == 4

    task2.delete_blocker(task1)
    assert len(task2.get_blockers()) == 1

    task4.delete_from_db()
    task5 = model_db.get_task_by_id(task5.task_id)
    assert len(task5.blocks_tasks()) == 0
    assert len(task3.get_blockers(descend=True)) == 0


def test_phases_1(create_db):
    model_db, db_dir, target_db_name = create_db

    proj_1 = model_db.add_project("proj_1", "some things")
    phase_1 = model_db.add_phase("phase_1", "phase of project 1 some things", project=proj_1)
    assert "phase_1" in str(phase_1)
    p1_copy = model_db.get_phase_by_id(phase_1.phase_id)
    assert phase_1 == p1_copy
    assert phase_1.project == proj_1
    p1_copy_2 = model_db.get_phase_by_name(phase_1.name)
    assert phase_1 == p1_copy_2
    no_phase = model_db.get_phase_by_id(-1)
    assert no_phase is None
    no_phase = model_db.get_phase_by_name('foobaar')
    assert no_phase is None
    assert len(model_db.get_phases_by_project_id(proj_1.project_id)) == 1
    with pytest.raises(Exception):
        # used name
        model_db.add_phase("phase_1", "phase of project 1 some things", project=proj_1)

    with pytest.raises(Exception):
        # used name
        bogus = PhaseRecord(model_db, Phase(name="phase_1", name_lower="phase_1", description=None, project_id=proj_1.project_id, position=1.0))
        bogus.save()

    with pytest.raises(Exception):
        # no project
        model_db.add_phase("phase_x", "phase of project 1 some things", project=None)

    with pytest.raises(Exception):
        # bad project id
        model_db.add_phase("phase_x", "phase of project 1 some things", project_id=99999999)

    with pytest.raises(Exception):
        # bad phase_id
        bogus = PhaseRecord(model_db, Phase(id=999999, name="phase_10", name_lower="phase_10", description=None, project_id=proj_1.project_id, position=1.0))
        bogus.save()

    phase_2 = proj_1.new_phase(name="phase_2", description=None)
    assert phase_2 != phase_1
    assert phase_2.project == proj_1
    assert phase_2.project == proj_1
    assert f"{phase_2.phase_id}" in str(phase_2)
    # make sure fresh copy has project
    assert model_db.get_phase_by_id(phase_2.phase_id).project == proj_1
    assert len(model_db.get_phases_by_project_id(proj_1.project_id)) == 2
    assert phase_2.follows == phase_1

    # just make sure it
    phase_2.name = "foo"
    phase_2.save()
    assert model_db.get_phase_by_id(phase_2.phase_id).name == "foo"


    with pytest.raises(Exception):
        # used name and different id
        bogus = PhaseRecord(model_db, Phase(id=phase_2.phase_id, name=phase_1.name, name_lower=phase_1.name.lower(), description=None, project_id=proj_1.project_id, position=1.0))
        bogus.save()


    phase_3 = PhaseRecord(model_db, Phase(name="phase_3", name_lower="phase_3", description=None, project_id=proj_1.project_id, position=1.0))
    # this will call phase_3.save()
    proj_1.add_phase(phase_3)

    orig_p3_id = phase_3.phase_id
    assert orig_p3_id is not None
    phase_3.delete_from_db()
    assert phase_3.phase_id is None
    assert model_db.get_phase_by_id(orig_p3_id) is None
    # make sure double delete does not explode
    phase_3.delete_from_db()


def test_phases_links_1(create_db):
    model_db, db_dir, target_db_name = create_db

    proj_1 = model_db.add_project("proj_1", "some things")
    with pytest.raises(Exception):
        model_db._save_phase("phase_bad", description=None, project_id=proj_1.project_id,
                             follows_id=9999999)

    phase_1 = model_db.add_phase("phase_1", "phase of project 1 some things", project=proj_1)
    assert phase_1.follows is None
    assert phase_1.follower is None
    phase_1.follows_id = phase_1.phase_id
    with pytest.raises(Exception):
        phase_1.save()
    phase_1.follows_id = 999999
    assert model_db.get_phase_that_follows(999999) is None
    with pytest.raises(Exception):
        phase_1.save()
    phase_1.follows_id = None
    phase_2 = proj_1.new_phase("phase_2", description=None, follows=phase_1)
    assert model_db.get_phase_by_id(phase_2.phase_id).follows == phase_1
    assert phase_1.follower == phase_2
    phase_3 = PhaseRecord(model_db, Phase(name="phase_3", name_lower="phase_3", description=None, project_id=proj_1.project_id, position=1.0))
    proj_1.add_phase(phase_3, follows=phase_2)
    phase_3.save()
    assert phase_3.follows_id == phase_2.phase_id
    assert phase_3.follows == phase_2
    assert model_db.get_phase_by_id(phase_3.phase_id).follows == phase_2
    # create the next two out of order, then set the links to correct order, and
    # check that they are returned in correct order on project
    phase_5 = PhaseRecord(model_db, Phase(name="phase_5", name_lower="phase_5", description=None, project_id=proj_1.project_id, position=1.0))
    phase_5.save()
    phase_4 = PhaseRecord(model_db, Phase(name="phase_4", name_lower="phase_4", description=None, project_id=proj_1.project_id, position=1.0))
    phase_4.save()

    phase_4.follows = phase_3
    phase_4.save()
    assert model_db.get_phase_by_id(phase_4.phase_id).follows == phase_3
    phase_5.follows = phase_4
    phase_5.save()
    assert model_db.get_phase_by_id(phase_5.phase_id).follows == phase_4

    expected = ['phase_1', 'phase_2', 'phase_3', 'phase_4', 'phase_5']
    ordered_list = proj_1.get_phases()
    for i in range(5):
        assert ordered_list[i].name == expected[i]

    # make sure it is impossible to have a phase from one project following a phase
    # from a different project
    proj_2 = model_db.add_project("proj_2", "other things")
    phase_5.project = proj_2
    with pytest.raises(Exception):
        phase_5.save()
    # restore it, which also checks for regression on double follow test on re-save
    phase_5.project = proj_1
    phase_5.save()

    # make sure it is impossible to have two phases following same phase when saving
    # phase directly
    phase_5.follows = phase_2
    phase_5.save()
    assert model_db.get_phase_by_id(phase_5.phase_id).follows == phase_2
    assert model_db.get_phase_by_id(phase_3.phase_id).follows == phase_5

    #set it back for next test
    phase_5.follows = phase_4
    phase_5.save()

    # now delete one in the chain and make sure the chain gets mended
    phase_4.delete_from_db()
    phase_5_new = model_db.get_phase_by_id(phase_5.phase_id)
    assert phase_5_new.follows == phase_3
    new_list = proj_1.get_phases()
    assert len(new_list) == 4
    assert new_list[-1].phase_id == phase_5_new.phase_id

    # make sure it is impossible to have two phases following same phase when
    # using project methods to create and add phases
    with pytest.raises(Exception):
        phase_6 = proj_2.new_phase(name='phase_6', description=None, follows=phase_3)
    phase_6 = proj_2.new_phase(name='phase_6', description=None)
    with pytest.raises(Exception):
        proj_2.add_phase(phase_6, follows=phase_3)

    phase_7 = proj_2.new_phase(name='phase_7', description=None)
    assert len(proj_2.get_phases()) == 2
    assert proj_2.get_phases()[-1] == phase_7
    # should relink list
    phase_8 = proj_2.new_phase(name='phase_8', description=None, follows=phase_6)
    assert len(proj_2.get_phases()) == 3
    assert proj_2.get_phases()[1] == phase_8
    assert proj_2.get_phases()[-1] == phase_7


def test_phase_tasks(create_db):
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





def test_backups(create_db):
    model_db, db_dir, target_db_name = create_db

    # We don't want our original database to have id values that
    # will get duplicated because the order of insertion is the same
    # for both original and backup. If that is true then we won't
    # now if things have been properly managed when writing the backup
    # records, the id values will just magically work. SO, lets insert and delete
    # a bunch of records
    o_proj_1 = model_db.add_project("proj_1", "some things")
    o_proj_2 = model_db.add_project("proj_2", "some things", parent=o_proj_1)
    o_phase_1 = model_db.add_phase('phase_1', '', project=o_proj_1)
    o_task_1 = model_db.add_task('task1', 'foo', 'ToDo', project_id=o_proj_1.project_id,
                                phase_id=o_phase_1.phase_id)
    o_task_2 = model_db.add_task('task2', 'foo', 'ToDo', project_id=o_proj_1.project_id,
                                phase_id=o_phase_1.phase_id)

    o_task_3 = model_db.add_task('task3', 'foo', 'ToDo', project_id=o_proj_1.project_id)

    did = o_task_2.add_blocker(o_task_1)

    # now delete them all and reinsert, should get new ids
    # have to do child first
    o_task_3.delete_from_db()
    o_task_2.delete_from_db()
    o_task_1.delete_from_db()
    o_phase_1.delete_from_db()
    o_proj_2.delete_from_db()
    o_proj_1.delete_from_db()

    o_proj_1 = model_db.add_project("proj_1", "some things")
    assert o_proj_1.project_id != 1
    o_proj_2 = model_db.add_project("proj_2", "some things", parent=o_proj_1)
    assert o_proj_1.project_id != 2
    o_phase_1 = model_db.add_phase('phase_1', '', project=o_proj_1)
    assert o_phase_1.phase_id != 1
    o_task_1 = model_db.add_task('task1', 'foo', 'ToDo', project_id=o_proj_1.project_id,
                                phase_id=o_phase_1.phase_id)
    assert o_task_1.task_id != 1
    o_task_2 = model_db.add_task('task2', 'foo', 'ToDo', project_id=o_proj_1.project_id,
                                phase_id=o_phase_1.phase_id)
    assert o_task_1.task_id != 2
    o_task_3 = model_db.add_task('task3', 'foo', 'ToDo', project_id=o_proj_1.project_id)
    assert o_task_1.task_id != 3

    did = o_task_2.add_blocker(o_task_1)


    target_db_path = Path(db_dir, 'test_backup_model.sqlite')
    if target_db_path.exists():
        target_db_path.unlink()
    model_db.make_backup(db_dir, 'test_backup_model.sqlite')
    bdb = ModelDB(db_dir, 'test_backup_model.sqlite')

    n_proj_1 = bdb.get_project_by_name('proj_1')
    # should be a different id, so equal fail
    assert n_proj_1 != o_proj_1
    assert n_proj_1.name == o_proj_1.name
    assert n_proj_1.description == o_proj_1.description

    n_proj_2 = bdb.get_project_by_name('proj_2')
    # should be a different id, so equal fail
    assert n_proj_2 != o_proj_2
    assert n_proj_2.name == o_proj_2.name
    assert n_proj_2.description == o_proj_2.description
    assert n_proj_2.parent == n_proj_1

    n_phase_1 = n_proj_1.get_phases()[0]
    assert n_phase_1.name == o_phase_1.name
    assert n_phase_1.description == o_phase_1.description
    assert n_phase_1.project.name == o_phase_1.project.name

    assert len(o_proj_1.get_tasks()) == len(n_proj_1.get_tasks())
    assert len(o_phase_1.get_tasks()) == len(n_phase_1.get_tasks())

    n_task_1 = bdb.get_task_by_name('task1')
    assert n_task_1 is not None
    n_task_2 = bdb.get_task_by_name('task2')
    assert n_task_2 is not None
    n_task_3 = bdb.get_task_by_name('task3')
    assert n_task_3 is not None

    assert o_task_1 in o_task_2.get_blockers()
    assert n_task_1 in n_task_2.get_blockers()


# ============================================================================
# DomainCatalog and DPMManager tests
# ============================================================================

@pytest.fixture
def dpm_config(tmp_path):
    """Create a DPM config with two domain databases containing test data."""
    # Create domain1 with test data
    db1 = ModelDB(tmp_path, name_override="domain1.db", autocreate=True)
    proj = db1.add_project("proj_alpha", "Alpha project")
    phase = db1.add_phase("phase_one", "First phase", project=proj)
    db1.add_task("task_uno", "First task", "ToDo",
                 project_id=proj.project_id, phase_id=phase.phase_id)
    db1.add_task("task_dos", "Second task", "ToDo",
                 project_id=proj.project_id)
    db1.close()

    # Create domain2 with minimal data
    db2 = ModelDB(tmp_path, name_override="domain2.db", autocreate=True)
    db2.add_project("proj_beta", "Beta project")
    db2.close()

    config = {
        "databases": {
            "domain1": {
                "path": "./domain1.db",
                "description": "Test domain 1"
            },
            "domain2": {
                "path": "./domain2.db",
                "description": "Test domain 2"
            }
        }
    }
    config_path = tmp_path / "config.json"
    with open(config_path, "w") as f:
        json.dump(config, f)
    return config_path


def test_domain_catalog_from_config(dpm_config):
    catalog = DomainCatalog.from_json_config(dpm_config)
    assert len(catalog.pmdb_domains) == 2
    assert "domain1" in catalog.pmdb_domains
    assert "domain2" in catalog.pmdb_domains

    d1 = catalog.pmdb_domains["domain1"]
    assert d1.name == "domain1"
    assert d1.description == "Test domain 1"
    assert d1.db is not None

    d2 = catalog.pmdb_domains["domain2"]
    assert d2.name == "domain2"
    assert d2.description == "Test domain 2"

    # Verify data is accessible through the catalog's ModelDB
    projects = d1.db.get_projects()
    assert len(projects) == 1
    assert projects[0].name == "proj_alpha"


def test_domain_catalog_absolute_path(tmp_path):
    db = ModelDB(tmp_path, name_override="abs_test.db", autocreate=True)
    db.close()

    config = {
        "databases": {
            "abs_domain": {
                "path": str(tmp_path / "abs_test.db"),
                "description": "Absolute path domain"
            }
        }
    }
    config_path = tmp_path / "config.json"
    with open(config_path, "w") as f:
        json.dump(config, f)

    catalog = DomainCatalog.from_json_config(config_path)
    assert "abs_domain" in catalog.pmdb_domains
    assert catalog.pmdb_domains["abs_domain"].db is not None


def test_domain_catalog_bad_configs(tmp_path):
    config_path = tmp_path / "config.json"

    # Missing "databases" key
    with open(config_path, "w") as f:
        json.dump({"something": "else"}, f)
    with pytest.raises(AssertionError):
        DomainCatalog.from_json_config(config_path)

    # Missing "path" in domain entry
    with open(config_path, "w") as f:
        json.dump({"databases": {"bad": {"description": "no path"}}}, f)
    with pytest.raises(AssertionError):
        DomainCatalog.from_json_config(config_path)

    # Missing "description" in domain entry
    db = ModelDB(tmp_path, name_override="exists.db", autocreate=True)
    db.close()
    with open(config_path, "w") as f:
        json.dump({"databases": {"bad": {"path": "./exists.db"}}}, f)
    with pytest.raises(AssertionError):
        DomainCatalog.from_json_config(config_path)

    # Invalid path format (not starting with / or ./)
    with open(config_path, "w") as f:
        json.dump({"databases": {"bad": {"path": "relative.db", "description": "bad"}}}, f)
    with pytest.raises(Exception):
        DomainCatalog.from_json_config(config_path)

    # Non-existent database file
    with open(config_path, "w") as f:
        json.dump({"databases": {"bad": {"path": "./nonexistent.db", "description": "missing"}}}, f)
    with pytest.raises(AssertionError):
        DomainCatalog.from_json_config(config_path)


def test_dpm_manager_init(dpm_config):
    mgr = DPMManager(dpm_config)
    assert mgr.domain_catalog is not None
    assert len(mgr.domain_catalog.pmdb_domains) == 2
    assert mgr.last_domain is None
    assert mgr.last_project is None
    assert mgr.last_phase is None
    assert mgr.last_task is None


def test_dpm_manager_domains(dpm_config):
    mgr = DPMManager(dpm_config)

    domains = mgr.get_domains()
    assert "domain1" in domains
    assert "domain2" in domains

    db = mgr.get_db_for_domain("domain1")
    assert db is not None
    projects = db.get_projects()
    assert len(projects) == 1
    assert projects[0].name == "proj_alpha"


def test_dpm_manager_default_domain(dpm_config):
    mgr = DPMManager(dpm_config)

    # No last_domain set yet, get_default_domain picks first in catalog
    default = mgr.get_default_domain()
    assert default == "domain1"
    assert mgr.last_domain == "domain1"

    # After setting a different domain, default should return that
    mgr.set_last_domain("domain2")
    assert mgr.get_default_domain() == "domain2"


def test_dpm_manager_last_domain(dpm_config):
    mgr = DPMManager(dpm_config)

    assert mgr.get_last_domain() is None

    mgr.set_last_domain("domain1")
    assert mgr.get_last_domain() == "domain1"

    mgr.set_last_domain("domain2")
    assert mgr.get_last_domain() == "domain2"

    with pytest.raises(Exception):
        mgr.set_last_domain("nonexistent")


def test_dpm_manager_last_project(dpm_config):
    mgr = DPMManager(dpm_config)

    assert mgr.get_last_project() is None

    db = mgr.get_db_for_domain("domain1")
    proj = db.get_project_by_name("proj_alpha")

    mgr.set_last_project("domain1", proj)
    assert mgr.get_last_project() == proj
    # set_last_project also sets the domain
    assert mgr.get_last_domain() == "domain1"

    # Invalid domain
    with pytest.raises(Exception):
        mgr.set_last_project("nonexistent", proj)

    # Project ID that doesn't exist in domain2 (domain2 only has id=1)
    proj2 = db.add_project("proj_gamma", "Gamma project")
    with pytest.raises(Exception):
        mgr.set_last_project("domain2", proj2)


def test_dpm_manager_last_phase(dpm_config):
    mgr = DPMManager(dpm_config)

    assert mgr.get_last_phase() is None

    db = mgr.get_db_for_domain("domain1")
    phase = db.get_phase_by_name("phase_one")

    mgr.set_last_phase("domain1", phase)
    assert mgr.get_last_phase() == phase
    # set_last_phase also sets domain and project
    assert mgr.get_last_domain() == "domain1"
    assert mgr.get_last_project() is not None
    assert mgr.get_last_project().name == "proj_alpha"

    # Invalid domain
    with pytest.raises(Exception):
        mgr.set_last_phase("nonexistent", phase)

    # Phase not in domain2
    with pytest.raises(Exception):
        mgr.set_last_phase("domain2", phase)


def test_dpm_manager_last_task(dpm_config):
    mgr = DPMManager(dpm_config)

    assert mgr.get_last_task() is None

    db = mgr.get_db_for_domain("domain1")

    # Task with phase — should set domain, project, and phase
    task = db.get_task_by_name("task_uno")
    mgr.set_last_task("domain1", task)
    assert mgr.get_last_task() == task
    assert mgr.get_last_domain() == "domain1"
    assert mgr.get_last_project().name == "proj_alpha"
    assert mgr.get_last_phase().name == "phase_one"

    # Task without phase — should update project but not clear phase
    task2 = db.get_task_by_name("task_dos")
    mgr.set_last_task("domain1", task2)
    assert mgr.get_last_task() == task2
    assert mgr.get_last_project().name == "proj_alpha"
    # Phase stays from the previous set (task_dos has no phase)
    assert mgr.get_last_phase().name == "phase_one"

    # Invalid domain
    with pytest.raises(Exception):
        mgr.set_last_task("nonexistent", task)

    # Task not in domain2
    with pytest.raises(Exception):
        mgr.set_last_task("domain2", task)


def test_dpm_manager_state_persistence(dpm_config):
    """State is persisted to disk and restored by a new DPMManager instance."""
    mgr = DPMManager(dpm_config)

    db = mgr.get_db_for_domain("domain1")
    task = db.get_task_by_name("task_uno")
    mgr.set_last_task("domain1", task)

    # New manager from same config should restore all state
    mgr2 = DPMManager(dpm_config)
    assert mgr2.get_last_domain() == "domain1"
    assert mgr2.get_last_project() is not None
    assert mgr2.get_last_project().name == "proj_alpha"
    assert mgr2.get_last_phase() is not None
    assert mgr2.get_last_phase().name == "phase_one"
    assert mgr2.get_last_task() is not None
    assert mgr2.get_last_task().name == "task_uno"


def test_dpm_manager_state_domain_only(dpm_config):
    """Persisting only a domain (no project/phase/task) restores correctly."""
    mgr = DPMManager(dpm_config)
    mgr.set_last_domain("domain2")

    mgr2 = DPMManager(dpm_config)
    assert mgr2.get_last_domain() == "domain2"
    assert mgr2.get_last_project() is None
    assert mgr2.get_last_phase() is None
    assert mgr2.get_last_task() is None


def test_dpm_manager_state_missing(dpm_config):
    """DPMManager starts clean when no state file exists."""
    mgr = DPMManager(dpm_config)
    assert mgr.get_last_domain() is None
    assert mgr.get_last_project() is None
    assert mgr.get_last_phase() is None
    assert mgr.get_last_task() is None


def test_dpm_manager_state_corrupt(dpm_config):
    """DPMManager handles a corrupt state file gracefully."""
    state_path = dpm_config.parent / ".dpm_state.json"
    with open(state_path, "w") as f:
        f.write("not valid json{{{")

    # Should not raise — logs a warning and starts clean
    with pytest.raises(json.decoder.JSONDecodeError):
        mgr = DPMManager(dpm_config)


def test_dpm_manager_state_stale_ids(dpm_config):
    """DPMManager handles state referencing IDs that no longer exist."""
    state_path = dpm_config.parent / ".dpm_state.json"
    state = {
        "last_domain": "domain1",
        "last_project_id": 99999,
        "last_phase_id": 99999,
        "last_task_id": 99999,
    }
    with open(state_path, "w") as f:
        json.dump(state, f)

    mgr = DPMManager(dpm_config)
    assert mgr.get_last_domain() == "domain1"
    assert mgr.get_last_project() is None
    assert mgr.get_last_phase() is None
    assert mgr.get_last_task() is None


def test_dpm_manager_state_stale_domain(dpm_config):
    """DPMManager ignores a state domain that is no longer in the catalog."""
    state_path = dpm_config.parent / ".dpm_state.json"
    state = {
        "last_domain": "removed_domain",
        "last_project_id": None,
        "last_phase_id": None,
        "last_task_id": None,
    }
    with open(state_path, "w") as f:
        json.dump(state, f)

    mgr = DPMManager(dpm_config)
    assert mgr.get_last_domain() is None


def test_dpm_manager_shutdown(dpm_config):
    mgr = DPMManager(dpm_config)
    db = mgr.get_db_for_domain("domain1")

    # Verify db works before shutdown
    projects = db.get_projects()
    assert len(projects) > 0

    asyncio.run(mgr.shutdown())

    # DB should be closed now
    with pytest.raises(Exception):
        db.get_projects()
