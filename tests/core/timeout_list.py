"""Unittest for TimeoutList."""
import unittest
import unittest.mock

import habapp_rules.core.timeout_list


class TestTimeoutList(unittest.TestCase):
	"""Tests for TimeoutList."""

	def setUp(self) -> None:
		"""Setup Tests."""
		self.normal_list = []
		self.timeout_list = habapp_rules.core.timeout_list.TimeoutList()

	def test_repr(self):
		"""Test repr of TimeoutList."""
		self.assertEqual(str(self.normal_list), str(self.timeout_list))
		for add_value in [None, "some_string", 14, 42.2]:
			self.normal_list.append(add_value)
			self.timeout_list.append(add_value, 100)
			self.assertEqual(str(self.normal_list), str(self.timeout_list))

	def test_bool(self):
		"""Test bool of TimeoutList."""
		with unittest.mock.patch.object(self.timeout_list, "_TimeoutList__remove_old_items") as remove_mock:
			self.assertFalse(bool(self.timeout_list))
			remove_mock.assert_called_once()

			remove_mock.reset_mock()
			self.timeout_list.append(42, 10)
			self.assertTrue(bool(self.timeout_list))
			remove_mock.assert_called_once()

	def test_contains(self):
		"""Test contains of TimeoutList."""
		with unittest.mock.patch.object(self.timeout_list, "_TimeoutList__remove_old_items") as remove_mock:
			# empty list
			self.assertFalse(42 in self.timeout_list)
			self.assertFalse("test" in self.timeout_list)
			self.assertEqual(2, remove_mock.call_count)

			# add 42
			remove_mock.reset_mock()
			self.timeout_list.append(42, 10)
			self.assertTrue(42 in self.timeout_list)
			self.assertFalse("test" in self.timeout_list)
			self.assertEqual(2, remove_mock.call_count)

			# add test string
			remove_mock.reset_mock()
			self.timeout_list.append("test", 10)
			self.assertTrue(42 in self.timeout_list)
			self.assertTrue("test" in self.timeout_list)
			self.assertEqual(2, remove_mock.call_count)

	def test_get_item(self):
		"""Test getting item from TimeoutList."""
		# empty list
		with self.assertRaises(IndexError):
			self.assertIsNone(self.timeout_list[0])

		with self.assertRaises(IndexError):
			self.assertIsNone(self.timeout_list[1])

		# list with two elements
		self.timeout_list.append("test", 10)
		self.timeout_list.append(42, 10)

		self.assertEqual("test", self.timeout_list[0])
		self.assertEqual(42, self.timeout_list[1])

		with self.assertRaises(IndexError):
			self.assertIsNone(self.timeout_list[2])

	def test_equal(self):
		"""Test equal of TimeoutList."""
		with unittest.mock.patch.object(self.timeout_list, "_TimeoutList__remove_old_items") as remove_old_mock:
			self.assertEqual(self.timeout_list, habapp_rules.core.timeout_list.TimeoutList())
			self.assertEqual(1, remove_old_mock.call_count)

			self.assertEqual(self.timeout_list, [])
			self.assertEqual(2, remove_old_mock.call_count)

			self.timeout_list.append(42, 10)
			self.assertEqual(self.timeout_list, [42])
			self.assertEqual(3, remove_old_mock.call_count)

			self.assertNotEqual(self.timeout_list, "")
			self.assertEqual(3, remove_old_mock.call_count)

	def test_not_equal(self):
		"""Test not equal of TimeoutList."""
		self.assertFalse(self.timeout_list != [])

		self.timeout_list.append(42, 10)
		self.assertTrue(self.timeout_list != [])
		self.assertTrue(self.timeout_list != [80])
		self.assertFalse(self.timeout_list != [42])

	def test_remove(self):
		"""Test remove of TimeoutList."""
		with self.assertRaises(ValueError) as context:
			self.timeout_list.remove(42)
		self.assertEqual("TimeoutList.remove(x): x not in list", str(context.exception))

		self.timeout_list.append(42, 10)
		self.timeout_list.append("test", 10)
		self.assertIsNone(self.timeout_list.remove(42))

		self.assertEqual(self.timeout_list, ["test"])

	def test_pop(self):
		"""Test pop of TimeoutList."""
		with self.assertRaises(IndexError):
			self.timeout_list.pop(0)

		self.timeout_list.append(42, 10)

		with self.assertRaises(IndexError):
			self.timeout_list.pop(1)

		with self.assertRaises(TypeError):
			self.timeout_list.pop("first")

		self.assertEqual(42, self.timeout_list.pop(0))
		self.assertEqual([], self.timeout_list)

		self.timeout_list.append(42, 10)
		self.timeout_list.append("test", 10)
		self.assertEqual("test", self.timeout_list.pop(1))
		self.assertEqual([42], self.timeout_list)
