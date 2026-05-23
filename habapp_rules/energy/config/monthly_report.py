"""Config models for monthly energy report."""

import datetime
import pathlib

import multi_notifier.connectors.connector_mail
import pydantic
from HABApp.core.errors import ItemNotFoundException, WrongItemTypeError
from HABApp.openhab.items import NumberItem, OpenhabItem

from habapp_rules.core.pydantic_base import BaseModel, ConfigBase, ItemBase, ParameterBase
from habapp_rules.energy.helper import get_historic_value


def _calc_difference(start_value: float, end_value: float) -> float:
    """Calculate the difference between start and end value and return zero if start value is greater than end value.

    Args:
        start_value: energy value at the start of the month
        end_value: energy value at the end of the month

    Returns:
        difference between start and end value and zero if start value is greater than end value
    """
    return max(0.0, start_value - end_value)


class EnergyShare(BaseModel):
    """Dataclass for defining energy share objects."""

    model_config = pydantic.ConfigDict(arbitrary_types_allowed=True)

    energy_item: NumberItem | list[NumberItem]
    chart_name: str
    monthly_power: float = 0.0

    def __init__(self, energy_item: str | NumberItem | list[NumberItem] | list[str], chart_name: str, monthly_power: float = 0.0) -> None:
        """Init energy share object without keywords.

        Args:
            energy_item: name or item of energy
            chart_name: name which will be shown in the chart
            monthly_power: monthly power of this energy share. This will be set by the energy share rule.
        """
        super().__init__(energy_item=energy_item, chart_name=chart_name, monthly_power=monthly_power)

    @staticmethod
    def _get_number_item_by_name(name: str) -> NumberItem:
        try:
            return NumberItem.get_item(name)
        except WrongItemTypeError as exc:
            msg = f"Item must be of type NumberItem. Given: {type(OpenhabItem.get_item(name))}"
            raise ValueError(msg) from exc
        except ItemNotFoundException as exc:
            msg = f"Could not find any item for given name '{name}'"
            raise ValueError(msg) from exc

    @pydantic.field_validator("energy_item", mode="before")
    @classmethod
    def check_oh_item(cls, data: str | NumberItem) -> NumberItem | list[NumberItem]:
        """Check if given item is an OpenHAB item or try to get it from OpenHAB.

        Args:
            data: configuration for energy item

        Returns:
            energy item

        Raises:
            ValueError: if item could not be found
        """
        if isinstance(data, NumberItem):
            return data
        if isinstance(data, list):
            if all(isinstance(itm, NumberItem) for itm in data):
                return data
            return [cls._get_number_item_by_name(itm) for itm in data]
        return cls._get_number_item_by_name(data)

    def get_energy_since(self, start_time: datetime.datetime) -> float:
        """Get energy since start time.

        Args:
            start_time: start time to search for the interested value

        Returns:
            energy since start time
        """
        if isinstance(self.energy_item, list):
            return sum(_calc_difference(itm.value, get_historic_value(itm, start_time, 0)) for itm in self.energy_item)
        return _calc_difference(self.energy_item.value, get_historic_value(self.energy_item, start_time, 0))

    @property
    def get_items_as_list(self) -> list[NumberItem]:
        """Get energy item(s) as list.

        Returns:
            All energy items
        """
        if isinstance(self.energy_item, list):
            return self.energy_item
        return [self.energy_item]


class MonthlyReportItems(ItemBase):
    """Items for monthly report."""

    energy_sum: NumberItem = pydantic.Field(..., description="item which holds the total energy consumption")


class MonthlyReportParameter(ParameterBase):
    """Parameter for monthly report."""

    known_energy_shares: list[EnergyShare] = pydantic.Field(default=[], description="list of EnergyShare objects which hold the known energy shares. E.g. energy for lights or ventilation")
    persistence_group_name: str | None = pydantic.Field(default=None, description="OpenHAB group name which holds all items which are persisted. If the group name is given it will be checked if all energy items are in the group")
    config_mail: multi_notifier.connectors.connector_mail.MailConfig = pydantic.Field(..., description="config for sending mails")
    recipients: list[str] = pydantic.Field(..., description="list of recipients who get the mail")
    debug: bool = pydantic.Field(default=False, description="if debug mode is active")
    history_months: int = pydantic.Field(default=12, ge=0, description="Number of past completed months to show in the history bar chart; 0 disables the feature")
    history_cache_path: pathlib.Path | None = pydantic.Field(default=None, description="Path to a JSON file used to cache monthly energy boundary values; None disables caching")  # todo save file next to rule file if set to None, or global cache path? or only path and generate name?


class MonthlyReportConfig(ConfigBase):
    """Config for monthly report."""

    items: MonthlyReportItems = pydantic.Field(..., description="Items for monthly report")
    parameter: MonthlyReportParameter = pydantic.Field(..., description="Parameter for monthly report")
