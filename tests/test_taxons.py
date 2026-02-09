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

from dpm.store.taxons import (DPMBase, TaxonDef, TaxonLevel,
                               TaxonDefRecord, TaxonLevelRecord)

def make_sw_taxonomy(db):
    taxonomy = db.add_taxon_def(
        name="Software Project",
        covers_dpm=DPMBase.domain,
    )
    vision = db.add_taxon_def(
        name="Vision",
        covers_dpm=DPMBase.project,
        parent_id=taxonomy.taxon_def_id,
        allow_multiple=False,
    )
    deliverable = db.add_taxon_def(
        name="Deliverable",
        covers_dpm=DPMBase.project,
        parent_id=vision.taxon_def_id,
    )
    epic = db.add_taxon_def(
        name="Epic",
        covers_dpm=DPMBase.project,
        parent_id=deliverable.taxon_def_id,
    )
    story = db.add_taxon_def(
        name="Story",
        covers_dpm=DPMBase.phase,
        parent_id=epic.taxon_def_id,
    )
    task = db.add_taxon_def(
        name="Task",
        covers_dpm=DPMBase.task,
        parent_id=story.taxon_def_id,
    )
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

    taxonomy_def = make_sw_taxonomy(db1)
    top = db1.add_taxon_level_for_domain(catalog=catalog, taxon_def_record=taxonomy_def, name="TestDomain")
    # Okay, so you'd never really do this, just inferring a structure of inferences from
    # the structure of the taxonomy, but it is handy for testing
    def add_level(parent, level_index=0):
        for index, child_def in enumerate(parent.taxo_def.children):
            if child_def.covers_dpm == DPMBase.project:
                if parent.taxo_type == DPMBase.domain:
                    domain_level = parent
                    parent_level = None
                else:
                    domain_level = parent.domain_level
                    parent_level = parent
                level = db1.add_taxon_level_for_project(
                    domain_level=domain_level,
                    parent_level=parent_level,
                    taxon_def_record=child_def,
                    name=f"Level {level_index} item {index}")
            elif child_def.covers_dpm == DPMBase.phase:
                level = db1.add_taxon_level_for_phase(
                    project_level=parent,
                    taxon_def_record=child_def,
                    name=f"Level {level_index} item {index}")
            elif child_def.covers_dpm == DPMBase.task:
                level = db1.add_taxon_level_for_task(
                    parent_level=parent,
                    taxon_def_record=child_def,
                    name=f"Level {level_index} item {index}")
            else:
                raise Exception('')
            add_level(level, level_index+1)
    add_level(top, 0)
    top_kids = top.get_children()
    
    



