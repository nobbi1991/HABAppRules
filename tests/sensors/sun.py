"""Tests for sun sensors."""
import collections
import unittest.mock

import HABApp

import habapp_rules.sensors.sun
import tests.helper.graph_machines
import tests.helper.oh_item
import tests.helper.rule_runner
import tests.helper.test_case_base


# pylint: disable=no-member, protected-access, too-many-public-methods
class TestSensorTempDiff(tests.helper.test_case_base.TestCaseBase):
	"""Tests cases for testing sun sensor 'temp_diff' rule."""

	def setUp(self) -> None:
		"""Setup test case."""
		tests.helper.test_case_base.TestCaseBase.setUp(self)

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Temperature_1", None)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Temperature_2", None)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Output_Temperature", None)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Threshold_Temperature", 10)

		self._sensor = habapp_rules.sensors.sun.SensorTempDiff("Unittest_Temperature_1", "Unittest_Temperature_2", "Unittest_Threshold_Temperature", "Unittest_Output_Temperature")

	def test_init_with_fixed_threshold(self):
		"""Test __init__ with fixed threshold value."""
		sensor = habapp_rules.sensors.sun.SensorTempDiff("Unittest_Temperature_1", "Unittest_Temperature_2", 42, "Unittest_Output_Temperature")
		self.assertEqual(42, sensor._hysteresis._threshold)

	def test_cb_threshold(self):
		"""Test _cb_threshold"""
		tests.helper.oh_item.item_state_change_event("Unittest_Threshold_Temperature", 20)
		self.assertEqual(20, self._sensor._hysteresis._threshold)

	def test_overall_behavior(self):
		"""Test overall behavior"""
		output_item = HABApp.openhab.items.OpenhabItem.get_item("Unittest_Output_Temperature")
		self.assertEqual(None, output_item.value)

		# update temperature 1
		tests.helper.oh_item.item_state_change_event("Unittest_Temperature_1", 20)
		self.assertEqual(None, output_item.value)

		# update temperature 2
		tests.helper.oh_item.item_state_change_event("Unittest_Temperature_2", 20)
		self.assertEqual("OFF", output_item.value)

		# update temperature 2
		tests.helper.oh_item.item_state_change_event("Unittest_Temperature_2", 30)
		self.assertEqual("OFF", output_item.value)

		# update temperature 2
		tests.helper.oh_item.item_state_change_event("Unittest_Temperature_2", 30.5)
		self.assertEqual("ON", output_item.value)

		# update temperature 1
		tests.helper.oh_item.item_state_change_event("Unittest_Temperature_1", 21)
		self.assertEqual("ON", output_item.value)

		# update temperature 1
		tests.helper.oh_item.item_state_change_event("Unittest_Temperature_1", 21.1)
		self.assertEqual("OFF", output_item.value)


class TestSensorBrightness(tests.helper.test_case_base.TestCaseBase):
	"""Tests cases for testing sun sensor 'brightness' rule."""

	def setUp(self) -> None:
		"""Setup test case."""
		tests.helper.test_case_base.TestCaseBase.setUp(self)

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Brightness", None)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Output_Brightness", None)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Threshold_Brightness", 1000)

		self._sensor = habapp_rules.sensors.sun.SensorBrightness("Unittest_Brightness", "Unittest_Threshold_Brightness", "Unittest_Output_Brightness")

	def test_init_with_fixed_threshold(self):
		"""Test __init__ with fixed threshold value."""
		sensor = habapp_rules.sensors.sun.SensorBrightness("Unittest_Brightness", 42, "Unittest_Output_Brightness")
		self.assertEqual(42, sensor._hysteresis._threshold)

	def test_cb_threshold(self):
		"""Test _cb_threshold."""
		tests.helper.oh_item.item_state_change_event("Unittest_Threshold_Brightness", 42000)
		self.assertEqual(42000, self._sensor._hysteresis._threshold)

	def test_overall_behavior(self):
		"""Test overall behavior"""
		output_item = HABApp.openhab.items.OpenhabItem.get_item("Unittest_Output_Brightness")

		# update brightness
		tests.helper.oh_item.item_state_change_event("Unittest_Brightness", 20)
		self.assertEqual("OFF", output_item.value)

		# update brightness
		tests.helper.oh_item.item_state_change_event("Unittest_Brightness", 1100)
		self.assertEqual("ON", output_item.value)

		# update brightness
		tests.helper.oh_item.item_state_change_event("Unittest_Brightness", 1000)
		self.assertEqual("ON", output_item.value)

		# update brightness
		tests.helper.oh_item.item_state_change_event("Unittest_Brightness", 900)
		self.assertEqual("OFF", output_item.value)


class TestSunPositionWindow(tests.helper.test_case_base.TestCaseBase):
	"""Tests cases for testing the sun position filter."""

	def test_init(self):
		"""Test __init__"""
		# normal init
		expected_result = habapp_rules.sensors.sun.SunPositionWindow(10, 80, 2, 20)
		self.assertEqual(expected_result, habapp_rules.sensors.sun.SunPositionWindow(10, 80, 2, 20))

		# init without elevation
		expected_result = habapp_rules.sensors.sun.SunPositionWindow(10, 80, 0, 90)
		self.assertEqual(expected_result, habapp_rules.sensors.sun.SunPositionWindow(10, 80))

		# init with min > max
		expected_result = habapp_rules.sensors.sun.SunPositionWindow(10, 80, 2, 20)
		self.assertEqual(expected_result, habapp_rules.sensors.sun.SunPositionWindow(80, 10, 20, 2))


class TestSunPositionFilter(tests.helper.test_case_base.TestCaseBase):
	"""Tests cases for testing the sun position filter."""

	def setUp(self) -> None:
		"""Setup test case."""
		tests.helper.test_case_base.TestCaseBase.setUp(self)

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Input_1", None)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Output_1", None)

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Input_2", None)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Output_2", None)

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Azimuth", 1000)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Elevation", 1000)

		self.position_window_1 = habapp_rules.sensors.sun.SunPositionWindow(10, 80, 2, 20)
		self.position_window_2 = habapp_rules.sensors.sun.SunPositionWindow(100, 120)

		self._filter_1 = habapp_rules.sensors.sun.SunPositionFilter(self.position_window_1, "Unittest_Azimuth", "Unittest_Elevation", "Unittest_Input_1", "Unittest_Output_1")
		self._filter_2 = habapp_rules.sensors.sun.SunPositionFilter([self.position_window_1, self.position_window_2], "Unittest_Azimuth", "Unittest_Elevation", "Unittest_Input_2", "Unittest_Output_2")

	def test_init(self):
		"""Test __init__"""
		self.assertEqual([self.position_window_1], self._filter_1._position_window)
		self.assertEqual([self.position_window_1, self.position_window_2], self._filter_2._position_window)

	def test_filter(self):
		"""Test if filter is working correctly."""
		TestCase = collections.namedtuple("TestCase", "azimuth, elevation, input, output_1, output_2")

		test_cases = [
			TestCase(0, 0, "OFF", "OFF", "OFF"),
			TestCase(0, 10, "OFF", "OFF", "OFF"),
			TestCase(50, 0, "OFF", "OFF", "OFF"),
			TestCase(50, 10, "OFF", "OFF", "OFF"),

			TestCase(0, 0, "ON", "OFF", "OFF"),
			TestCase(0, 10, "ON", "OFF", "OFF"),
			TestCase(50, 0, "ON", "OFF", "OFF"),
			TestCase(50, 10, "ON", "ON", "ON"),

			TestCase(0, 0, "OFF", "OFF", "OFF"),
			TestCase(0, 10, "OFF", "OFF", "OFF"),
			TestCase(110, 0, "OFF", "OFF", "OFF"),
			TestCase(110, 10, "OFF", "OFF", "OFF"),

			TestCase(0, 0, "ON", "OFF", "OFF"),
			TestCase(0, 10, "ON", "OFF", "OFF"),
			TestCase(110, 0, "ON", "OFF", "ON"),
			TestCase(110, 10, "ON", "OFF", "ON"),

			TestCase(50, None, "OFF", "OFF", "OFF"),
			TestCase(None, 10, "OFF", "OFF", "OFF"),
			TestCase(None, None, "OFF", "OFF", "OFF"),

			TestCase(50, None, "ON", "ON", "ON"),
			TestCase(None, 10, "ON", "ON", "ON"),
			TestCase(None, None, "ON", "ON", "ON"),
		]

		item_output_1 = HABApp.openhab.items.OpenhabItem.get_item("Unittest_Output_1")
		item_output_2 = HABApp.openhab.items.OpenhabItem.get_item("Unittest_Output_2")

		with unittest.mock.patch.object(self._filter_1, "_instance_logger") as log_1_mock, unittest.mock.patch.object(self._filter_2, "_instance_logger") as log_2_mock:
			for test_case in test_cases:
				log_1_mock.reset_mock()
				log_2_mock.reset_mock()

				tests.helper.oh_item.set_state("Unittest_Input_1", test_case.input)
				tests.helper.oh_item.set_state("Unittest_Input_2", test_case.input)

				tests.helper.oh_item.item_state_change_event("Unittest_Elevation", test_case.elevation)
				tests.helper.oh_item.item_state_change_event("Unittest_Azimuth", test_case.azimuth)

				self.assertEqual(test_case.output_1, item_output_1.value)
				self.assertEqual(test_case.output_2, item_output_2.value)

				if test_case.azimuth is None or test_case.elevation is None:
					log_1_mock.warning.assert_called_once()
					log_2_mock.warning.assert_called_once()
				else:
					log_1_mock.warning.assert_not_called()
					log_2_mock.warning.assert_not_called()
