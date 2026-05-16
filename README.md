# habapp_rules

A Python library of ready-to-use automation rules for [HABApp](https://habapp.readthedocs.io/), built on top of [OpenHAB](https://www.openhab.org/).
Rules model real-world smart home scenarios as state machines powered by the [`transitions`](https://github.com/pytransitions/transitions) library.

## Modules at a glance

| Module | Rules | Purpose |
|--------|-------|---------|
| `actors` | Light, LightHcl, BathroomLight, Shading, Ventilation, Heating, Irrigation, EnergySaveSwitch | Smart device control |
| `sensors` | Motion, Sun, Astro, DwdWindAlarm, HumiditySwitch, CurrentSwitch | Environmental monitoring & filtering |
| `energy` | VirtualEnergyMeter, MonthlyReport | Energy tracking & monthly email reports |
| `system` | Presence, Sleep, RecurringTask, CounterTask, SummerWinter, SendStateChanged, ItemWatchdog | Home automation logic |
| `media` | Sonos | Sonos speaker control |
| `network` | Wol | Wake-on-LAN |
| `bridge` | KnxMqttDimmerBridge | KNX ↔ MQTT protocol bridge |
| `common` | HysteresisSwitch, ExponentialFilter, And/Or/Not, InvertValue, NumericLogic | Reusable utility rules |

## Requirements

- Python ≥ 3.11
- OpenHAB with HABApp 25.12.0

## Installation

```bash
pip install habapp_rules
```

## Usage

Each rule follows the same pattern: define an `Items` class (OpenHAB item references), a `Parameter` class (tuning knobs), combine them into a `Config`, and pass it to the rule constructor.

```python
# rules/my_rules.py  (HABApp rules file)
import multi_notifier.connectors.connector_mail as mail_connector

from habapp_rules.energy.config.monthly_report import (
    EnergyShare,
    MonthlyReportConfig,
    MonthlyReportItems,
    MonthlyReportParameter,
)
from habapp_rules.energy.monthly_report import MonthlyReport
from habapp_rules.system.config.presence import PresenceConfig, PresenceItems, PresenceParameter
from habapp_rules.system.presence import Presence

# Presence detection
Presence(
    PresenceConfig(
        items=PresenceItems(
            presence="Presence_State",
            leaving="Presence_Leaving",
            absence="Presence_Absence",
        ),
        parameter=PresenceParameter(
            phones=["Phone_Norbert", "Phone_Anna"],
        ),
    )
)

# Monthly energy report by email
MonthlyReport(
    MonthlyReportConfig(
        items=MonthlyReportItems(energy_sum="Energy_Total"),
        parameter=MonthlyReportParameter(
            known_energy_shares=[
                EnergyShare("Energy_Dishwasher", "Dishwasher"),
                EnergyShare("Energy_WashingMachine", "Washing machine"),
            ],
            config_mail=mail_connector.MailConfig(
                user="sender@example.com",
                password="secret",
                smtp_host="smtp.example.com",
                smtp_port=587,
            ),
            recipients=["me@example.com"],
            history_months=12,
        ),
    )
)
```

## Rule overview

### actors

| Rule | Description |
|------|-------------|
| `Light` | Dimmable/switchable light with manual override, presence, sleep, motion, door, and pre-sleep states |
| `LightHcl` | Human-Centric Lighting — adjusts colour temperature by sun elevation or time of day |
| `BathroomLight` | Bathroom light with separate main and mirror brightness for day/night/sleep |
| `Shading` | Roller shutter / blind control with wind alarm, sun protection, sleep, night close, and door-open positions |
| `Ventilation` | Multi-stage ventilation with hand/external requests and long-absence reduction |
| `Heating` | KNX heating with configurable offset; `HeatingActive` sets a flag when any actor is active |
| `Irrigation` | Garden watering with schedule, repetitions, and brake times |
| `EnergySaveSwitch` | Smart switch with presence/sleep conditions, current-based waiting, and max-on timeout |

### sensors

| Rule | Description |
|------|-------------|
| `Motion` | Motion sensor with brightness lock, sleep-based suppression, and hysteresis |
| `Sun` (Brightness / TemperatureDifference) | Exponential-filtered sun signal with hysteresis for sun protection |
| `Astro` (SetDay / SetNight) | Sets a day/night switch based on sun elevation threshold |
| `DwdWindAlarm` | Wind alarm state driven by DWD (German Weather Service) warnings |
| `HumiditySwitch` | Detects high humidity or rapid changes with extended timeout |
| `CurrentSwitch` | Switches ON when electrical current exceeds a threshold |

### energy

| Rule | Description |
|------|-------------|
| `VirtualEnergyMeterSwitch` / `VirtualEnergyMeterNumber` | Estimates energy for devices without real metering by tracking on-time |
| `MonthlyReport` | Sends a monthly HTML email with a donut chart (current month breakdown) and a bar chart of the last N months |

### system

| Rule | Description |
|------|-------------|
| `Presence` | State machine: Present → Leaving → Absence → LongAbsence, driven by phones and door contacts |
| `Sleep` | State machine: Awake → PreSleeping → Sleeping → PostSleeping, with lock support |
| `RecurringTask` | Triggers a task item ON when its recurrence interval (or fixed time) is reached |
| `CounterTask` | Sets a switch ON when a numeric item exceeds a threshold |
| `SummerWinter` | Detects summer/winter from outdoor temperature using weighted mean and hysteresis |
| `SendStateChanged` | Sends a Telegram/email notification when an OpenHAB item changes |
| `ItemWatchdog` | Raises a warning if an item is not updated within a configurable timeout |

### media / network / bridge / common

| Rule | Description |
|------|-------------|
| `Sonos` | Sonos speaker lifecycle (power, booting, standby, playback) with volume lock and favourites |
| `Wol` | Sends a Wake-on-LAN magic packet to a target MAC address |
| `KnxMqttDimmerBridge` | Translates KNX wall switch commands to MQTT dimmer commands |
| `HysteresisSwitch` | Threshold switch with configurable upper/lower hysteresis bands |
| `ExponentialFilter` | First-order exponential filter with optional instant-rise or instant-fall |
| `And` / `Or` / `Not` / `InvertValue` | Boolean logic combining multiple switch/contact items |
| `NumericLogic` (Min/Max/Average) | Combines multiple numeric items into a single output |

## Development

### Setup

```bash
uv sync --frozen --all-groups
```

### Common commands

| Task | Command |
|------|---------|
| Run all tests with coverage | `uv run scripts/run_tests_with_coverage.py` |
| Run a single test | `uv run python -m unittest tests.actors.light.TestLightBase.test_manual_on` |
| Format | `uv run ruff format habapp_rules/` |
| Lint | `uv run ruff check --fix habapp_rules/` |
| Type check | `uv run mypy habapp_rules` |
| All pre-push checks | `uv run prek run --all-files` |
| Build | `uv build` |

100% branch coverage is enforced. Every new code path must have a test.

### Dependency management

```bash
# Add a runtime dependency
uv add <package>

# Add a dev dependency
uv add <package> --group dev

# Update all dependencies and lockfile
uv sync -U --all-groups

# Update lockfile only
uv lock -U
```
