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

from dpm.store.models import ModelDB,  Task, Project, Phase, Task, DPMManager, DomainCatalog
from dpm.store.wrappers import TaskRecord, ProjectRecord, PhaseRecord

from dpm.store.taxons import (DPMBase, TaxonDef, TaxonLevel,
                               TaxonDefRecord, TaxonLevelRecord, build_software_suite_taxonomy, build_software_taxonomy)

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
    taxonomy_def = build_software_taxonomy(db1)
    #taxonomy_suite_def = build_software_suite_taxonomy(db1)
    config_path = tmp_path / "config.json"
    with open(config_path, "w") as f:
        json.dump(config, f)
    catalog = DomainCatalog.from_json_config(config_path)

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

def test_sw_project(create_db, tmp_path):
    db1 = ModelDB(tmp_path, name_override="test_domain.db", autocreate=True)
    config = {
        "databases": {
            "DPM_PROJECT": {
                "path": "./test_domain.db",
                "description": "DPM software project"
            }
        }
    }
    taxonomy_def = build_software_taxonomy(db1)
    config_path = tmp_path / "config.json"
    with open(config_path, "w") as f:
        json.dump(config, f)
    catalog = DomainCatalog.from_json_config(config_path)

    top = db1.add_taxon_level_for_domain(catalog=catalog, taxon_def_record=taxonomy_def, name="DPM_PROJECT")

    vision_def = taxonomy_def.get_child_by_name('Vision')
    assert vision_def
    desc = """"Speed and simplicity for project management, kanban style tracking,
    dependency relationships without dates, customized flavors for
    categories of similar projects.
    """
    vision = top.add_project_level(taxon_def_record=vision_def,
                                   name="Project managenent tool supporting dependencies and custom flavors",
                                   description=textwrap.dedent(desc))
    
    deliverable_def = taxonomy_def.get_child_by_name('Deliverable')
    assert deliverable_def
    desc = """"First version of flavor support, adding software project flavor"""
    deliverable = vision.add_project_level(taxon_def_record=deliverable_def,
                                           name="Flavors prototype",
                                           description=textwrap.dedent(desc))
    
    
    epic_def = taxonomy_def.get_child_by_name('Epic')
    assert epic_def
    epic = deliverable.add_child(taxon_def_record=epic_def,
                                 name="Databse support for taxonomies")

    assert epic
    assert isinstance(epic.dpm_model, ProjectRecord)
    
    story_def = taxonomy_def.get_child_by_name('Story')
    assert story_def
    story = epic.add_child(taxon_def_record=story_def,
                           name="Test taxon models/utils")

    assert story
    assert isinstance(story.dpm_model, PhaseRecord)
    task_def = taxonomy_def.get_child_by_name('Task')
    assert task_def
    task = story.add_child(taxon_def_record=task_def,
                           name="Test creation of one software project with all levels")

    assert task
    assert isinstance(task.dpm_model, TaskRecord)


def test_sw_suite(create_db, tmp_path):
    db1 = ModelDB(tmp_path, name_override="test_domain.db", autocreate=True)
    config = {
        "databases": {
            "ASSIST_PROJECT": {
                "path": "./test_domain.db",
                "description": "ASSISTANT software mega-project"
            }
        }
    }
    taxonomy_def = build_software_suite_taxonomy(db1)
    config_path = tmp_path / "config.json"
    with open(config_path, "w") as f:
        json.dump(config, f)
    catalog = DomainCatalog.from_json_config(config_path)

    top = db1.add_taxon_level_for_domain(catalog=catalog, taxon_def_record=taxonomy_def, name="ASSIST_PROJECT")

    vision_def = taxonomy_def.get_child_by_name('Vision')
    assert vision_def
    desc = """"LLM powered assistant with multimodal interface including voice"""
    vision = top.add_project_level(taxon_def_record=vision_def,
                                   name="AI Assistant",
                                   description=textwrap.dedent(desc))
    
    subsystem_def = taxonomy_def.get_child_by_name('Subsystem')
    assert subsystem_def
    desc = """"Voice to Text multiple drafts mechanism"""
    palaver = vision.add_project_level(taxon_def_record=subsystem_def,
                                           name="Palaver",
                                           description=textwrap.dedent(desc))
    
    
    deliverable_def = taxonomy_def.get_child_by_name('Deliverable')
    assert deliverable_def
    rescan = palaver.add_project_level(taxon_def_record=deliverable_def,
                                           name="palaver multiple drafts",
                                           description=textwrap.dedent(desc))
    
    
    epic_def = taxonomy_def.get_child_by_name('Epic')
    assert epic_def
    epic_1 = rescan.add_child(taxon_def_record=epic_def,
                                 name="add rescan monitor")

    assert epic_1
    assert isinstance(epic_1.dpm_model, ProjectRecord)
    
    story_def = taxonomy_def.get_child_by_name('Story')
    assert story_def
    story_1 = epic_1.add_child(taxon_def_record=story_def,
                           name="add remove draft trigger to draft finder")

    assert story_1
    assert isinstance(story_1.dpm_model, PhaseRecord)
    task_def = taxonomy_def.get_child_by_name('Task')
    assert task_def
    task_1 = story_1.add_child(taxon_def_record=task_def,
                               name="add try hint text_event logic")
    assert task_1
    assert isinstance(task_1.dpm_model, TaskRecord)
    

    ## gibbon stuff
    
    desc = """"Palaver draft to intent tree mapper"""
    gibbon = vision.add_project_level(taxon_def_record=subsystem_def,
                                           name="Gibbon",
                                           description=textwrap.dedent(desc))
    assert gibbon
    gibbon_multi_draft = gibbon.add_project_level(taxon_def_record=deliverable_def,
                                           name="gibbon multiple drafts",
                                           description=textwrap.dedent(desc))
    assert gibbon_multi_draft
    epic_2 = gibbon_multi_draft.add_child(taxon_def_record=epic_def,
                                          name="add wait for rescan option")
    assert epic_2
    story_2 = epic_2.add_child(taxon_def_record=story_def,
                               name="make intent tree logic support fast and slow")
    assert story_2

    task_2 = story_2.add_child(taxon_def_record=task_def,
                               name="do something")
    

