import unittest.mock


def call_timeout(mock_object: unittest.mock.MagicMock) -> None:  # todo rename/remove, this is also working for threading.Timer
    """Helper to simulate timeout of timer.

    :param mock_object: mock object of transitions.extensions.states.Timer
    :return:
    """
    timer_func = mock_object.call_args.args[1]
    timer_args = mock_object.call_args.kwargs.get("args", {})
    timer_func(*timer_args)
