"""Config models for monthly energy report."""

import HABApp
import multi_notifier.connectors.connector_mail
import pydantic

import habapp_rules.core.pydantic_base


class EnergyShare(pydantic.BaseModel):
    """Dataclass for defining energy share objects."""

    model_config = pydantic.ConfigDict(arbitrary_types_allowed=True)

    energy_item: HABApp.openhab.items.NumberItem
    chart_name: str
    monthly_power: float = 0.0

    def __init__(self, energy_item: str | HABApp.openhab.items.NumberItem, chart_name: str, monthly_power: float = 0.0):
        """Init energy share object without keywords.

        :param energy_item: name or item of energy
        :param chart_name: name which will be shown in the chart
        :param monthly_power: monthly power of this energy share. This will be set by the energy share rule.
        """
        super().__init__(energy_item=energy_item, chart_name=chart_name, monthly_power=monthly_power)

    @pydantic.field_validator("energy_item", mode="before")
    @classmethod
    def check_oh_item(cls, data: str | HABApp.openhab.items.NumberItem) -> HABApp.openhab.items.NumberItem:
        """Check if given item is an OpenHAB item or try to get it from OpenHAB.

        :param data: configuration for energy item
        :return: energy item
        :raises ValueError: if item could not be found
        """
        if isinstance(data, HABApp.openhab.items.NumberItem):
            return data
        try:
            return HABApp.openhab.items.NumberItem.get_item(data)
        except HABApp.core.errors.ItemNotFoundException:
            raise ValueError(f"Could not find any item for given name '{data}'")


class MonthlyReportItems(habapp_rules.core.pydantic_base.ItemBase):
    """Items for monthly report."""

    energy_sum: HABApp.openhab.items.NumberItem = pydantic.Field(..., description="item which holds the total energy consumption")


class MonthlyReportParameter(habapp_rules.core.pydantic_base.ParameterBase):
    """Parameter for monthly report."""

    known_energy_shares: list[EnergyShare] = pydantic.Field([], description="list of EnergyShare objects which hold the known energy shares. E.g. energy for lights or ventilation")
    persistence_group_name: str | None = pydantic.Field(None, description="OpenHAB group name which holds all items which are persisted. If the group name is given it will be checked if all energy items are in the group")
    config_mail: multi_notifier.connectors.connector_mail.MailConfig = pydantic.Field(..., description="config for sending mails")
    recipients: list[str] = pydantic.Field(..., description="list of recipients who get the mail")
    debug: bool = pydantic.Field(False, description="if debug mode is active")


class MonthlyReportConfig(habapp_rules.core.pydantic_base.ConfigBase):
    """Config for monthly report."""

    items: MonthlyReportItems = pydantic.Field(..., description="Items for monthly report")
    parameter: MonthlyReportParameter = pydantic.Field(..., description="Parameter for monthly report")
