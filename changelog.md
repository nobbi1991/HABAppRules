# Version 9.0.0 - 16.11.2025

## Breaking changes

- renamed `cb_brightness_change` of `habapp_rules.actors.state_observer.StateObserverDimmer` to `cb_change`

## Features

- added `habapp_rules.media.sonos.Sonos` to control and monitor Sonos Speaker
- added `habapp_rules.system.task.CounterTask` to set a task item to `ON` if a value is exceeded
- made `last_done` of `habapp_rules.system.task.RecurringTask` optional. If not set, a item will be created by habapp_rules

# Version 8.1.5 - 20.10.2025

## Project related

- internal stuff

# Version 8.1.4 - 20.10.2025

## Project related

- removed requirements.txt and moved dependencies to pyproject.toml
- use UV for locking versions of dependencies
- use UV for building and publishing

# Version 8.1.3 - 04.10.2025

## Bugfix

- fixed bugs in `habapp_rules.actors.light_hcl.HclElevation` and `habapp_rules.actors.light_hcl.HclTime`:
  - color was not set if light switched on and state was not `Auto_HCL`
  - color was not set to sleeping color if focus was switched off during sleeping time

# Version 8.1.2 - 03.10.2025

## Bugfix

- removed deprecation triggered by `habapp_rules.system.presence.Presence` if phones are used
- fixed bug in `habapp_rules.system.sleep.Sleep` which did not change back to sleep / awake if request changed in `pre_sleeping` or `post_sleeping`
- added parameter `color_tolerance` to `habapp_rules.actors.light_hcl.config.HclElevationParameter` and `habapp_rules.actors.light_hcl.config.HclTimeParameter` to set the color tolerance for hand detection and avoid false positives if the light can not set exact color values

# Version 8.1.1 - 15.08.2025

## Bugfix

- fixed bug in `habapp_rules.system.presence.Presence` which did not stop the phone-leaving-counter correctly

# Version 8.1.0 - 31.07.2025

## Features

- added support for OpenHAB 5.0
- bumped HABApp to 25.7.0

# Version 8.0.0 - 15.07.2025

## Breaking changes

- bumped HABApp to 25.6.2. Check release infos:
  - [HABApp 25.04.0](https://github.com/spacemanspiff2007/HABApp/releases/tag/25.04.0)
  - [HABApp 25.05.0](https://github.com/spacemanspiff2007/HABApp/releases/tag/25.05.0)
  - [HABApp 25.06.0](https://github.com/spacemanspiff2007/HABApp/releases/tag/25.06.0)

# Version 7.4.3 - 23.03.2025

## Bugfix

- fixed bug in `habapp_rules.energy.montly_report.MonthlyReport` which crashed if one energy-share was negative. Now, this share will be ignored

# Version 7.4.2 - 13.03.2025

## Bugfix

- fixed bug in `habapp_rules.actors.ventilation.VentilationHeliosTwoStage` and `habapp_rules.actors.ventilation.VentilationHeliosTwoStageHumidity` which made the rules unusable if a NumberItem was used

# Version 7.4.1 - 11.03.2025

## Bugfix

- added missing reporting of current `ventilation_level` to `habapp_rules.actors.ventilation.VentilationHeliosTwoStage` and `habapp_rules.actors.ventilation.VentilationHeliosTwoStageHumidity`

# Version 7.4.0 - 10.03.2025

## Features

- added rule `habapp_rules.network.wol.Wol` to wake up devices via Wake-on-LAN
- added rules `habapp_rules.energy.virtual_energy_meter.VirtualEnergyMeterSwitch` and `habapp_rules.energy.virtual_energy_meter.VirtualEnergyMeterNumber` to estimate energy consumption of devices without current / energy measurement
- Added support for multiple energy items to `habapp_rules.energy.config.monthly_report.EnergyShare`

# Version 7.3.0 - 08.02.2025

## Features

- Added parameter `brightness_night_extended` to config of `habapp_rules.actors.light_bathroom.BathroomLight` to configure the brightness for the extended sleep time

# Version 7.2.2 - 02.02.2025

## Bugfix

- Fixed bug in `habapp_rules.actors.energy_save_switch.EnergySaveSwitch` where the max_on_time-timeout switched off the switch, also if external request was active
- Fixed bug in `habapp_rules.actors.light_bathroom.BathroomLight` which set the night brightness also if the light was switched on via dimming

# Version 7.2.1 - 31.12.2024

## Bugfix

- Added workaround for all rules of `habapp_rules.actors.ventilation` for triggering the ventilation if presence state is `long_absence`. Check the following GitHub link for more details: https://github.com/spacemanspiff2007/eascheduler/issues/24

# Version 7.2.0 - 15.12.2024

## Features

- added rule `habapp_rules.actors.shading.ReferenceRun` to trigger the reference run for blinds every month
- added rule `habapp_rules.system.task.RecurringTask` to trigger recurring tasks

## Bugfix

- removed timezone from all datetime.items, since timezone makes no sense in the OpenHAB context

# Version 7.1.0 - 01.12.2024

## Features

- added rule `habapp_rules.actors.light_bathroom.BathroomLight` to control bathroom light
- added the python version to `habapp_rules.core.version.SetVersions`
- added `habapp_rules.sensors.sun.WinterFilter` to filter the sun signal depending on heating state. This can be used to avoid sun protection when heating is active
- added `habapp_rules.actors.heating.HeatingActive` which can be used to set a heating flag if one of the heating actors is active
- improved `habapp_rules.core.timeout_list`

## Bugfix

- added additional wait time to `habapp_rules.actors.energy_save_switch.EnergySaveSwitch` when switch is in wait for current state and current falls below threshold.

# Version 7.0.1 - 25.11.2024

## Bugfix

- bumped HABApp to 24.11.1 to fix startup bug with python 3.13

# Version 7.0.0 - 22.11.2024

## Breaking changes

- bumped HABApp to 24.11.0. Check [release info](https://community.openhab.org/t/habapp-24/152810/27)
- updated docker container to use python 3.13
- renamed all `habapp_rules` exceptions to error. E.g. `habapp_rules.HabAppRulesException` to `habapp_rules.HabAppRulesError`
- renamed `habapp_rules.system.watchdog` to `habapp_rules.system.item_watchdog`
- moved rules of `habapp_rules.actors.power` to `habapp_rules.sensors.current_switch`

## Features

- Added rules in `habapp_rules.actors.energy_save_switch` to switch off sockets during sleeping time or at absence to save energy.

## Bugfix

- moved rules of `habapp_rules.actors.power` to `habapp_rules.sensors.current_switch`. Old location is still supported, but deprecated
- fixed wrong item name in `habapp_rules.energy.monthly_report.MonthlyReport`

# Version 6.2.0 - 06.10.2024

## Features

- added rule `habapp_rules.system.notification.SendStateChanged` which can be used to send a mail or telegram message if the state of an item changes
- added rule `habapp_rules.actors.heating.KnxHeating` which can be used to set the target temperature of a KNX heating actor which only supports temperature offsets
- added temperature difference item of `habapp_rules.sensors.sun.SensorTemperatureDifference` to `filtered_signal_groups`
- added rule `habapp_rules.actors.power.CurrentSwitch` which can be used to enable a switch item if current is above a threshold
- added rule `habapp_rules.system.watchdog.Watchdog` which can be used to check if an item was updated in time

## Bugfix

- fixed bug in `habapp_rules.actors.light.LightSwitchExtended` and `habapp_rules.actors.light.LightDimmerExtended` which did not re-trigger the timer if a door was opened.
- fixed bug in all rules of `habapp_rules.actors.light` where a timer with time=None was used if a light function is not active. Now, the time is changed to 0 sec if a function is not configured.

# Version 6.1.0 - 19.08.2024

## Features

- added support for dimmer items which can be configured for `switch_on` for all rules in `habapp_rules.actors.light_hcl`
- bumped versions:
  - HABApp to 24.08.1
  - multi-notifier to 0.5.0
  - holidays to 0.53

# Version 6.0.1 - 22.07.2024

## Bugfix

- round light color of all rules in `habapp_rules.actors.light_hcl` to integer values to avoid strange formating in OpenHAB
- added config parameter `leaving_only_if_on` to `habapp_rules.actors.config.light.LightParameter` to disable unexpected leaving light, if light was not on and leaving started
- fixed bug in all shading rules of `habapp_rules.actors.shading` which did not switch to sleeping state if previous state was Auto_DoorOpen

# Version 6.0.0 - 27.06.2024

## Breaking changes

- **IMPORTANT**: The config and parameter of all rules changed dramatically! Now, the config must be given as pydantic config object. This enables better valdiation and future releases with less interface changes.

## Features

- added additional config to `habapp_rules.actors.shading.Shutter` and `habapp_rules.actors.shading.Raffstore` which allows to set different positions for day and night if sleeping is active
- added possibility to pass shading objects to `habapp_rules.actors.shading.ResetAllManualHand` which should be reset by this rule
- added `habapp_rules.sensors.humidity.HumiditySwitch` to set a switch item if high humidity is detected. Currently only a absolut threshold is accepted
- send update of summer / winter of `habapp_rules.system.summer_winter.SummerWinter` after every check. If this rule is used to send the summer / winter state to the KNX bus, this ensures, that the state is sent at least once a day
- added hysteresis switch to `habapp_rules.sensors.sun.SensorBrightness` and `habapp_rules.sensors.sun.SunPositionFilter`. Breaking change: Parameter order changed!
- bumped holidays to 0.51
- bumped matplotlib to 3.9.0

## Bugfix

- fixed bug in `habapp_rules.actors.shading.Shutter` and `habapp_rules.actors.shading.Raffstore` which caused the `Hand` state if MDT actors are used

# Version 5.7.0 - 09.04.2024

## Features

- added possibility to add groups to `habapp_rules.core.helper.create_additional_item`
- added possibility to add groups to `habapp_rules.sensors.sun.SensorBrightness` and `habapp_rules.sensors.sun.SensorTemperatureDifference`

# Bugfix

- fixed bug in `habapp_rules.core.helper.create_additional_item` which added a `[%s]` to string items

# Version 5.6.2 - 02.04.2024

# Bugfix

- fixed bug of all rules in `habapp_rules.actors.ventilation` which raised an exception if presence changed to long absence.

# Version 5.6.1 - 01.04.2024

# Bugfix

- fixed bug of missing resources of `habapp_rules.energy.montly_report.MonthlyReport` if used in docker container

# Version 5.6.0 - 24.03.2024

# Features

- added `habapp_rules.energy.montly_report.MonthlyReport` for generating a monthly energy report mail
- bumped holidays to 0.45
- bumped multi-notifier to 0.4.0

# Version 5.5.1 - 07.03.2024

# Bugfix

- fixed bug in `habapp_rules.actors.shading._ShadingBase`, which caused an exception if night state was checked but no day/night item was given

# Version 5.5.0 - 05.03.2024

## Features

- added rules in `habapp_rules.actors.ventilation` to control ventilation objects
- added `name_switch_on` to `habapp_rules.actors.light_hcl.HclTime` and `habapp_rules.actors.light_hcl.HclElevation` to add the possibility to also update the color if a item switches on
- added new transition to `habapp_rules.actors.light._LightExtendedMixin` to also switch on the light if current state is `auto_preoff` and the door opened
- added `habapp_rules.sensors.dwd.DwdWindAlarm` to set wind alarm depending on DWD warnings
- added `habapp_rules.core.version.SetVersions` to set versions of HABApp and habapp_rules to OpenHAB items
- added `habapp_rules.common.logic.InvertValue` which can be used to set the inverted value of one item to another
- bumped holidays to 0.44
- bumped HABApp to 24.02.0

# Bugfix

- fixed bug in `habapp_rules.actors.state_observer.StateObserverNumber` which triggered the manual-detected-callback if the received number deviates only a little bit because of data types. (e.g.: 1.000001 != 1.0)
- fixed bug for dimmer lights in `habapp_rules.actors.light` which did not set the correct brightness if light was switched on.
- fixed bug in `habapp_rules.common.hysteresis.HysteresisSwitch.get_output` resulted in a wrong switch state if the value was 0.
- added missing state transition to `habapp_rules.sensors.motion.Motion`. When state was `PostSleepLocked` and sleep started there was no change to `SleepLocked`
- fixed strange behavior of `habapp_rules.system.presence.Presence` which did not abort leaving when the first phone appeared. This let to absence state if someone returned when leaving was active.

# Version 5.4.3 - 14.01.2024

## Bugfix

- fixed bug in `habapp_rules.actors.shading.Raffstore` which triggered a hand detection also if only small slat differences occurred

# Version 5.4.2 - 14.01.2024

## Bugfix

- fixed bug in all observers of `habapp_rules.actors.state_observer` which triggered the manual callback also if the value change of numeric values is tiny
- fixed bug in `habapp_rules.actors.shading._ShadingBase` which triggered a hand detection also if only small position differences occurred

# Version 5.4.1 - 26.12.2023

## Bugfix

- fixed bug in `habapp_rules.core.state_machine.StateMachineRule` which prevents inheritance of `habapp_rules`-rules in local rules

# Version 5.4.0 - 25.12.2023

## Features

- added dependabot to keep all dependencies up to date
- added `habapp_rules.actors.light_hcl` for setting light temperature depending on time or sun elevation
- added `habapp_rules.actors.state_observer.StateObserverNumber` for observe state changes of a number item

## Bugfix

- fixed too short restore time for all light rules when sleep was aborted in `habapp_rules.actors.light._LightBase`

# Version 5.3.1 - 30.11.2023

## Bugfix

- fixed bug in `habapp_rules.core.state_machine_rule.on_rule_removed` which did not remove rules which have a hierarchical state machine

# Version 5.3.0 - 21.11.2023

## Features

- added `habapp_rules.common.logic.Sum` for calculation the sum of number items

## Bugfix

- only use items (instead item names) for all habapp_rules implementations which are using `habapp_rules.core.helper.send_if_different`
- cancel timer / timeouts of replaced rules

# Version 5.2.1 - 17.10.2023

## Bugfix

- fixed bug in `habapp_rules.actors.shading.ResetAllManualHand` which did not reset all shading objects if triggered via KNX

# Version 5.2.0 - 10.10.2023

## Features

- added rule `habapp_rules.system.sleep.LinkSleep` to link multiple sleep rules

## Bugfix

- fixed bug in `habapp_rules.actors.shading.ResetAllManualHand` which did not always reset all shading instances.
- fixed bug in `habapp_rules.actors.shading._ShadingBase` which caused wrong shading states after sleeping or night

# Version 5.1.0 - 06.10.2023

## Features

- added rule `habapp_rules.sensors.astro.SetNight` and `habapp_rules.sensors.astro.SetDay` to set / unset night and day state depending on sun elevation

## Bugfix

- fixed bug in `habapp_rules.actors.shading._ShadingBase` which caused a switch to night close if it was not configured.

# Version 5.0.0 - 01.10.2023

## Breaking changes

- added support for more than two sensor values to `habapp_rules.sensors.sun.SensorTemperatureDifference`. Breaking change: Item names must be given as list of names.

## Features

- added logic functions `habapp_rules.common.logic.Min` and `habapp_rules.common.logic.Max`
- updated HABApp to 23.09.02

# Version 4.1.0 - 27.09.2023

## Features

- Updated docker container to use python 3.11

# Version 4.0.0 - 13.09.2023

## Breaking changes

- renamed `habapp_rules.actors.light.Light` to `habapp_rules.actors.light.LightDimmer` and `habapp_rules.actors.light.LightExtended` to `habapp_rules.actors.light.LightDimmerExtended`
- moved / renamed `habapp_rules.actors.light_config` to `habapp_rules.actors.config.light`
- changed parameter names and order of `habapp_rules.bridge.knx_mqtt.KnxMqttDimmerBridge` and added support for KNX switch items
- all items which are created from habapp_rules start with prefix `H_`
- removed `_create_additional_item` from `habapp_rules.core.state_machine_rule.StateMachineRule` and added it as standalone function: `habapp_rules.core.helper.create_additional_item`

## Features

- added `habapp_rules.actors.light.LightSwitch` and `habapp_rules.actors.light.LightSwitchExtended` which add the support for `switch` lights
- added `habapp_rules.sensors.sun` to handle and filter different kind of sun sensors
- added `habapp_rules.common.filter.ExponentialFilter` to apply a exponential filter to a number item. This can be used to smoothen signals.
- added `habapp_rules.actors.shading` to handle shading objects
- increased startup speed by upgrading to HABApp==23.09.0

# Version 3.1.1 - 08.05.2023

## Bugfix

- fixed bug of `habapp_rules.actors.irrigation.Irrigation` where type of Number item could be float type

# Version 3.1.0 - 08.05.2023

## Features

- added `habapp_rules.actors.irrigation.Irrigation` to control basic irrigation systems

# Version 3.0.1 - 28.04.2023

## Bugfix

- fixed build of docker image

# Version 3.0.0 - 28.04.2023

## Breaking changes

- Moved some modules from `common` to `core`
- Changed parameter order of `habapp_rules.system.presence.Presence`

## Features

- Added `habapp_rules.actors.light` to control dimmer lights (switch lights will be supported later):
  - `habapp_rules.actors.light.Light` for basic light functionality like switch-on brightness or leaving / sleeping light
  - `habapp_rules.actors.light.LightExtended` includes everything from `habapp_rules.actors.light.Light` plus switch on depending on motion or opening of a door
- Added `habapp_rules.sensors.motion` to filter motion sensors
- Added `habapp_rules.common.hysteresis` as a helper for value depended switch with hysteresis
- Added `habapp_rules.core.timeout_list`
- Added logging of `habapp_rules` version
- Added `habapp_rules.common.hysteresis` which implements a hysteresis switch
- Changed `habapp_rules.system.summer_winter` that one full day of data is enough for summer / winter detected, also if more days are set for mean calculation

## Bugfix

- fixed bug of `habapp_rules.system.presence.Presence` which avoided instantiation if no phone outside_doors where given
- fixed bug of `habapp_rules.core.state_machine.StateMachineRule._create_additional_item` which returned a bool value instead of the created item if an item was created

## GitHub Actions

- Changed updated checkout@v2 to checkout@v3 which uses node16
- Removed `helper` submodule and switched to `nose_helper` package

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
