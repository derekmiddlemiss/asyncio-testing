import asyncio
from typing import Any, Generic, List, Sequence, TypeVar, Union

T = TypeVar("T")


async def run_tasks_in_cancellation_group(tasks: List[asyncio.Task]) -> None:
    try:
        await asyncio.gather(*tasks, return_exceptions=False)
    except Exception:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise


async def run_tasks_in_cancellation_group_with_results(
    tasks: List[asyncio.Task[T]],
) -> List[Union[T, BaseException]]:
    """
    Run a list of tasks and return their results.
    If any task raises an exception, all remaining tasks are cancelled,
    and the original exception is re-raised.

    Args:
        tasks: A list of asyncio.Task objects to run

    Returns:
        A list containing the results of all tasks in the same order as the input tasks

    Raises:
        Exception: If any task raises an exception, it is re-raised after cancelling all other tasks
    """
    try:
        results: List[Union[T, BaseException]] = await asyncio.gather(
            *tasks, return_exceptions=False
        )
        return results
    except Exception:
        for task in tasks:
            if not task.done():
                task.cancel()
        # We need return_exceptions=True here to prevent CancelledError from being raised
        # when we're trying to clean up after another exception
        exc_results: List[Union[T, BaseException]] = await asyncio.gather(
            *tasks, return_exceptions=True
        )
        return exc_results
