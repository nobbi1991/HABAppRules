import HABApp
import pydantic

import habapp_rules.core.pydantic_base


class ExampleItems(habapp_rules.core.pydantic_base.ItemBase):
	"""Example items for testing."""
	test_switch: HABApp.openhab.items.SwitchItem
	test_number: HABApp.openhab.items.NumberItem | None = pydantic.Field(None, json_schema_extra={"create_if_not_exists": True})
	test_state: habapp_rules.core.pydantic_base.AdditionalItem


class ExampleConfig(habapp_rules.core.pydantic_base.ConfigBase):
	"""Example config for testing."""
	items: ExampleItems


bla = ExampleItems(
	test_switch="name_of_test_switch",
	test_number="name_of_test_number",
	test_state=habapp_rules.core.pydantic_base.AdditionalItem(type=habapp_rules.core.pydantic_base.ItemTypes.number, name="test_state", groups=["bla"])
)
# bla = ExampleItems(test_switch="name_of_test_switch")

print(bla.test_switch.__repr__())
print(bla.test_number.__repr__())

json_config = {
	"items":
		{
			"test_switch": "json_test_switch",
			"test_number": "json_test_number",
			"test_state": {
				"type": "number",
				"name": "test_state",
				"groups": ["persist"]
			}
		}
}

result = ExampleConfig.model_validate(json_config)
bla = 2


