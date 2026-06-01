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

        # data in the forward window -> returns the first value, only the forward window is queried
        fake_persistence_data.data = {"0.0": 42, "1.0": 1337}
        self.assertEqual(42, get_historic_value(mock_item, start_time))
        mock_item.get_persistence_data.assert_called_once_with(start_time=start_time, end_time=end_time)

    def test_get_historic_value_backward_fallback(self) -> None:
        """Empty forward window falls back to the hour before start_time and returns the most recent value."""
        mock_item = unittest.mock.MagicMock()
        forward_data = HABApp.openhab.definitions.helpers.persistence_data.OpenhabPersistenceData()
        forward_data.data = {}
        backward_data = HABApp.openhab.definitions.helpers.persistence_data.OpenhabPersistenceData()
        backward_data.data = {"0.0": 100, "1.0": 200}
        mock_item.get_persistence_data.side_effect = [forward_data, backward_data]

        start_time = datetime.datetime.now()

        # most recent value of the backward window (last entry) is returned
        self.assertEqual(200, get_historic_value(mock_item, start_time))
        mock_item.get_persistence_data.assert_any_call(start_time=start_time - datetime.timedelta(hours=1), end_time=start_time)

    def test_get_historic_value_no_data(self) -> None:
        """No data in either window returns 0 and logs a warning."""
        mock_item = unittest.mock.MagicMock()
        empty_data = HABApp.openhab.definitions.helpers.persistence_data.OpenhabPersistenceData()
        empty_data.data = {}
        mock_item.get_persistence_data.return_value = empty_data

        with unittest.mock.patch("habapp_rules.energy.helper.LOGGER") as logger_mock:
            self.assertEqual(0, get_historic_value(mock_item, datetime.datetime.now()))
        logger_mock.warning.assert_called_once()
