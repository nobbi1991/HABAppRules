# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

HABApp Rules is a Python library of automation rules for [HABApp](https://habapp.readthedocs.io/), a home automation framework built on top of OpenHAB. Rules model real-world smart home scenarios (lights, presence, sleep, energy, shading, HVAC, etc.) as state machines using the `transitions` library.

## Commands

**Dependencies (managed with UV):**

```
uv sync --frozen --all-groups
```

**Run all tests with coverage:**

```
uv run scripts/run_tests_with_coverage.py
```

**Run a single test:**

```
uv run python -m unittest tests.actors.light.TestLightBase.test_manual_on
```

**Linting and formatting:**

```
uv run ruff format habapp_rules/
uv run ruff check --fix habapp_rules/
uv run mypy habapp_rules
```

**Pre-push hooks (runs format, lint, type check, and tests):**

```
uv run prek run --all-files
```

**Build:**

```
uv build
```

## Architecture

### Module Layout

Each domain (actors, sensors, energy, etc.) is split into two layers:

- `habapp_rules/<domain>/<rule>.py` — rule logic (state machine behavior, HABApp event callbacks)
- `habapp_rules/<domain>/config/<rule>.py` — Pydantic configuration classes

Tests mirror this layout under `tests/<domain>/`.

### Core Abstractions (`habapp_rules/core/`)

- **`pydantic_base.py`** — Foundation for all configs:
  - `ItemBase`: Declares OpenHAB item references; all fields must be `OpenhabItem` or `Thing` types.
  - `ParameterBase`: Rule tuning parameters.
  - `ConfigBase[ITEM, PARAM]`: Generic combining items + parameters.
- **`state_machine_rule.py`** — Base HABApp `Rule` subclasses with `transitions`-powered state machines:
  - `StateMachineRule`: flat state machine.
  - `StateMachineWithTimeout` / `HierarchicalStateMachineWithTimeout`: adds timeout states and hierarchical nesting.
- **`exceptions.py`** — `HabAppRulesError`, `HabAppRulesConfigurationError` (raised on bad config).
- **`helper.py`** — Item creation helpers, state queries.

### Typical Rule Pattern

1. Define `Items(ItemBase)` and `Parameter(ParameterBase)` in `config/<rule>.py`.
1. Combine into `Config(ConfigBase[Items, Parameter])`.
1. In `<rule>.py`, subclass `StateMachineRule` (or a timeout variant), declare states/transitions, and wire HABApp event listeners via `listen_event(...)` callbacks following the naming convention `_cb_<event_name>`.

### State Machine Conventions

- States are typically hierarchical: a top-level `manual` state and an `auto` state with substates (e.g., `auto_on`, `auto_off`, `auto_leaving`).
- Transitions trigger on OpenHAB item events filtered with `ItemStateChangedEventFilter`, `ItemStateUpdatedEventFilter`, etc.
- Each rule generates a state chart PNG in `tests/actors/_state_charts/` via `graphviz`.

### Testing Infrastructure (`tests/helper/`)

- `TestCaseBase` — mocks OpenHAB items and intercepts commands/updates.
- `TestCaseBaseStateMachine` — extends `TestCaseBase` with mocked `threading.Timer` for deterministic state machine tests.
- `oh_item.py` — helpers to create and manipulate mocked items.
- `rule_runner.py` — runs rules in an isolated environment.

## Changelog

Always add an entry to `CHANGELOG.md` for every change. Entries go under the topmost (unreleased) version block, in the appropriate section (`Breaking changes`, `Features`, or `Bugfix`).

## Code Quality Requirements

- **100% branch coverage** is enforced (`coverage html --fail-under=100`). Every new code path needs a test.
- **Ruff** line length: 250 characters. Docstring style: Google.
- **MyPy** strict typing with the Pydantic plugin enabled.
- Pre-push hooks enforce all of the above automatically via `prek`.
