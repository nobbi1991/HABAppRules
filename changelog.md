# Version 2.2.0 - dd.mm.yyyy

## Features

- Added ``habapp_rules.actors.light`` to control lights:
  - ``habapp_rules.actors.light.Light`` for basic light functionality like switch-on brightness or leaving / sleeping light
  - ``habapp_rules.actors.light.LightExtended`` includes everything from ``habapp_rules.actors.light.Light`` plus switch on depending on movement or opening of a door
- Added ``habapp_rules.core.timeout_list``
- Moved some modules from ``common`` to ``core``
- removed ``helper`` submodule and switched to ``nose_helper`` package
- Added logging of ``habapp_rules`` version

# Version 2.1.1 - 04.02.2023

## Bugfix

- Fixed bug of `habapp_rules.system.presence.Presence` where `long_absence` would be set to `absence ` if there was an restart of HABApp
- Fixed bug of `habapp_rules.system.presence.Presence` where it was not possible to change state to `leaving` from `absence` or `long_absence` by leaving-switch

# Version 2.1.0 - 01.02.2023

## Features

- Added more logging to `habapp_rules.system.sleep.Sleep`, `habapp_rules.system.presence.Presence`, `habapp_rules.system.summer_winter.SummerWinter`

## Bugfix

- Fixed bug where timers would not start at initial state of `habapp_rules.system.sleep.Sleep` and `habapp_rules.system.presence.Presence` would not start

# Version 2.0.1 - 31.01.2023

## Bugfix

- Fixed bug at summer / winter where `last_check_name` could not be set

# Version 2.0.0 - 10.11.2022

## General

- removed communication modules

## Features

- Added nox checks

# Version 1.1.0 - 08.08.2022

## Features

- Added logical function rules (AND + OR)
