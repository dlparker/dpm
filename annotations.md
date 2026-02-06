# Type Annotation Upgrade Checklist

This document lists all functions and methods in the `src` tree that need type annotations added or upgraded according to modern Python standards (using primitive types `list`, `dict`, `set` instead of `typing.List`, `typing.Dict`, `typing.Set`).

## Convention
- Checklist item format: `[ ] filename.py:line_number - FunctionName - Description`
- Each item represents one function/method that can be annotated

---

## src/dpm/store/task_db.py

### FilterWrapper class
- [ ] task_db.py:14 - `filter_key` - Add `-> None` return type
- [ ] task_db.py:17 - `items` - Add return type for iterator yielding tuples

### TrackingWrapper class
- [ ] task_db.py:31 - `__init__` - Add type annotation for `wrapped` parameter
- [ ] task_db.py:38 - `__getattr__` - Add type annotation for `attr` and return type
- [ ] task_db.py:43 - `__setattr__` - Add type annotation for `attr` and `val` parameters
- [ ] task_db.py:49 - `is_changed` - Add `-> bool` return type
- [ ] task_db.py:55 - `get_changes` - Add return type for dict mapping
- [ ] task_db.py:66 - `revert` - Add `-> None` return type

### TaskRecord class
- [ ] task_db.py:79 - `__init__` - Ensure `task_db` parameter is annotated
- [ ] task_db.py:90 - `__repr__` - Add `-> str` return type
- [ ] task_db.py:93 - `__eq__` - Add type annotation for `other: Any` and `-> bool`
- [ ] task_db.py:99 - `add_blocker` - Add type annotation for `other_task` parameter
- [ ] task_db.py:107 - `delete_blocker` - Add type annotation for `other_task` parameter
- [ ] task_db.py:110 - `get_blockers` - Add return type `list['TaskRecord']`
- [ ] task_db.py:121 - `blocks_tasks` - Add return type `list['TaskRecord']`
- [ ] task_db.py:131 - `save` - Add `-> bool` return type
- [ ] task_db.py:138 - `get_tracking_wrapper` - Add return type `TrackingWrapper`
- [ ] task_db.py:141 - `delete_from_db` - Add `-> None` return type
- [ ] task_db.py:146 - `add_to_project` - Add type annotation for `project` parameter
- [ ] task_db.py:150 - `add_to_phase` - Add type annotations for `phase` and `move_to_project` parameters
- [ ] task_db.py:161 - `project` (property getter) - Add `-> Optional['ProjectRecord']` return type
- [ ] task_db.py:167 - `project` (property setter) - Add type annotation for `value` parameter
- [ ] task_db.py:174 - `phase` (property getter) - Add `-> Optional['PhaseRecord']` return type
- [ ] task_db.py:180 - `phase` (property setter) - Add type annotation for `value` parameter
- [ ] task_db.py:184 - `to_json_dict` - Add `-> FilterWrapper` return type

### ProjectRecord class
- [ ] task_db.py:189 - `__init__` - Ensure `task_db`, `parent`, `parent_id` have annotations
- [ ] task_db.py:203 - `__repr__` - Add `-> str` return type
- [ ] task_db.py:207 - `__eq__` - Add type annotation for `other: Any` and `-> bool`
- [ ] task_db.py:213 - `save` - Add return type annotation
- [ ] task_db.py:218 - `get_kids` - Add return type `list['ProjectRecord']`
- [ ] task_db.py:221 - `get_tasks` - Add return type `list['TaskRecord']`
- [ ] task_db.py:224 - `parent` (property getter) - Add `-> Optional['ProjectRecord']` return type
- [ ] task_db.py:230 - `parent` (property setter) - Add type annotation for `value` parameter
- [ ] task_db.py:234 - `get_tracking_wrapper` - Add return type `TrackingWrapper`
- [ ] task_db.py:237 - `new_phase` - Add return type and parameter annotations
- [ ] task_db.py:249 - `add_phase` - Add return type and parameter annotations
- [ ] task_db.py:261 - `get_phases` - Add return type `list['PhaseRecord']`
- [ ] task_db.py:264 - `delete_from_db` - Add `-> None` return type
- [ ] task_db.py:289 - `to_json_dict` - Add `-> FilterWrapper` return type

### PhaseRecord class
- [ ] task_db.py:294 - `__init__` - Ensure `task_db` and other parameters have annotations
- [ ] task_db.py:304 - `__eq__` - Add type annotation for `other: Any` and `-> bool`
- [ ] task_db.py:310 - `__repr__` - Add `-> str` return type
- [ ] task_db.py:314 - `follows` (property getter) - Add `-> Optional['PhaseRecord']` return type
- [ ] task_db.py:320 - `follows` (property setter) - Add type annotation for `value` parameter
- [ ] task_db.py:324 - `follower` (property getter) - Add `-> Optional['PhaseRecord']` return type
- [ ] task_db.py:328 - `project` (property getter) - Add `-> 'ProjectRecord'` return type
- [ ] task_db.py:332 - `project` (property setter) - Add type annotation for `value` parameter
- [ ] task_db.py:336 - `save` - Add return type annotation
- [ ] task_db.py:341 - `get_tasks` - Add return type `list['TaskRecord']`
- [ ] task_db.py:344 - `get_tracking_wrapper` - Add return type `TrackingWrapper`
- [ ] task_db.py:347 - `change_project` - Add type annotation for `new_project_id` parameter
- [ ] task_db.py:352 - `delete_from_db` - Add `-> None` return type
- [ ] task_db.py:369 - `to_json_dict` - Add `-> FilterWrapper` return type

### TaskDB class
- [ ] task_db.py:384 - `__init__` - Ensure parameter types are complete
- [ ] task_db.py:397 - `open` - Already has `-> None` return type
- [ ] task_db.py:410 - `init_db` - Add `-> None` return type
- [ ] task_db.py:451 - `make_backup` - Add return type `Path`
- [ ] task_db.py:509 - `add_task` - Add return type `'TaskRecord'`
- [ ] task_db.py:531 - `get_task_by_name` - Add return type `Optional['TaskRecord']`
- [ ] task_db.py:545 - `get_task_by_id` - Add return type `Optional['TaskRecord']`
- [ ] task_db.py:559 - `get_tasks` - Add return type `list['TaskRecord']`
- [ ] task_db.py:574 - `get_tasks_by_status` - Add return type `list['TaskRecord']`
- [ ] task_db.py:591 - `get_tasks_by_project_id` - Add return type `list['TaskRecord']`
- [ ] task_db.py:606 - `move_phase_and_tasks_to_project` - Add return type `'PhaseRecord'`
- [ ] task_db.py:628 - `replace_task_project_refs` - Add `-> None` return type
- [ ] task_db.py:640 - `get_tasks_by_phase_id` - Add return type `list['TaskRecord']`
- [ ] task_db.py:655 - `replace_task_phase_refs` - Add `-> None` return type
- [ ] task_db.py:676 - `save_task_record` - Add return type `'TaskRecord'`
- [ ] task_db.py:716 - `add_task_blocker` - Add return type `int`
- [ ] task_db.py:730 - `delete_task_blocker` - Add `-> None` return type
- [ ] task_db.py:737 - `get_task_blockers` - Add return type `list['TaskRecord']`
- [ ] task_db.py:752 - `get_tasks_blocked` - Add return type `list['TaskRecord']`
- [ ] task_db.py:762 - `delete_task_record` - Add `-> None` return type
- [ ] task_db.py:771 - `add_project` - Add return type `'ProjectRecord'`
- [ ] task_db.py:799 - `get_project_by_id` - Add return type `Optional['ProjectRecord']`
- [ ] task_db.py:813 - `get_project_by_name` - Add return type `Optional['ProjectRecord']`
- [ ] task_db.py:827 - `get_projects` - Add return type `list['ProjectRecord']`
- [ ] task_db.py:841 - `get_projects_by_parent_id` - Add return type `list['ProjectRecord']`
- [ ] task_db.py:860 - `save_project_record` - Add return type `'ProjectRecord']`
- [ ] task_db.py:893 - `get_tasks_for_project` - Add return type `list['TaskRecord']`
- [ ] task_db.py:898 - `delete_project_record` - Add `-> None` return type
- [ ] task_db.py:905 - `add_phase` - Add return type `'PhaseRecord'`
- [ ] task_db.py:909 - `save_phase` - Add return type `'PhaseRecord'`
- [ ] task_db.py:998 - `row_to_phase` - Add return type `'PhaseRecord'`
- [ ] task_db.py:1010 - `get_phase_by_id` - Add return type `Optional['PhaseRecord']`
- [ ] task_db.py:1022 - `get_phase_by_name` - Add return type `Optional['PhaseRecord']`
- [ ] task_db.py:1034 - `get_phases_by_project_id` - Add return type `list['PhaseRecord']`
- [ ] task_db.py:1048 - `get_phase_that_follows` - Add return type `Optional['PhaseRecord']`
- [ ] task_db.py:1068 - `save_phase_record` - Add return type `'PhaseRecord'`
- [ ] task_db.py:1074 - `get_tasks_for_phase` - Add return type `list['TaskRecord']`
- [ ] task_db.py:1079 - `delete_phase_record` - Add `-> None` return type
- [ ] task_db.py:1086 - `close` - Add `-> None` return type

---

## src/dpm/store/models.py

### FilterWrapper class
- [ ] models.py:12 - `filter_key` - Add `-> None` return type
- [ ] models.py:20 - `items` - Add return type for iterator yielding tuples

### TrackingWrapper class
- [ ] models.py:42 - `__init__` - Add type annotation for `wrapped` parameter
- [ ] models.py:49 - `__getattr__` - Add type annotation for `attr` and return type
- [ ] models.py:56 - `__setattr__` - Add type annotation for `attr` and `val` parameters
- [ ] models.py:64 - `is_changed` - Add `-> bool` return type
- [ ] models.py:70 - `get_changes` - Add return type `dict`
- [ ] models.py:84 - `revert` - Add `-> None` return type
- [ ] models.py:96 - `save` - Add return type annotation

### ProjectRecord class
- [ ] models.py:156 - `__init__` - Already well annotated
- [ ] models.py:160 - All properties already annotated with return types
- [ ] models.py:207 - `__repr__` - Add `-> str` return type
- [ ] models.py:210 - `__eq__` - Add type annotation for `other: Any` and `-> bool`
- [ ] models.py:216 - `save` - Add return type annotation
- [ ] models.py:219 - `get_kids` - Add return type `list['ProjectRecord']`
- [ ] models.py:222 - `get_tasks` - Add return type `list['TaskRecord']`
- [ ] models.py:225 - `get_tracking_wrapper` - Add return type `TrackingWrapper`
- [ ] models.py:228 - `new_phase` - Add return type `'PhaseRecord'` and parameter annotations
- [ ] models.py:239 - `add_phase` - Add return type and parameter annotations
- [ ] models.py:255 - `get_phases` - Add return type `list['PhaseRecord']`
- [ ] models.py:258 - `delete_from_db` - Add `-> None` return type
- [ ] models.py:281 - `to_json_dict` - Add `-> FilterWrapper` return type

### PhaseRecord class
- [ ] models.py:296 - `__init__` - Already well annotated
- [ ] models.py:301 - Most properties already annotated with return types
- [ ] models.py:357 - `follower` (property) - Add `-> Optional['PhaseRecord']` return type
- [ ] models.py:368 - `__eq__` - Already annotated
- [ ] models.py:374 - `__repr__` - Already annotated
- [ ] models.py:377 - `save` - Add return type annotation
- [ ] models.py:380 - `get_tasks` - Add return type `list['TaskRecord']`
- [ ] models.py:383 - `get_tracking_wrapper` - Add return type `TrackingWrapper`
- [ ] models.py:386 - `change_project` - Add type annotation for `new_project_id` parameter
- [ ] models.py:391 - `delete_from_db` - Add `-> None` return type
- [ ] models.py:407 - `to_json_dict` - Add `-> FilterWrapper` return type

### TaskRecord class
- [ ] models.py:423 - `__init__` - Already well annotated
- [ ] models.py:427 - Most properties already annotated with return types
- [ ] models.py:451 - `phase` (property setter) - Add type annotation for `value` parameter
- [ ] models.py:503 - `__repr__` - Already annotated
- [ ] models.py:506 - `__eq__` - Already annotated
- [ ] models.py:512 - `add_blocker` - Add type annotation for `other_task` parameter
- [ ] models.py:520 - `delete_blocker` - Add type annotation for `other_task` parameter
- [ ] models.py:523 - `get_blockers` - Add return type `list['TaskRecord']`
- [ ] models.py:534 - `blocks_tasks` - Add return type `list['TaskRecord']`
- [ ] models.py:544 - `save` - Already has `-> bool`
- [ ] models.py:551 - `get_tracking_wrapper` - Add return type `TrackingWrapper`
- [ ] models.py:554 - `delete_from_db` - Add `-> None` return type
- [ ] models.py:559 - `add_to_project` - Add type annotation for `project` parameter
- [ ] models.py:563 - `add_to_phase` - Add type annotations for `phase` and `move_to_project` parameters
- [ ] models.py:574 - `to_json_dict` - Add `-> FilterWrapper` return type

### ModelDB class
- [ ] models.py:594 - `__init__` - Already well annotated
- [ ] models.py:612 - `open` - Already has `-> None`
- [ ] models.py:617 - `close` - Add `-> None` return type
- [ ] models.py:623 - `add_task` - Add return type `'TaskRecord'`
- [ ] models.py:647 - `get_task_by_name` - Add return type `Optional['TaskRecord']`
- [ ] models.py:654 - `get_task_by_id` - Add return type `Optional['TaskRecord']`
- [ ] models.py:661 - `get_tasks` - Add return type `list['TaskRecord']`
- [ ] models.py:666 - `get_tasks_by_status` - Add return type `list['TaskRecord']`
- [ ] models.py:673 - `get_tasks_by_project_id` - Add return type `list['TaskRecord']`
- [ ] models.py:678 - `get_tasks_by_phase_id` - Add return type `list['TaskRecord']`
- [ ] models.py:683 - `get_tasks_for_project` - Add return type `list['TaskRecord']`
- [ ] models.py:688 - `get_tasks_for_phase` - Add return type `list['TaskRecord']`
- [ ] models.py:693 - `save_task_record` - Add return type `'TaskRecord'`
- [ ] models.py:741 - `delete_task_record` - Add `-> None` return type
- [ ] models.py:754 - `replace_task_project_refs` - Add `-> None` return type
- [ ] models.py:767 - `replace_task_phase_refs` - Add `-> None` return type
- [ ] models.py:790 - `add_task_blocker` - Add return type `int`
- [ ] models.py:803 - `delete_task_blocker` - Add `-> None` return type
- [ ] models.py:812 - `get_task_blockers` - Add return type `list['TaskRecord']`
- [ ] models.py:826 - `get_tasks_blocked` - Add return type `list['TaskRecord']`
- [ ] models.py:837 - `add_project` - Add return type `'ProjectRecord'`
- [ ] models.py:862 - `get_project_by_id` - Add return type `Optional['ProjectRecord']`
- [ ] models.py:869 - `get_project_by_name` - Add return type `Optional['ProjectRecord']`
- [ ] models.py:876 - `get_projects` - Add return type `list['ProjectRecord']`
- [ ] models.py:881 - `get_projects_by_parent_id` - Add return type `list['ProjectRecord']`
- [ ] models.py:889 - `save_project_record` - Add return type `'ProjectRecord']`
- [ ] models.py:926 - `delete_project_record` - Add `-> None` return type
- [ ] models.py:939 - `add_phase` - Add return type `'PhaseRecord'`
- [ ] models.py:943 - `_save_phase` - Add return type `'PhaseRecord'`
- [ ] models.py:1018 - `get_phase_by_id` - Add return type `Optional['PhaseRecord']`
- [ ] models.py:1026 - `get_phase_by_name` - Add return type `Optional['PhaseRecord']`
- [ ] models.py:1034 - `_get_follows_id` - Add return type `Optional[int]`
- [ ] models.py:1043 - `get_phases_by_project_id` - Add return type `list['PhaseRecord']`
- [ ] models.py:1054 - `get_phase_that_follows` - Add return type `Optional['PhaseRecord']`
- [ ] models.py:1070 - `save_phase_record` - Add return type `'PhaseRecord']`
- [ ] models.py:1083 - `delete_phase_record` - Add `-> None` return type
- [ ] models.py:1090 - `move_phase_and_tasks_to_project` - Add return type `'PhaseRecord']`
- [ ] models.py:1118 - `make_backup` - Add return type `Path`

### DomainCatalog class
- [ ] models.py:1195 - Dataclass already well annotated
- [ ] models.py:1198 - `from_json_config` - Add return type `'DomainCatalog'` and parameter type for `config_path`

### DPMManager class
- [ ] models.py:1226 - `__init__` - Already well annotated
- [ ] models.py:1236 - `_state_path` (property) - Already annotated
- [ ] models.py:1239 - `_load_state` - Add `-> None` return type
- [ ] models.py:1270 - `_save_state` - Add `-> None` return type
- [ ] models.py:1284 - `get_db_for_domain` - Add return type `ModelDB`
- [ ] models.py:1287 - `get_default_domain` - Add return type `str`
- [ ] models.py:1292 - `shutdown` - Already async
- [ ] models.py:1296 - `get_domains` - Add return type `dict[str, PMDBDomain]`
- [ ] models.py:1299 - `set_last_domain` - Add type annotation for `domain` parameter
- [ ] models.py:1305 - `get_last_domain` - Add return type `Optional[str]`
- [ ] models.py:1308 - `set_last_project` - Already well annotated
- [ ] models.py:1319 - `get_last_project` - Add return type `Optional['ProjectRecord']`
- [ ] models.py:1322 - `set_last_phase` - Already well annotated
- [ ] models.py:1334 - `get_last_phase` - Add return type `Optional['PhaseRecord']`
- [ ] models.py:1337 - `set_last_task` - Already well annotated
- [ ] models.py:1351 - `get_last_task` - Add return type `Optional['TaskRecord']`

---

## src/dpm/fastapi/shared/api_router.py

### TAPAPIService class
- [ ] shared/api_router.py:15 - `__init__` - Add type annotations for `server` and `prefix_tag` parameters
- [ ] shared/api_router.py:21 - `become_router` - Already has `-> APIRouter` return type
- [ ] shared/api_router.py:27 - `get_tap_focus` - Add return type `TAPFocusResponse`
- [ ] shared/api_router.py:40 - `set_tap_task` - Add return type `TAPFocusResponse`

---

## src/dpm/fastapi/shared/ui_router.py

### UIRouter class
- [ ] shared/ui_router.py:14 - `__init__` - Add type annotations for `server` and `dpm_manager` parameters
- [ ] shared/ui_router.py:20 - `_get_status_data` - Add return type `dict[str, str]`
- [ ] shared/ui_router.py:25 - `become_router` - Add return type `APIRouter`
- [ ] shared/ui_router.py:29 - `home` - All route handlers already have Request annotation, add complete return type
- [ ] shared/ui_router.py:46 - `status_partial` - Add complete return type

### Helper functions
- [ ] shared/ui_router.py:18 - `format_timestamp` - Add type annotations for `ts` parameter and `-> Optional[str]` return type
- [ ] shared/ui_router.py:25 - `time_ago` - Add type annotations for `ts` parameter and `-> Optional[str]` return type

---

## src/dpm/fastapi/dpm/api_router.py

### PMDBAPIService class
- [ ] dpm/api_router.py:116 - `__init__` - Add type annotations for `server`, `dpm_manager`, and `prefix_tag` parameters
- [ ] dpm/api_router.py:122 - `become_router` - Already has `-> APIRouter` return type
- [ ] dpm/api_router.py:149 - `_get_db` - Already well annotated

### Domain endpoints
- [ ] dpm/api_router.py:159 - `list_domains` - Add return type `list[DomainResponse]`
- [ ] dpm/api_router.py:164 - `list_projects` - Add return type `list[ProjectResponse]`
- [ ] dpm/api_router.py:178 - `get_project` - Add return type `ProjectResponse`
- [ ] dpm/api_router.py:192 - `create_project` - Add return type `ProjectResponse`
- [ ] dpm/api_router.py:211 - `update_project` - Add return type `ProjectResponse`
- [ ] dpm/api_router.py:237 - `delete_project` - Add return type `None`

### Project-related endpoints
- [ ] dpm/api_router.py:245 - `list_project_phases` - Add return type `list[PhaseResponse]`
- [ ] dpm/api_router.py:261 - `list_project_tasks` - Add return type `list[TaskResponse]`

### Phase endpoints
- [ ] dpm/api_router.py:282 - `list_phases` - Add return type `list[PhaseResponse]`
- [ ] dpm/api_router.py:301 - `get_phase` - Add return type `PhaseResponse`
- [ ] dpm/api_router.py:316 - `create_phase` - Add return type `PhaseResponse`
- [ ] dpm/api_router.py:337 - `update_phase` - Add return type `PhaseResponse`
- [ ] dpm/api_router.py:366 - `delete_phase` - Add return type `None`
- [ ] dpm/api_router.py:374 - `list_phase_tasks` - Add return type `list[TaskResponse]`

### Task endpoints
- [ ] dpm/api_router.py:395 - `list_tasks` - Add return type `list[TaskResponse]`
- [ ] dpm/api_router.py:422 - `get_task` - Add return type `TaskResponse`
- [ ] dpm/api_router.py:438 - `create_task` - Add return type `TaskResponse`
- [ ] dpm/api_router.py:461 - `update_task` - Add return type `TaskResponse`
- [ ] dpm/api_router.py:493 - `delete_task` - Add return type `None`

### Blocker endpoints
- [ ] dpm/api_router.py:505 - `list_task_blockers` - Add return type `list[BlockerResponse]`
- [ ] dpm/api_router.py:518 - `add_blocker` - Add return type `dict[str, str]`
- [ ] dpm/api_router.py:541 - `remove_blocker` - Add return type `None`
- [ ] dpm/api_router.py:554 - `list_tasks_blocked_by` - Add return type `list[BlockerResponse]`

---

## src/dpm/fastapi/dpm/ui_router.py

### PMDBUIRouter class
- [ ] dpm/ui_router.py:43 - `__init__` - Add type annotations for `server` and `dpm_manager` parameters
- [ ] dpm/ui_router.py:50 - `_get_db` - Add return type `ModelDB`
- [ ] dpm/ui_router.py:53 - `become_router` - Add return type `APIRouter`

### Domain/navigation routes
- [ ] dpm/ui_router.py:61 - `pm_domains` (GET) - Add return type `HTMLResponse`
- [ ] dpm/ui_router.py:82 - `pm_nav_tree` (GET) - Add return type `HTMLResponse`
- [ ] dpm/ui_router.py:106 - `pm_nav_projects` (GET) - Add return type `HTMLResponse`
- [ ] dpm/ui_router.py:125 - `pm_nav_project_children` (GET) - Add return type `HTMLResponse`
- [ ] dpm/ui_router.py:153 - `pm_nav_phase_tasks` (GET) - Add return type `HTMLResponse`

### Project routes
- [ ] dpm/ui_router.py:181 - `pm_projects` (GET) - Add return type `HTMLResponse`
- [ ] dpm/ui_router.py:208 - `pm_project_children` (GET) - Add return type `HTMLResponse`

### Project CRUD routes
- [ ] dpm/ui_router.py:281 - `pm_project_create` (GET) - Add return type `HTMLResponse`
- [ ] dpm/ui_router.py:309 - `pm_project_create_submit` (POST) - Add return type `HTMLResponse`
- [ ] dpm/ui_router.py:348 - `pm_project_edit` (GET) - Add return type `HTMLResponse`
- [ ] dpm/ui_router.py:380 - `pm_project_edit_submit` (POST) - Add return type `HTMLResponse`
- [ ] dpm/ui_router.py:432 - `pm_project_edit_modal` (GET) - Add return type `HTMLResponse`
- [ ] dpm/ui_router.py:452 - `pm_project_edit_modal_submit` (POST) - Add return type `HTMLResponse`
- [ ] dpm/ui_router.py:489 - `pm_project_delete` (GET) - Add return type `HTMLResponse`
- [ ] dpm/ui_router.py:525 - `pm_project_delete_submit` (POST) - Add return type `HTMLResponse`

### Phase CRUD routes
- [ ] dpm/ui_router.py:560 - `pm_phase_create` (GET) - Add return type `HTMLResponse`
- [ ] dpm/ui_router.py:589 - `pm_phase_create_submit` (POST) - Add return type `HTMLResponse`
- [ ] dpm/ui_router.py:629 - `pm_phase_edit` (GET) - Add return type `HTMLResponse`
- [ ] dpm/ui_router.py:661 - `pm_phase_edit_submit` (POST) - Add return type `HTMLResponse`
- [ ] dpm/ui_router.py:704 - `pm_phase_delete` (GET) - Add return type `HTMLResponse`
- [ ] dpm/ui_router.py:738 - `pm_phase_delete_submit` (POST) - Add return type `HTMLResponse`
- [ ] dpm/ui_router.py:770 - `pm_phase_edit_modal` (GET) - Add return type `HTMLResponse`
- [ ] dpm/ui_router.py:790 - `pm_phase_edit_modal_submit` (POST) - Add return type `HTMLResponse`

### Task CRUD routes
- [ ] dpm/ui_router.py:834 - `pm_task_create_in_project` (GET) - Add return type `HTMLResponse`
- [ ] dpm/ui_router.py:867 - `pm_task_create_in_project_submit` (POST) - Add return type `HTMLResponse`
- [ ] dpm/ui_router.py:921 - `pm_task_create_in_phase` (GET) - Add return type `HTMLResponse`
- [ ] dpm/ui_router.py:954 - `pm_task_create_in_phase_submit` (POST) - Add return type `HTMLResponse`
- [ ] dpm/ui_router.py:1008 - `pm_project_phases_options` (GET) - Add return type `HTMLResponse`
- [ ] dpm/ui_router.py:1026 - `pm_task_edit` (GET) - Add return type `HTMLResponse`
- [ ] dpm/ui_router.py:1068 - `pm_task_edit_submit` (POST) - Add return type `HTMLResponse`
- [ ] dpm/ui_router.py:1142 - `pm_task_delete` (GET) - Add return type `HTMLResponse`
- [ ] dpm/ui_router.py:1176 - `pm_task_delete_submit` (POST) - Add return type `HTMLResponse`

---

## src/dpm/fastapi/server.py

### DPMServer class
- [ ] fastapi/server.py:28 - `__init__` - Add type annotation for `config_path` parameter (`str | os.PathLike`)
- [ ] fastapi/server.py:57 - `shutdown` - Already async
- [ ] fastapi/server.py:61 - `lifespan` - Already annotated

---

## scripts/server.py

### Main function
- [ ] scripts/server.py:10 - `main` - Already has `async def` (no return type needed for async main)

---

## Summary Statistics

**Total items needing annotation upgrade:** Approximately 180+ functions/methods

**Files covered:**
- `src/dpm/store/task_db.py` - 65+ items
- `src/dpm/store/models.py` - 70+ items
- `src/dpm/fastapi/shared/api_router.py` - 4 items
- `src/dpm/fastapi/shared/ui_router.py` - 7 items
- `src/dpm/fastapi/dpm/api_router.py` - 20+ items
- `src/dpm/fastapi/dpm/ui_router.py` - 30+ items
- `src/dpm/fastapi/server.py` - 1 item

**Note:** This checklist focuses on discoverable and non-controversial type annotations. Some items may require additional imports (e.g., `from typing import Any`) for type annotations like `other: Any` in `__eq__` methods.

---

## Implementation Notes

1. **Forward References:** Use string quotes for forward references (e.g., `'TaskRecord'`, `'ProjectRecord'`) to avoid circular import issues.

2. **Optional Types:** Use `Optional[T]` for parameters/returns that can be `None`.

3. **List and Dict Types:** Use primitive types `list[T]` and `dict[K, V]` instead of `typing.List[T]` and `typing.Dict[K, V]`.

4. **Property Getters/Setters:** Ensure both getter and setter properties have consistent type annotations.

5. **Async Functions:** Async route handlers should have appropriate return types (e.g., `HTMLResponse`, `JSONResponse`).

6. **Self Type:** Self-referential return types should be quoted strings when the class isn't fully defined yet.

---

## Verification Checklist

After completing annotations:
- [ ] Run `mypy` or similar type checker to verify annotations
- [ ] Ensure no circular import issues
- [ ] Verify all imports needed for type hints are included
- [ ] Test that the application still runs without errors
- [ ] Check that API routes still return expected types
