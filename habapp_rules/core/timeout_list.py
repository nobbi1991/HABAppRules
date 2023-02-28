"""Test for timeout_list"""
import dataclasses
import time
import typing


@dataclasses.dataclass
class ValueWithTimeout:
	"""Define item for TimeoutList"""
	value: typing.Any
	timeout: float
	add_timestamp: float


class TimeoutList:
	"""List like class, where every item has a timeout, which will remove it from the list."""

	def __init__(self) -> None:
		"""Init class"""
		self.__items: list[ValueWithTimeout] = []

	def __repr__(self) -> str:
		"""Get representation of all list items (without timeout)

		:return: all list elements which are currently in the list
		"""
		self.__remove_old_items()
		return str([itm.value for itm in self.__items])

	def __bool__(self) -> bool:
		"""Check if list has items

		:return: true if items in list
		"""
		self.__remove_old_items()
		return bool(self.__items)

	def __contains__(self, item: typing.Any) -> bool:
		"""Check if an item is in the list

		:param item: item which should be checked
		:return: true if item is in the list
		"""
		self.__remove_old_items()
		return item in [itm.value for itm in self.__items]

	def __getitem__(self, index: int) -> typing.Any:
		"""Get item from list by index

		:param index: index of item position in list.
		:return: item from list
		"""
		self.__remove_old_items()
		return self.__items[index].value

	def __eq__(self, other: typing.Any) -> bool:
		"""Check if equal.

		:param other: other item
		:return: true if equal
		"""
		if isinstance(other, TimeoutList):
			return repr(self) == repr(other)

		if isinstance(other, list):
			self.__remove_old_items()
			return [itm.value for itm in self.__items] == other

		return False

	def __remove_old_items(self) -> None:
		"""Remove items from list, which are timed-out."""
		current_time = time.time()
		self.__items = [itm for itm in self.__items if current_time - itm.add_timestamp < itm.timeout]

	def append(self, item: typing.Any, timeout: float) -> None:
		"""Add item to list

		:param item: item which should be added to the list
		:param timeout: timeout, after which the item is not valid anymore
		"""
		self.__items.append(ValueWithTimeout(item, timeout, time.time()))

	def remove(self, item: typing.Any) -> None:
		"""Remove item from list. If there are duplicates. The first element will be removed.

		:param item: item which should be deleted
		:raises ValueError: if item not in list
		"""
		item_to_remove = next((itm for itm in self.__items if itm.value == item), None)

		if not item_to_remove:
			raise ValueError(f"{self.__class__.__name__}.remove(x): x not in list")

		self.__items.remove(item_to_remove)

	def pop(self, element_index: int) -> typing.Any:
		"""Pop item from list

		:param element_index: list index of element which should be deleted
		:return: item which was removed
		:raises IndexError: if index is out of range
		:raises TypeError: if index can not be interpreted as integer
		"""
		return self.__items.pop(element_index).value
