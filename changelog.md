# Version 5.5.0 - 05.03.2024

## Features

- added rules in ``habapp_rules.actors.ventilation`` to control ventilation objects
- added ``name_switch_on`` to ``habapp_rules.actors.light_hcl.HclTime`` and ``habapp_rules.actors.light_hcl.HclElevation`` to add the possibility to also update the color if a item switches on
- added new transition to ``habapp_rules.actors.light._LightExtendedMixin`` to also switch on the light if current state is ``auto_preoff`` and the door opened
- added ``habapp_rules.sensors.dwd.DwdWindAlarm`` to set wind alarm depending on DWD warnings
- added ``habapp_rules.core.version.SetVersions`` to set versions of HABApp and habapp_rules to OpenHAB items
- added ``habapp_rules.common.logic.InvertValue`` which can be used to set the inverted value of one item to another
- bumped holidays to 0.44
- bumped HABApp to 24.02.0

# Bugfix

- fixed bug in ``habapp_rules.actors.state_observer.StateObserverNumber`` which triggered the manual-detected-callback if the received number deviates only a little bit because of data types. (e.g.: 1.000001 != 1.0) 
- fixed bug for dimmer lights in ``habapp_rules.actors.light`` which did not set the correct brightness if light was switched on.
- fixed bug in ``habapp_rules.common.hysteresis.HysteresisSwitch.get_output`` resulted in a wrong switch state if the value was 0. 
- added missing state transition to ``habapp_rules.sensors.motion.Motion``. When state was ``PostSleepLocked`` and sleep started there was no change to ``SleepLocked``
- fixed strange behavior of ``habapp_rules.system.presence.Presence`` which did not abort leaving when the first phone appeared. This let to absence state if someone returned when leaving was active.

# Version 5.4.3 - 14.01.2024

## Bugfix

- fixed bug in ``habapp_rules.actors.shading.Raffstore`` which triggered a hand detection also if only small slat differences occurred

# Version 5.4.2 - 14.01.2024

## Bugfix

- fixed bug in all observers of ``habapp_rules.actors.state_observer`` which triggered the manual callback also if the value change of numeric values is tiny
- fixed bug in ``habapp_rules.actors.shading._ShadingBase`` which triggered a hand detection also if only small position differences occurred

# Version 5.4.1 - 26.12.2023

## Bugfix

- fixed bug in ``habapp_rules.core.state_machine.StateMachineRule`` which prevents inheritance of ``habapp_rules``-rules in local rules

# Version 5.4.0 - 25.12.2023

## Features

- added dependabot to keep all dependencies up to date
- added ``habapp_rules.actors.light_hcl`` for setting light temperature depending on time or sun elevation
- added ``habapp_rules.actors.state_observer.StateObserverNumber`` for observe state changes of a number item

## Bugfix

- fixed too short restore time for all light rules when sleep was aborted in ``habapp_rules.actors.light._LightBase``

# Version 5.3.1 - 30.11.2023

## Bugfix

- fixed bug in ``habapp_rules.core.state_machine_rule.on_rule_removed`` which did not remove rules which have a hierarchical state machine

# Version 5.3.0 - 21.11.2023

## Features

- added ``habapp_rules.common.logic.Sum`` for calculation the sum of number items

## Bugfix

- only use items (instead item names) for all habapp_rules implementations which are using ``habapp_rules.core.helper.send_if_different``
- cancel timer / timeouts of replaced rules

# Version 5.2.1 - 17.10.2023

## Bugfix

- fixed bug in ``habapp_rules.actors.shading.ResetAllManualHand`` which did not reset all shading objects if triggered via KNX

# Version 5.2.0 - 10.10.2023

## Features

- added rule ``habapp_rules.system.sleep.LinkSleep`` to link multiple sleep rules

## Bugfix

- fixed bug in ``habapp_rules.actors.shading.ResetAllManualHand`` which did not always reset all shading instances.
- fixed bug in ``habapp_rules.actors.shading._ShadingBase`` which caused wrong shading states after sleeping or night

# Version 5.1.0 - 06.10.2023

## Features

- added rule ``habapp_rules.sensors.astro.SetNight`` and ``habapp_rules.sensors.astro.SetDay`` to set / unset night and day state depending on sun elevation

## Bugfix

- fixed bug in ``habapp_rules.actors.shading._ShadingBase`` which caused a switch to night close if it was not configured.

# Version 5.0.0 - 01.10.2023

## Breaking changes

- added support for more than two sensor values to ``habapp_rules.sensors.sun.SensorTemperatureDifference``. Breaking change: Item names must be given as list of names.

## Features

- added logic functions ``habapp_rules.common.logic.Min`` and ``habapp_rules.common.logic.Max``
- updated HABApp to 23.09.02

# Version 4.1.0 - 27.09.2023

## Features

- Updated docker container to use python 3.11

# Version 4.0.0 - 13.09.2023

## Breaking changes

- renamed ``habapp_rules.actors.light.Light`` to ``habapp_rules.actors.light.LightDimmer`` and ``habapp_rules.actors.light.LightExtended`` to ``habapp_rules.actors.light.LightDimmerExtended``
- moved / renamed ``habapp_rules.actors.light_config`` to ``habapp_rules.actors.config.light``
- changed parameter names and order of ``habapp_rules.bridge.knx_mqtt.KnxMqttDimmerBridge`` and added support for KNX switch items
- all items which are created from habapp_rules start with prefix ``H_``
- removed ``_create_additional_item`` from ``habapp_rules.core.state_machine_rule.StateMachineRule`` and added it as standalone function: ``habapp_rules.core.helper.create_additional_item``

## Features

- added ``habapp_rules.actors.light.LightSwitch`` and ``habapp_rules.actors.light.LightSwitchExtended`` which add the support for ``switch`` lights
- added ``habapp_rules.sensors.sun`` to handle and filter different kind of sun sensors
- added ``habapp_rules.common.filter.ExponentialFilter`` to apply a exponential filter to a number item. This can be used to smoothen signals.
- added ``habapp_rules.actors.shading`` to handle shading objects
- increased startup speed by upgrading to HABApp==23.09.0

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
