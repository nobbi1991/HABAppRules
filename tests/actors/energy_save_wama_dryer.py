import pathlib
import sys
import unittest

import HABApp

import tests.helper.graph_machines
import tests.helper.oh_item
import tests.helper.test_case_base
from habapp_rules.actors.config.energy_save_wama_dryer import EnergySaveWaMaDryerConfig, EnergySaveWaMaDryerItems, EnergySaveWaMaDryerParameter
from habapp_rules.actors.energy_save_wama_dryer import EnergySaveWaMaDryer


class TestEnergySaveSwitch(tests.helper.test_case_base.TestCaseBaseStateMachine):
    """Tests cases for testing energy save switch."""

    def setUp(self) -> None:
        """Setup test case."""
        tests.helper.test_case_base.TestCaseBaseStateMachine.setUp(self)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Min_State")
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Min_Manual")
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Min_ExternalRequest")
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Min_WaMaDelayedStart")

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Min_WaMaSwitch")
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Min_WaMaCurrent")
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Min_DryerSwitch")
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Min_DryerCurrent")

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "H_Unittest_Min_WaMa_state")
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "H_Unittest_Min_Dryer_state")

        self._rule_min = EnergySaveWaMaDryer(
            EnergySaveWaMaDryerConfig(
                items=EnergySaveWaMaDryerItems(
                    state="Unittest_Min_State",
                    manual="Unittest_Min_Manual",
                    external_request="Unittest_Min_ExternalRequest",
                    wama_delayed_start="Unittest_Min_WaMaDelayedStart",
                    wama_switch="Unittest_Min_WaMaSwitch",
                    wama_current="Unittest_Min_WaMaCurrent",
                    dryer_switch="Unittest_Min_DryerSwitch",
                    dryer_current="Unittest_Min_DryerCurrent",
                ),
                parameter=EnergySaveWaMaDryerParameter(wama_current_threshold=0.5, dryer_current_threshold=1),
            )
        )

    @unittest.skipIf(sys.platform != "win32", "Should only run on windows when graphviz is installed")
    def test_create_graph(self) -> None:  # pragma: no cover
        """Create state machine graph for documentation."""
        picture_dir = pathlib.Path(__file__).parent / "_state_charts" / "EnergySaveSwitchWaMaDryer"
        if not picture_dir.is_dir():
            picture_dir.mkdir(parents=True)

        graph = tests.helper.graph_machines.HierarchicalGraphMachineTimer(model=tests.helper.graph_machines.FakeModel(), states=self._rule_min.states, transitions=self._rule_min.trans, initial=self._rule_min.state, show_conditions=False)

        graph.get_graph().draw(picture_dir / "EnergySaveSwitchWaMaDryer.png", format="png", prog="dot")

        for state_name in [state for state in self._get_state_names(self._rule_min.states) if "init" not in state.lower()]:
            graph = tests.helper.graph_machines.HierarchicalGraphMachineTimer(model=tests.helper.graph_machines.FakeModel(), states=self._rule_min.states, transitions=self._rule_min.trans, initial=state_name, show_conditions=True)
            graph.get_graph(force_new=True, show_roi=True).draw(picture_dir / f"EnergySaveSwitchWaMaDryer_{state_name}.png", format="png", prog="dot")
