#!/usr/bin/env python
import sys
import os
from pathlib import Path
import json
import pytest

from sqlmodel import Session, select
from dpm.store.wrappers import ModelDB
from dpm.store.domains import DomainCatalog
from dpm.store.sw_models import GuardrailType, Vision, Subsystem, Deliverable, Epic, Story, SWTask
from dpm.store.sw_wrappers import (
    VisionRecord, SubsystemRecord, DeliverableRecord,
    EpicRecord, StoryRecord, SWTaskRecord, SWModelDB
)


@pytest.fixture
def sw_db(tmp_path):
    db_path = tmp_path / "test_sw.sqlite"
    model_db = ModelDB(tmp_path, name_override="test_sw.sqlite", autocreate=True)

    config = {
        "databases": {
            "TestDomain": {
                "path": str(db_path),
                "description": "Test domain",
                "domain_mode": "software"
            }
        }
    }
    config_path = tmp_path / "config.json"
    with open(config_path, "w") as f:
        json.dump(config, f)
    catalog = DomainCatalog.from_json_config(config_path)
    domain = catalog.pmdb_domains['TestDomain']
    return domain.db, domain


def test_wrappers_simple(sw_db):
    """Original test ported to new fixture — ensures basic creation still works."""
    db, domain = sw_db
    sw = db.sw_model_db

    epic1 = sw.add_epic(domain, "epic1")
    vision1 = sw.add_vision(domain, "vision1")
    epic2 = sw.add_epic(domain, "epic2", vision=vision1)
    sub1 = sw.add_subsystem(domain, "sub1")
    epic3 = sw.add_epic(domain, "epic3", subsystem=sub1)
    sub2 = sw.add_subsystem(domain, "sub2", vision=vision1)
    epic4 = sw.add_epic(domain, "epic4", subsystem=sub2)

    deli1 = sw.add_deliverable(domain, "deliverable1")
    deli2 = sw.add_deliverable(domain, "deliverable2", vision=vision1)
    deli3 = sw.add_deliverable(domain, "deliverable3", subsystem=sub1)
    epic5 = sw.add_epic(domain, "epic5", deliverable=deli3)

    story1 = sw.add_story(domain, "story1", vision=vision1)
    story2 = sw.add_story(domain, "story2", subsystem=sub1)
    story3 = sw.add_story(domain, "story3", deliverable=deli3)
    story4 = sw.add_story(domain, "story4", epic=epic5)

    task1 = sw.add_task(domain, "task1", vision=vision1)
    task2 = sw.add_task(domain, "task2", subsystem=sub1)
    task3 = sw.add_task(domain, "task3", deliverable=deli3)
    task4 = sw.add_task(domain, "task4", epic=epic5)
    task5 = sw.add_task(domain, "task5", story=story4)


def test_sw_queries(sw_db):
    """Create a hierarchy and verify all lookup/list/type-detection methods."""
    db, domain = sw_db
    sw = db.sw_model_db

    # Build hierarchy: vision > subsystem > deliverable > epic > story > task
    vision = sw.add_vision(domain, "Vision1")
    sub = sw.add_subsystem(domain, "Sub1", vision=vision)
    deli = sw.add_deliverable(domain, "Del1", subsystem=sub)
    epic = sw.add_epic(domain, "Epic1", deliverable=deli)
    story = sw.add_story(domain, "Story1", epic=epic)
    task = sw.add_task(domain, "Task1", story=story)

    # Lookup by SW ID
    assert sw.get_vision_by_id(vision.vision_id) is not None
    assert sw.get_vision_by_id(vision.vision_id).vision_id == vision.vision_id
    assert sw.get_subsystem_by_id(sub.subsystem_id).subsystem_id == sub.subsystem_id
    assert sw.get_deliverable_by_id(deli.deliverable_id).deliverable_id == deli.deliverable_id
    assert sw.get_epic_by_id(epic.epic_id).epic_id == epic.epic_id
    assert sw.get_story_by_id(story.story_id).story_id == story.story_id
    assert sw.get_swtask_by_id(task.swtask_id).swtask_id == task.swtask_id

    # Lookup by SW ID — miss returns None
    assert sw.get_vision_by_id(9999) is None
    assert sw.get_subsystem_by_id(9999) is None
    assert sw.get_deliverable_by_id(9999) is None
    assert sw.get_epic_by_id(9999) is None
    assert sw.get_story_by_id(9999) is None
    assert sw.get_swtask_by_id(9999) is None

    # Lookup from base model ID
    assert sw.get_vision_for_project(vision.project_id).vision_id == vision.vision_id
    assert sw.get_subsystem_for_project(sub.project_id).subsystem_id == sub.subsystem_id
    assert sw.get_deliverable_for_project(deli.project_id).deliverable_id == deli.deliverable_id
    assert sw.get_epic_for_project(epic.project_id).epic_id == epic.epic_id
    assert sw.get_story_for_phase(story.phase_id).story_id == story.story_id
    assert sw.get_swtask_for_task(task.task_id).swtask_id == task.swtask_id

    # Lookup from base model ID — miss returns None
    assert sw.get_vision_for_project(9999) is None
    assert sw.get_subsystem_for_project(9999) is None
    assert sw.get_deliverable_for_project(9999) is None
    assert sw.get_epic_for_project(9999) is None
    assert sw.get_story_for_phase(9999) is None
    assert sw.get_swtask_for_task(9999) is None

    # List queries — unfiltered
    assert len(sw.get_visions()) == 1
    assert len(sw.get_subsystems()) == 1
    assert len(sw.get_deliverables()) == 1
    assert len(sw.get_epics()) == 1
    assert len(sw.get_stories()) == 1
    assert len(sw.get_swtasks()) == 1

    # List queries — filtered
    assert len(sw.get_subsystems(vision=vision)) == 1
    assert len(sw.get_deliverables(parent=sub)) == 1
    assert len(sw.get_epics(parent=deli)) == 1
    assert len(sw.get_stories(epic=epic)) == 1
    assert len(sw.get_swtasks(story=story)) == 1
    assert len(sw.get_swtasks(epic=epic)) == 1

    # Type detection
    assert sw.get_sw_type(vision.project_id) == "Vision"
    assert sw.get_sw_type(sub.project_id) == "Subsystem"
    assert sw.get_sw_type(deli.project_id) == "Deliverable"
    assert sw.get_sw_type(epic.project_id) == "Epic"
    assert sw.get_sw_type(9999) is None

    assert sw.get_sw_phase_type(story.phase_id) == "Story"
    assert sw.get_sw_phase_type(9999) is None

    assert sw.get_sw_task_type(task.task_id) == "SWTask"
    assert sw.get_sw_task_type(9999) is None


def test_sw_delete_cascade(sw_db):
    """Delete at various levels, verify no orphaned overlay rows."""
    db, domain = sw_db
    sw = db.sw_model_db

    # Build hierarchy
    vision = sw.add_vision(domain, "Vision1")
    epic = sw.add_epic(domain, "Epic1", vision=vision)
    story = sw.add_story(domain, "Story1", epic=epic)
    task = sw.add_task(domain, "Task1", story=story)

    # Delete task — SWTask overlay should be gone
    task_id = task.task_id
    swtask_id = task.swtask_id
    task.delete_from_db()
    assert sw.get_swtask_for_task(task_id) is None
    assert sw.get_swtask_by_id(swtask_id) is None

    # Delete story (phase) — Story overlay should be gone
    story_phase_id = story.phase_id
    story_id = story.story_id
    story.delete_from_db()
    assert sw.get_story_for_phase(story_phase_id) is None
    assert sw.get_story_by_id(story_id) is None

    # Delete epic (project) — Epic overlay should be gone
    epic_project_id = epic.project_id
    epic_id = epic.epic_id
    epic.delete_from_db()
    assert sw.get_epic_for_project(epic_project_id) is None
    assert sw.get_epic_by_id(epic_id) is None

    # Delete vision — Vision overlay should be gone
    vision_project_id = vision.project_id
    vision_id = vision.vision_id
    vision.delete_from_db()
    assert sw.get_vision_for_project(vision_project_id) is None
    assert sw.get_vision_by_id(vision_id) is None


def test_sw_delete_cascade_subsystem_deliverable(sw_db):
    """Delete subsystem and deliverable, verify overlay cleanup."""
    db, domain = sw_db
    sw = db.sw_model_db

    sub = sw.add_subsystem(domain, "Sub1")
    deli = sw.add_deliverable(domain, "Del1", subsystem=sub)

    deli_pid = deli.project_id
    deli.delete_from_db()
    assert sw.get_deliverable_for_project(deli_pid) is None

    sub_pid = sub.project_id
    sub.delete_from_db()
    assert sw.get_subsystem_for_project(sub_pid) is None


def test_sw_guardrail_inheritance(sw_db):
    """epic(MVP) > story(inherits) > task(inherits); explicit override wins."""
    db, domain = sw_db
    sw = db.sw_model_db

    epic = sw.add_epic(domain, "Epic1", guardrail_type=GuardrailType.MVP)
    assert epic.guardrail_type == GuardrailType.MVP

    # Story inherits from epic
    story = sw.add_story(domain, "Story1", epic=epic)
    assert story.guardrail_type == GuardrailType.MVP

    # Task inherits from story
    task = sw.add_task(domain, "Task1", story=story)
    assert task.guardrail_type == GuardrailType.MVP

    # Task inherits from epic (no story)
    task2 = sw.add_task(domain, "Task2", epic=epic)
    assert task2.guardrail_type == GuardrailType.MVP

    # Explicit override wins
    story2 = sw.add_story(domain, "Story2", epic=epic, guardrail_type=GuardrailType.PROTOTYPE)
    assert story2.guardrail_type == GuardrailType.PROTOTYPE

    task3 = sw.add_task(domain, "Task3", story=story2, guardrail_type=GuardrailType.POC)
    assert task3.guardrail_type == GuardrailType.POC

    # Default when no epic
    vision = sw.add_vision(domain, "Vision1")
    story3 = sw.add_story(domain, "Story3", vision=vision)
    assert story3.guardrail_type == GuardrailType.PRODUCTION

    task4 = sw.add_task(domain, "Task4", vision=vision)
    assert task4.guardrail_type == GuardrailType.PRODUCTION


def test_sw_guardrail_save(sw_db):
    """Change guardrail_type, save, re-query, verify persisted."""
    db, domain = sw_db
    sw = db.sw_model_db

    epic = sw.add_epic(domain, "Epic1", guardrail_type=GuardrailType.MVP)

    # Change and save epic guardrail
    epic.guardrail_type = GuardrailType.PROTOTYPE
    epic.save()
    epic_reloaded = sw.get_epic_by_id(epic.epic_id)
    assert epic_reloaded.guardrail_type == GuardrailType.PROTOTYPE

    # Story guardrail save
    story = sw.add_story(domain, "Story1", epic=epic)
    story.guardrail_type = GuardrailType.POC
    story.save()
    story_reloaded = sw.get_story_by_id(story.story_id)
    assert story_reloaded.guardrail_type == GuardrailType.POC

    # SWTask guardrail save
    task = sw.add_task(domain, "Task1", story=story)
    task.guardrail_type = GuardrailType.RESEARCH
    task.save()
    task_reloaded = sw.get_swtask_by_id(task.swtask_id)
    assert task_reloaded.guardrail_type == GuardrailType.RESEARCH


def test_sw_wrap_project(sw_db):
    """wrap_project returns correct types."""
    db, domain = sw_db
    sw = db.sw_model_db

    vision = sw.add_vision(domain, "Vision1")
    sub = sw.add_subsystem(domain, "Sub1")
    deli = sw.add_deliverable(domain, "Del1")
    epic = sw.add_epic(domain, "Epic1")

    # Also add a plain project (no overlay)
    plain = db.add_project("PlainProject")

    # wrap_project should return the typed record
    wrapped_vision = sw.wrap_project(db.get_project_by_id(vision.project_id))
    assert isinstance(wrapped_vision, VisionRecord)

    wrapped_sub = sw.wrap_project(db.get_project_by_id(sub.project_id))
    assert isinstance(wrapped_sub, SubsystemRecord)

    wrapped_deli = sw.wrap_project(db.get_project_by_id(deli.project_id))
    assert isinstance(wrapped_deli, DeliverableRecord)

    wrapped_epic = sw.wrap_project(db.get_project_by_id(epic.project_id))
    assert isinstance(wrapped_epic, EpicRecord)

    # Plain project stays as ProjectRecord
    wrapped_plain = sw.wrap_project(plain)
    assert type(wrapped_plain).__name__ == "ProjectRecord"
