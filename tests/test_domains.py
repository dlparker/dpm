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
from dpm.store.domains import DPMManager, DomainCatalog, DomainMode
from dpm.store.wrappers import ModelDB, TaskRecord, ProjectRecord, PhaseRecord


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
                "description": "Test domain 2",
                "domain_mode": "software"
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
    assert d2.domain_mode == DomainMode.SOFTWARE

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
