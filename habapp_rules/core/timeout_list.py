"""Test for timeout_list."""

import dataclasses
import time
from collections.abc import Iterator
from typing import Any


@dataclasses.dataclass
class ValueWithTimeout:
    """Define item for TimeoutList."""

    value: object
    timeout: float
    add_timestamp: float

    def __lt__(self, other: "ValueWithTimeout") -> bool:
        """Compare two ValueWithTimeout objects.

        Args:
            other: other object for comparison

        Returns:
            True if self.value is less than other.value
        """
        if not isinstance(other, ValueWithTimeout):
            return NotImplemented
        return self.value < other.value

    def __eq__(self, other: object) -> bool:
        """Check if equal.

        Args:
            other: other item

        Returns:
            True if equal
        """
        if not isinstance(other, ValueWithTimeout):
            return NotImplemented
        return self.value == other.value

    def __hash__(self) -> int:
        """Get hash of the ValueWithTimeout object.

        Returns:
            hash value
        """
        return hash((self.value, self.timeout, self.add_timestamp))


class TimeoutList:
    """List like class, where every item has a timeout, which will remove it from the list."""

    def __init__(self) -> None:
        """Init class."""
        self.__items: list[ValueWithTimeout] = []

    def __repr__(self) -> str:
        """Get representation of all list items (without timeout).

        Returns:
            all list elements which are currently in the list
        """
        self.__remove_old_items()
        return str([itm.value for itm in self.__items])

    def __bool__(self) -> bool:
        """Check if list has items.

        Returns:
            true if items in list
        """
        self.__remove_old_items()
        return bool(self.__items)

    def __contains__(self, item: object) -> bool:
        """Check if an item is in the list.

        Args:
            item: item which should be checked

        Returns:
            true if item is in the list
        """
        self.__remove_old_items()
        return item in [itm.value for itm in self.__items]

    def __getitem__(self, index: int) -> object:
        """Get item from list by index.

        Args:
            index: index of item position in list.

        Returns:
            item from list
        """
        self.__remove_old_items()
        return self.__items[index].value

    def __eq__(self, other: object) -> bool:
        """Check if equal.

        Args:
            other: other item

        Returns:
            true if equal
        """
        if isinstance(other, TimeoutList):
            return repr(self) == repr(other)

        if isinstance(other, list):
            self.__remove_old_items()
            return [itm.value for itm in self.__items] == other

        return False

    def __hash__(self) -> int:
        """Get hash of the TimeoutList object.

        Returns:
            hash value
        """
        return hash(tuple(itm.value for itm in self.__items))

    def __iter__(self) -> Iterator[Any]:
        """Get an iterator for the items in the list.

        The iterator yields the values of the items in the list.

        Returns:
            iterator for the items in the list
        """
        self.__remove_old_items()
        return (itm.value for itm in self.__items)

    def __remove_old_items(self) -> None:
        """Remove items from list, which are timed-out."""
        current_time = time.time()
        self.__items = [itm for itm in self.__items if current_time - itm.add_timestamp < itm.timeout]

    def append(self, item: object, timeout: float) -> None:
        """Add item to list.

        Args:
            item: item which should be added to the list
            timeout: timeout, after which the item is not valid anymore
        """
        self.__items.append(ValueWithTimeout(item, timeout, time.time()))

    def remove(self, item: object) -> None:
        """Remove item from list. If there are duplicates. The first element will be removed.

        Args:
            item: item which should be deleted

        Raises:
            ValueError: if item not in list
        """
        item_to_remove = next((itm for itm in self.__items if itm.value == item), None)

        if not item_to_remove:
            msg = f"{self.__class__.__name__}.remove(x): x not in list"
            raise ValueError(msg)

        self.__items.remove(item_to_remove)

    def pop(self, element_index: int) -> object:
        """Pop item from list.

        Args:
            element_index: list index of element which should be deleted

        Returns:
            item which was removed

        Raises:
            IndexError: if index is out of range
            TypeError: if index can not be interpreted as integer
        """
        return self.__items.pop(element_index).value
