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
from sqlalchemy.util.langhelpers import textwrap

from dpm.store.wrappers import ModelDB
from dpm.store.domains import DomainCatalog

@pytest.fixture
def create_db():
    db_dir = Path("/tmp")
    target_db_name = "discard_test_model_db.sqlite"
    target_db_path = db_dir / target_db_name
    if target_db_path.exists():
        target_db_path.unlink()
    model_db = ModelDB(db_dir, name_override=target_db_name, autocreate=True)
    return [model_db, db_dir, target_db_name]

def test_wrappers_simple(create_db, tmp_path):
    model_db, db_dir, target_db_name = create_db
    model_db.close()
    
    config = {
        "databases": {
            "TestDomain": {
                "path": str(db_dir / target_db_name),
                "description": "Test domain 1",
                "domain_mode": "software"
            }
        }
    }
    config_path = tmp_path / "config.json"
    with open(config_path, "w") as f:
        json.dump(config, f)
    catalog = DomainCatalog.from_json_config(config_path)

    domain = catalog.pmdb_domains['TestDomain']
    assert domain.db
    db = domain.db
    epic1 = db.sw_model_db.add_epic(domain, "epic1")
    vision1 = db.sw_model_db.add_vision(domain, "vision1")
    epic2 = db.sw_model_db.add_epic(domain, "epic2", vision=vision1)
    sub1 = db.sw_model_db.add_subsystem(domain, "sub1")
    epic3 = db.sw_model_db.add_epic(domain, "epic3", subsystem=sub1)
    sub2 = db.sw_model_db.add_subsystem(domain, "sub2", vision=vision1)
    epic4 = db.sw_model_db.add_epic(domain, "epic4", subsystem=sub2)

    deli1 = db.sw_model_db.add_deliverable(domain, "deliverable1")
    deli2 = db.sw_model_db.add_deliverable(domain, "deliverable2", vision=vision1)
    deli3 = db.sw_model_db.add_deliverable(domain, "deliverable3", subsystem=sub1)
    epic5 = db.sw_model_db.add_epic(domain, "epic5", deliverable=deli3)

    story1 = db.sw_model_db.add_story(domain, "story1", vision=vision1)
    story2 = db.sw_model_db.add_story(domain, "story2", subsystem=sub1)
    story3 = db.sw_model_db.add_story(domain, "story3", deliverable=deli3)
    story4 = db.sw_model_db.add_story(domain, "story4", epic=epic5)
    
    task1 = db.sw_model_db.add_task(domain, "task1", vision=vision1)
    task2 = db.sw_model_db.add_task(domain, "task2", subsystem=sub1)
    task3 = db.sw_model_db.add_task(domain, "task3", deliverable=deli3)
    task4 = db.sw_model_db.add_task(domain, "task4", epic=epic5)
    task5 = db.sw_model_db.add_task(domain, "task5", story=story4)
    
    
    
