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

def test_epic_simple(create_db, tmp_path):
    model_db, db_dir, target_db_name = create_db
    model_db.close()
    
    config = {
        "databases": {
            "TestDomain": {
                "path": str(db_dir / target_db_name),
                "description": "Test domain 1"
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
    assert epic1 
    
