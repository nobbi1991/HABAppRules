import logging
import typing

from habapp_rules.actors.config.energy_save_switch import EnergySaveSwitchConfig, EnergySaveSwitchItems, EnergySaveSwitchParameter
from habapp_rules.actors.config.energy_save_wama_dryer import EnergySaveWaMaDryerConfig
from habapp_rules.actors.energy_save_switch import EnergySaveSwitch
from habapp_rules.core.helper import create_additional_item
from habapp_rules.core.logger import InstanceLogger
from habapp_rules.core.state_machine_rule import StateMachineRule

LOGGER = logging.getLogger(__name__)


class EnergySaveWaMaDryer(StateMachineRule):
    states: typing.ClassVar = [
        {"name": "Manual"},
        {"name": "Hand", "timeout": 0, "on_timeout": ["_auto_hand_timeout"]},
        {"name": "Auto", "initial": "Init", "children": [{"name": "Init"}, {"name": "AllOff"}, {"name": "AllOn"}, {"name": "OnlyWaMa"}, {"name": "OnlyDryer"}, {"name": "WaMaWaiting", "timeout": 0, "on_timeout": ["_wama_wait_timeout"]}]},
    ]

    trans: typing.ClassVar = [
        # lock
        {"trigger": "wama_on", "source": "Auto_AllOff", "dest": "Auto_WaMaWaiting", "conditions": "_wama_is_programmed"},
        {"trigger": "wama_on", "source": "Auto_AllOff", "dest": "Auto_OnlyWaMa", "unless": "_wama_is_programmed"},
        {"trigger": "wama_on", "source": "Auto_OnlyDryer", "dest": "Auto_AllOn", "unless": "_wama_is_programmed"},
        {"trigger": "dryer_on", "source": "Auto_AllOff", "dest": "Auto_OnlyDryer"},
        {"trigger": "dryer_on", "source": "Auto_OnlyWaMa", "dest": "Auto_AllOn"},
    ]

    def __init__(self, config: EnergySaveWaMaDryerConfig) -> None:
        """Initialize EnergySaveWaMaDryer.

        Args:
            config: Config for energy save washing machine / dryer
        """
        self._config = config
        self.state = "Auto_Init"  # TODO: remove

        base_name = self._config.items.state.name.removeprefix("I").removesuffix("_state").removesuffix("_State")
        wama_state_item = create_additional_item(f"H_{base_name}_WaMa_state", "String")
        dryer_state_item = create_additional_item(f"H_{base_name}_Dryer_state", "String")

        self._rule_wama = EnergySaveSwitch(
            EnergySaveSwitchConfig(
                items=EnergySaveSwitchItems(switch=self._config.items.wama_switch, state=wama_state_item.name, external_request=self._config.items.external_request, manual=self._config.items.manual, current=self._config.items.wama_current),
                parameter=EnergySaveSwitchParameter(
                    current_threshold=self._config.parameter.wama_current_threshold, extended_wait_for_current_time=self._config.parameter.wama_extended_wait_for_current_time, hand_timeout=self._config.parameter.wama_hand_timeout
                ),
            )
        )

        self._rule_dryer = EnergySaveSwitch(
            EnergySaveSwitchConfig(
                items=EnergySaveSwitchItems(switch=self._config.items.dryer_switch, state=dryer_state_item.name, external_request=self._config.items.external_request, manual=self._config.items.manual, current=self._config.items.dryer_current),
                parameter=EnergySaveSwitchParameter(
                    current_threshold=self._config.parameter.dryer_current_threshold, extended_wait_for_current_time=self._config.parameter.dryer_extended_wait_for_current_time, hand_timeout=self._config.parameter.dryer_hand_timeout
                ),
            )
        )

        StateMachineRule.__init__(self, self._config.items.state)
        self._instance_logger = InstanceLogger(LOGGER, self._config.items.state.name)
