"""Helper for testing transitions."""

import unittest.mock


def call_timeout(mock_object: unittest.mock.MagicMock) -> None:
    """Helper to simulate timeout of timer.

    Args:
        mock_object: mock object of transitions.extensions.states.Timer
    """
    timer_func = mock_object.call_args.args[1]
    timer_args = mock_object.call_args.kwargs.get("args", {})
    timer_func(*timer_args)
