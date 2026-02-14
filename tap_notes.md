# TAP Interaction Model Notes

## Overview

TAP ("Talk And Point") is a planned interaction model for voice-controlled project management. The DPM UI and API are designed to be embedded in the vboss project, an LLM-assisted voice-controlled assistant system.

## Concept

Voice-to-text transcriptions interact with DPM components in the vboss server to select domains, projects, phases, tasks, and other items on voice command. The user then views and manipulates the selected objects visually — a "talk and point" workflow.

The interaction flow:
1. User speaks a command (e.g., "show the authentication task")
2. LLM interprets the transcription and calls DPM APIs to select the matching entity
3. The UI updates to focus on the selected entity
4. User can then manipulate it through the visual interface

## Current Implementation

The `/last/*` routes in `ui_router.py` are a rudimentary experiment in creating this focus mechanism:

- **`/last/project/`** (`pm:last_project`) — Displays the most recently selected project
- **`/last/phase/`** (`pm:last_phase`) — Displays the most recently selected phase
- **`/last/task/`** (`pm:last_task`) — Displays the most recently selected task

These routes use `DPMManager`'s last-accessed tracking (`get_last_project`, `get_last_phase`, `get_last_task`) to resolve what the user is currently focused on. If nothing has been selected, they redirect to the domains list.

The `DPMManager` state is also used by the kanban board's auto-redirect (`/board` → `/{domain}/board`) to remember the user's last context.

## Design Considerations

- The `/last/*` routes are not currently linked from any DPM template — they are intended to be driven by the vboss voice layer, not manual navigation.
- The `ServerOps` protocol and embeddable router architecture exist specifically to support this use case: the DPM routers plug into the vboss server alongside other components.
- The `tap_focus` attribute on `DPMServer` (currently unused) was a placeholder for richer focus state beyond simple last-accessed tracking.
