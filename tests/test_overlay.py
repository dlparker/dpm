#!/usr/bin/env python
"""
Test interoperability between TaskDB (direct sqlite) and ModelDB (SqlModel).

These tests verify that databases created by one implementation can be
correctly read and modified by the other, ensuring schema compatibility.
"""
import sys
import os
from pathlib import Path
import pytest

from dpm.store.task_db import TaskDB
from dpm.store.models import ModelDB


@pytest.fixture
def shared_db_path():
    """Provide a shared database path for cross-implementation tests."""
    db_dir = Path("/tmp")
    target_db_name = "overlay_test_db.sqlite"
    target_db_path = db_dir / target_db_name
    if target_db_path.exists():
        target_db_path.unlink()
    return [db_dir, target_db_name, target_db_path]


def test_taskdb_write_modeldb_read(shared_db_path):
    """Test that data written by TaskDB can be read by ModelDB."""
    db_dir, target_db_name, target_db_path = shared_db_path

    # Write with TaskDB
    task_db = TaskDB(db_dir, name_override=target_db_name, autocreate=True)

    proj_1 = task_db.add_project("proj_1", "project one description")
    proj_2 = task_db.add_project("proj_2", "child project", parent=proj_1)

    phase_1 = task_db.add_phase("phase_1", "first phase", project=proj_1)
    phase_2 = proj_1.new_phase("phase_2", "second phase", follows=phase_1)

    task_1 = task_db.add_task("task_1", "first task", "ToDo",
                               project_id=proj_1.project_id, phase_id=phase_1.phase_id)
    task_2 = task_db.add_task("task_2", "second task", "Doing",
                               project_id=proj_1.project_id, phase_id=phase_1.phase_id)
    task_3 = task_db.add_task("task_3", "blocking task", "ToDo",
                               project_id=proj_1.project_id)

    task_2.add_blocker(task_1)
    task_2.add_blocker(task_3)

    task_db.close()

    # Read with ModelDB
    model_db = ModelDB(db_dir, name_override=target_db_name)

    # Verify projects
    m_proj_1 = model_db.get_project_by_name("proj_1")
    assert m_proj_1 is not None
    assert m_proj_1.description == "project one description"
    assert m_proj_1.parent_id is None

    m_proj_2 = model_db.get_project_by_name("proj_2")
    assert m_proj_2 is not None
    assert m_proj_2.parent_id == m_proj_1.project_id

    # Verify phases
    m_phase_1 = model_db.get_phase_by_name("phase_1")
    assert m_phase_1 is not None
    assert m_phase_1.project_id == m_proj_1.project_id
    assert m_phase_1.follows_id is None

    m_phase_2 = model_db.get_phase_by_name("phase_2")
    assert m_phase_2 is not None
    assert m_phase_2.follows_id == m_phase_1.phase_id

    # Verify phase ordering
    phases = m_proj_1.get_phases()
    assert len(phases) == 2
    assert phases[0].name == "phase_1"
    assert phases[1].name == "phase_2"

    # Verify tasks
    m_task_1 = model_db.get_task_by_name("task_1")
    assert m_task_1 is not None
    assert m_task_1.status == "ToDo"
    assert m_task_1.phase_id == m_phase_1.phase_id

    m_task_2 = model_db.get_task_by_name("task_2")
    assert m_task_2 is not None
    assert m_task_2.status == "Doing"

    # Verify blockers
    blockers = m_task_2.get_blockers(only_not_done=False)
    blocker_ids = [b.task_id for b in blockers]
    assert m_task_1.task_id in blocker_ids
    assert model_db.get_task_by_name("task_3").task_id in blocker_ids

    model_db.close()


def test_modeldb_write_taskdb_read(shared_db_path):
    """Test that data written by ModelDB can be read by TaskDB."""
    db_dir, target_db_name, target_db_path = shared_db_path

    # Write with ModelDB
    model_db = ModelDB(db_dir, name_override=target_db_name, autocreate=True)

    proj_1 = model_db.add_project("proj_1", "project one description")
    proj_2 = model_db.add_project("proj_2", "child project", parent=proj_1)

    phase_1 = model_db.add_phase("phase_1", "first phase", project=proj_1)
    phase_2 = proj_1.new_phase("phase_2", "second phase", follows=phase_1)

    task_1 = model_db.add_task("task_1", "first task", "ToDo",
                                project_id=proj_1.project_id, phase_id=phase_1.phase_id)
    task_2 = model_db.add_task("task_2", "second task", "Doing",
                                project_id=proj_1.project_id, phase_id=phase_1.phase_id)
    task_3 = model_db.add_task("task_3", "blocking task", "ToDo",
                                project_id=proj_1.project_id)

    task_2.add_blocker(task_1)
    task_2.add_blocker(task_3)

    model_db.close()

    # Read with TaskDB
    task_db = TaskDB(db_dir, name_override=target_db_name)

    # Verify projects
    t_proj_1 = task_db.get_project_by_name("proj_1")
    assert t_proj_1 is not None
    assert t_proj_1.description == "project one description"
    assert t_proj_1.parent_id is None

    t_proj_2 = task_db.get_project_by_name("proj_2")
    assert t_proj_2 is not None
    assert t_proj_2.parent_id == t_proj_1.project_id

    # Verify phases
    t_phase_1 = task_db.get_phase_by_name("phase_1")
    assert t_phase_1 is not None
    assert t_phase_1.project_id == t_proj_1.project_id
    assert t_phase_1.follows_id is None

    t_phase_2 = task_db.get_phase_by_name("phase_2")
    assert t_phase_2 is not None
    assert t_phase_2.follows_id == t_phase_1.phase_id

    # Verify phase ordering
    phases = t_proj_1.get_phases()
    assert len(phases) == 2
    assert phases[0].name == "phase_1"
    assert phases[1].name == "phase_2"

    # Verify tasks
    t_task_1 = task_db.get_task_by_name("task_1")
    assert t_task_1 is not None
    assert t_task_1.status == "ToDo"
    assert t_task_1.phase_id == t_phase_1.phase_id

    t_task_2 = task_db.get_task_by_name("task_2")
    assert t_task_2 is not None
    assert t_task_2.status == "Doing"

    # Verify blockers
    blockers = t_task_2.get_blockers(only_not_done=False)
    blocker_ids = [b.task_id for b in blockers]
    assert t_task_1.task_id in blocker_ids
    assert task_db.get_task_by_name("task_3").task_id in blocker_ids

    task_db.close()


def test_mixed_writes_taskdb_first(shared_db_path):
    """Test interleaved writes: TaskDB creates, ModelDB modifies, TaskDB reads."""
    db_dir, target_db_name, target_db_path = shared_db_path

    # TaskDB creates initial data
    task_db = TaskDB(db_dir, name_override=target_db_name, autocreate=True)
    proj_1 = task_db.add_project("proj_1", "original description")
    phase_1 = task_db.add_phase("phase_1", "original phase", project=proj_1)
    task_1 = task_db.add_task("task_1", "original task", "ToDo",
                               project_id=proj_1.project_id, phase_id=phase_1.phase_id)
    task_db.close()

    # ModelDB modifies data
    model_db = ModelDB(db_dir, name_override=target_db_name)
    m_proj_1 = model_db.get_project_by_name("proj_1")
    m_proj_1.description = "modified by ModelDB"
    m_proj_1.save()

    m_task_1 = model_db.get_task_by_name("task_1")
    m_task_1.status = "Done"
    m_task_1.description = "completed by ModelDB"
    m_task_1.save()

    # ModelDB adds new data
    phase_2 = m_proj_1.new_phase("phase_2", "added by ModelDB")
    task_2 = model_db.add_task("task_2", "new task by ModelDB", "ToDo",
                                project_id=m_proj_1.project_id, phase_id=phase_2.phase_id)
    model_db.close()

    # TaskDB reads and verifies
    task_db = TaskDB(db_dir, name_override=target_db_name)

    t_proj_1 = task_db.get_project_by_name("proj_1")
    assert t_proj_1.description == "modified by ModelDB"

    t_task_1 = task_db.get_task_by_name("task_1")
    assert t_task_1.status == "Done"
    assert t_task_1.description == "completed by ModelDB"

    t_phase_2 = task_db.get_phase_by_name("phase_2")
    assert t_phase_2 is not None
    assert t_phase_2.description == "added by ModelDB"

    t_task_2 = task_db.get_task_by_name("task_2")
    assert t_task_2 is not None
    assert t_task_2.phase_id == t_phase_2.phase_id

    task_db.close()


def test_mixed_writes_modeldb_first(shared_db_path):
    """Test interleaved writes: ModelDB creates, TaskDB modifies, ModelDB reads."""
    db_dir, target_db_name, target_db_path = shared_db_path

    # ModelDB creates initial data
    model_db = ModelDB(db_dir, name_override=target_db_name, autocreate=True)
    proj_1 = model_db.add_project("proj_1", "original description")
    phase_1 = model_db.add_phase("phase_1", "original phase", project=proj_1)
    task_1 = model_db.add_task("task_1", "original task", "ToDo",
                                project_id=proj_1.project_id, phase_id=phase_1.phase_id)
    model_db.close()

    # TaskDB modifies data
    task_db = TaskDB(db_dir, name_override=target_db_name)
    t_proj_1 = task_db.get_project_by_name("proj_1")
    t_proj_1.description = "modified by TaskDB"
    t_proj_1.save()

    t_task_1 = task_db.get_task_by_name("task_1")
    t_task_1.status = "Done"
    t_task_1.description = "completed by TaskDB"
    t_task_1.save()

    # TaskDB adds new data
    phase_2 = t_proj_1.new_phase("phase_2", "added by TaskDB")
    task_2 = task_db.add_task("task_2", "new task by TaskDB", "ToDo",
                               project_id=t_proj_1.project_id, phase_id=phase_2.phase_id)
    task_db.close()

    # ModelDB reads and verifies
    model_db = ModelDB(db_dir, name_override=target_db_name)

    m_proj_1 = model_db.get_project_by_name("proj_1")
    assert m_proj_1.description == "modified by TaskDB"

    m_task_1 = model_db.get_task_by_name("task_1")
    assert m_task_1.status == "Done"
    assert m_task_1.description == "completed by TaskDB"

    m_phase_2 = model_db.get_phase_by_name("phase_2")
    assert m_phase_2 is not None
    assert m_phase_2.description == "added by TaskDB"

    m_task_2 = model_db.get_task_by_name("task_2")
    assert m_task_2 is not None
    assert m_task_2.phase_id == m_phase_2.phase_id

    model_db.close()


def test_blocker_interop(shared_db_path):
    """Test that blocker relationships work across implementations."""
    db_dir, target_db_name, target_db_path = shared_db_path

    # TaskDB creates tasks
    task_db = TaskDB(db_dir, name_override=target_db_name, autocreate=True)
    proj_1 = task_db.add_project("proj_1", "test project")
    task_1 = task_db.add_task("task_1", "blocker", "ToDo", project_id=proj_1.project_id)
    task_2 = task_db.add_task("task_2", "blocked", "ToDo", project_id=proj_1.project_id)
    task_db.close()

    # ModelDB adds blocker relationship
    model_db = ModelDB(db_dir, name_override=target_db_name)
    m_task_1 = model_db.get_task_by_name("task_1")
    m_task_2 = model_db.get_task_by_name("task_2")
    m_task_2.add_blocker(m_task_1)
    model_db.close()

    # TaskDB verifies blocker
    task_db = TaskDB(db_dir, name_override=target_db_name)
    t_task_2 = task_db.get_task_by_name("task_2")
    blockers = t_task_2.get_blockers()
    assert len(blockers) == 1
    assert blockers[0].name == "task_1"

    # TaskDB adds another task and blocker
    task_3 = task_db.add_task("task_3", "another blocker", "ToDo",
                               project_id=proj_1.project_id)
    t_task_2.add_blocker(task_3)
    task_db.close()

    # ModelDB verifies both blockers
    model_db = ModelDB(db_dir, name_override=target_db_name)
    m_task_2 = model_db.get_task_by_name("task_2")
    blockers = m_task_2.get_blockers()
    assert len(blockers) == 2
    blocker_names = [b.name for b in blockers]
    assert "task_1" in blocker_names
    assert "task_3" in blocker_names
    model_db.close()


def test_delete_interop(shared_db_path):
    """Test that deletes work correctly across implementations."""
    db_dir, target_db_name, target_db_path = shared_db_path

    # TaskDB creates data
    task_db = TaskDB(db_dir, name_override=target_db_name, autocreate=True)
    proj_1 = task_db.add_project("proj_1", "test project")
    phase_1 = task_db.add_phase("phase_1", "test phase", project=proj_1)
    task_1 = task_db.add_task("task_1", "to delete", "ToDo",
                               project_id=proj_1.project_id, phase_id=phase_1.phase_id)
    task_2 = task_db.add_task("task_2", "to keep", "ToDo",
                               project_id=proj_1.project_id, phase_id=phase_1.phase_id)
    task_db.close()

    # ModelDB deletes task_1
    model_db = ModelDB(db_dir, name_override=target_db_name)
    m_task_1 = model_db.get_task_by_name("task_1")
    m_task_1.delete_from_db()
    model_db.close()

    # TaskDB verifies deletion
    task_db = TaskDB(db_dir, name_override=target_db_name)
    assert task_db.get_task_by_name("task_1") is None
    assert task_db.get_task_by_name("task_2") is not None

    # TaskDB deletes phase (should orphan task_2)
    t_phase_1 = task_db.get_phase_by_name("phase_1")
    t_phase_1.delete_from_db()
    task_db.close()

    # ModelDB verifies phase deletion and task orphaning
    model_db = ModelDB(db_dir, name_override=target_db_name)
    assert model_db.get_phase_by_name("phase_1") is None
    m_task_2 = model_db.get_task_by_name("task_2")
    assert m_task_2 is not None
    assert m_task_2.phase_id is None
    assert m_task_2.project_id is not None
    model_db.close()


def test_phase_ordering_interop(shared_db_path):
    """Test that phase ordering (position field) works across implementations."""
    db_dir, target_db_name, target_db_path = shared_db_path

    # TaskDB creates phases in order
    task_db = TaskDB(db_dir, name_override=target_db_name, autocreate=True)
    proj_1 = task_db.add_project("proj_1", "test project")
    phase_1 = task_db.add_phase("phase_1", "first", project=proj_1)
    phase_2 = proj_1.new_phase("phase_2", "second", follows=phase_1)
    phase_3 = proj_1.new_phase("phase_3", "third", follows=phase_2)
    task_db.close()

    # ModelDB verifies order and inserts a phase between 1 and 2
    model_db = ModelDB(db_dir, name_override=target_db_name)
    m_proj_1 = model_db.get_project_by_name("proj_1")
    phases = m_proj_1.get_phases()
    assert [p.name for p in phases] == ["phase_1", "phase_2", "phase_3"]

    m_phase_1 = model_db.get_phase_by_name("phase_1")
    phase_1_5 = m_proj_1.new_phase("phase_1_5", "inserted", follows=m_phase_1)
    model_db.close()

    # TaskDB verifies new order
    task_db = TaskDB(db_dir, name_override=target_db_name)
    t_proj_1 = task_db.get_project_by_name("proj_1")
    phases = t_proj_1.get_phases()
    assert [p.name for p in phases] == ["phase_1", "phase_1_5", "phase_2", "phase_3"]
    task_db.close()


def test_project_hierarchy_interop(shared_db_path):
    """Test that project parent/child relationships work across implementations."""
    db_dir, target_db_name, target_db_path = shared_db_path

    # TaskDB creates hierarchy
    task_db = TaskDB(db_dir, name_override=target_db_name, autocreate=True)
    proj_root = task_db.add_project("root", "root project")
    proj_child_1 = task_db.add_project("child_1", "first child", parent=proj_root)
    proj_child_2 = task_db.add_project("child_2", "second child", parent=proj_root)
    task_db.close()

    # ModelDB verifies and adds grandchild
    model_db = ModelDB(db_dir, name_override=target_db_name)
    m_root = model_db.get_project_by_name("root")
    kids = m_root.get_kids()
    assert len(kids) == 2
    kid_names = [k.name for k in kids]
    assert "child_1" in kid_names
    assert "child_2" in kid_names

    m_child_1 = model_db.get_project_by_name("child_1")
    grandchild = model_db.add_project("grandchild", "grandchild project", parent=m_child_1)
    model_db.close()

    # TaskDB verifies grandchild
    task_db = TaskDB(db_dir, name_override=target_db_name)
    t_grandchild = task_db.get_project_by_name("grandchild")
    assert t_grandchild is not None
    assert t_grandchild.parent.name == "child_1"
    assert t_grandchild.parent.parent.name == "root"
    task_db.close()
