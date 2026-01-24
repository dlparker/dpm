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
                                FilterWrapper, Task, Project, Phase)


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
        bad_db = ModelDB('/tmp_not_there')

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


def test_wrappers_1(create_db):
    model_db, db_dir, target_db_name = create_db

    proj_1 = model_db.add_project("proj_1", "some things")
    assert "proj_1" in str(proj_1)
    proj_wrap = proj_1.get_tracking_wrapper()
    assert not proj_wrap.is_changed()
    proj_wrap.description = "diff"
    assert proj_wrap.description == "diff"
    assert proj_wrap._orig_description != proj_1.description
    assert proj_wrap.is_changed()
    assert "description" in proj_wrap.get_changes()
    proj_wrap.revert()
    assert not proj_wrap.is_changed()

    # make sure get and set work on wrapped
    wrapped = proj_wrap.__getattr__('_wrapped')
    proj_wrap._wrapped = wrapped

    phase_1 = model_db.add_phase('phase_1', '', project=proj_1)
    phase_wrap = phase_1.get_tracking_wrapper()
    assert not phase_wrap.is_changed()
    phase_1.description = "diff"
    assert phase_wrap.is_changed()
    assert "description" in phase_wrap.get_changes()
    phase_wrap.revert()
    assert not phase_wrap.is_changed()

    task_1 = model_db.add_task('task1', 'foo', 'ToDo', project_id=proj_1.project_id, phase_id=phase_1.phase_id)
    task_1_wrap = task_1.get_tracking_wrapper()
    assert not task_1_wrap.is_changed()
    task_1.description = "diff"
    assert task_1_wrap.is_changed()
    assert "description" in task_1_wrap.get_changes()
    task_1_wrap.revert()
    assert not task_1_wrap.is_changed()

    proj_2 = model_db.add_project("proj_2", "other things")
    phase_2 = model_db.add_phase('phase_2', '', project=proj_1)

    task_1.phase = phase_2
    assert task_1_wrap.is_changed()
    task_1_wrap.revert()
    assert not task_1_wrap.is_changed()

    task_1.project = proj_2
    assert task_1_wrap.is_changed()
    task_1_wrap.revert()
    assert not task_1_wrap.is_changed()

    task_2 = model_db.add_task('task2', 'foo', 'ToDo', project_id=proj_1.project_id,
                              phase_id=phase_1.phase_id)
    phase_3 = model_db.add_phase('phase_3', '', project=proj_2)
    task_2_wrap = task_2.get_tracking_wrapper()
    task_2.project = proj_2
    assert task_2_wrap.is_changed()
    task_2_wrap.save()
    task_2 = model_db.get_task_by_id(task_2.task_id)
    assert task_2.project == proj_2
    assert task_2.phase is None


def test_json(create_db):
    model_db, db_dir, target_db_name = create_db

    proj_1 = model_db.add_project("proj_1", "some things")
    pj1 = json.dumps(proj_1.to_json_dict())
    assert "proj_1" in pj1
    phase_1 = model_db.add_phase('phase_1', '', project=proj_1)
    jd = phase_1.to_json_dict()
    ph1 = json.dumps(jd)
    assert "phase_1" in ph1

    task_1 = model_db.add_task('task1', 'foo', 'ToDo', project_id=proj_1.project_id)
    # now just make sure our filter works with supplied value
    j1 = json.dumps(task_1.to_json_dict())
    fw2 = FilterWrapper(task_1.to_json_dict())
    fw2.filter_key('project_id')
    j2 = json.dumps(fw2)
    assert "project_id" in j1
    assert "project_id" not in j2



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
