import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

T = TypeVar("T")


def call_async_sync(async_func: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any) -> T:
    """Call an async function from synchronous code.

    Args:
        async_func: The async function to call
        *args: Arguments to pass to the async function
        **kwargs: Key word arguments to pass to the async function

    Returns:
        The result of the async function
    """
    loop = asyncio.get_event_loop()
    if loop.is_running():
        # If there's already a running event loop, we need to create a new one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(async_func(*args, **kwargs))
        finally:
            loop.close()
    else:
        # Use the existing event loop
        return loop.run_until_complete(async_func(*args, **kwargs))
