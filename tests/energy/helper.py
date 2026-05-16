import datetime
import unittest
import unittest.mock

import HABApp.openhab.definitions.helpers.persistence_data

from habapp_rules.energy.helper import get_historic_value


class TestHelperFunctions(unittest.TestCase):
    """Test all global functions."""

    def test_get_historic_value(self) -> None:
        """Test _get_historic_value."""
        mock_item = unittest.mock.MagicMock()
        fake_persistence_data = HABApp.openhab.definitions.helpers.persistence_data.OpenhabPersistenceData()
        mock_item.get_persistence_data.return_value = fake_persistence_data

        start_time = datetime.datetime.now()
        end_time = start_time + datetime.timedelta(hours=1)

        # no data
        self.assertEqual(0, get_historic_value(mock_item, start_time))
        mock_item.get_persistence_data.assert_called_once_with(start_time=start_time, end_time=end_time)

        # data
        fake_persistence_data.data = {"0.0": 42, "1.0": 1337}
        self.assertEqual(42, get_historic_value(mock_item, start_time))
