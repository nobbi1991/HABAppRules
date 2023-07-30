# Version 4.0.0 - dd.mm.2023

## Breaking changes

- renamed ``habapp_rules.actors.light.Light`` to ``habapp_rules.actors.light.LightDimmer`` and ``habapp_rules.actors.light.LightExtended`` to ``habapp_rules.actors.light.LightDimmerExtended``
- changed parameter names and order of ``habapp_rules.bridge.knx_mqtt.KnxMqttDimmerBridge`` and added support for KNX switch items

## Features

- added ``habapp_rules.actors.light.LightSwitch`` and ``habapp_rules.actors.light.LightSwitchExtended`` which add the support for ``switch`` lights
- added ``habapp_rules.sensors.sun`` to handle and filter different kind of sun sensors
- added ``habapp_rules.common.filter.ExponentialFilter`` to apply a exponential filter to a number item. This can be used to smoothen signals.
- increased startup speed by upgrading to habapp~=1.1.0

# Version 3.1.1 - 08.05.2023

## Bugfix

- fixed bug of ``habapp_rules.actors.irrigation.Irrigation`` where type of Number item could be float type

# Version 3.1.0 - 08.05.2023

## Features

- added ``habapp_rules.actors.irrigation.Irrigation`` to control basic irrigation systems

# Version 3.0.1 - 28.04.2023

## Bugfix

- fixed build of docker image

# Version 3.0.0 - 28.04.2023

## Breaking changes

- Moved some modules from ``common`` to ``core``
- Changed parameter order of ``habapp_rules.system.presence.Presence``

## Features

- Added ``habapp_rules.actors.light`` to control dimmer lights (switch lights will be supported later):
    - ``habapp_rules.actors.light.Light`` for basic light functionality like switch-on brightness or leaving / sleeping light
    - ``habapp_rules.actors.light.LightExtended`` includes everything from ``habapp_rules.actors.light.Light`` plus switch on depending on motion or opening of a door
- Added ``habapp_rules.sensors.motion`` to filter motion sensors
- Added ``habapp_rules.common.hysteresis`` as a helper for value depended switch with hysteresis
- Added ``habapp_rules.core.timeout_list``
- Added logging of ``habapp_rules`` version
- Added ``habapp_rules.common.hysteresis`` which implements a hysteresis switch
- Changed ``habapp_rules.system.summer_winter`` that one full day of data is enough for summer / winter detected, also if more days are set for mean calculation

## Bugfix

- fixed bug of ``habapp_rules.system.presence.Presence`` which avoided instantiation if no phone outside_doors where given
- fixed bug of ``habapp_rules.core.state_machine.StateMachineRule._create_additional_item`` which returned a bool value instead of the created item if an item was created

## GitHub Actions

- Changed updated checkout@v2 to checkout@v3 which uses node16
- Removed ``helper`` submodule and switched to ``nose_helper`` package

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
