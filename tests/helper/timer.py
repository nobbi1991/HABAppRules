"""Helper for testing transitions."""
import unittest.mock


def call_timeout(mock_object: unittest.mock.MagicMock) -> None:
    """Call a mocked timeout during unit test.

    :param mock_object: mock object of transitions.extensions.states.Timer
    """
    timer_func = mock_object.call_args.args[1]
    timer_args = mock_object.call_args.kwargs.get("args", {})
    timer_func(*timer_args)
