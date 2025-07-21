import asyncio
from collections import Counter
from itertools import count
from unittest.mock import AsyncMock

import pytest

from src.shell.run_in_subprocess import run_in_subprocess
from src.shell.run_tasks_in_cancellation_group import (
    run_tasks_in_cancellation_group,
    run_tasks_in_cancellation_group_with_results,
)


@pytest.mark.asyncio
async def test_run_tasks_in_cancellation_group_happy_path():
    """Test that run_tasks_in_cancellation_group successfully completes when all tasks succeed."""

    # Create mock tasks that will complete successfully
    async def successful_task():
        await asyncio.sleep(0.1)
        return "success"

    task1 = asyncio.create_task(successful_task())
    task2 = asyncio.create_task(successful_task())
    task3 = asyncio.create_task(successful_task())

    # Run the tasks in a cancellation group
    await run_tasks_in_cancellation_group([task1, task2, task3])

    # Verify all tasks completed successfully
    assert (
        task1.done() and not task1.cancelled()
    ), "Task 1 should be done and not cancelled"
    assert (
        task2.done() and not task2.cancelled()
    ), "Task 2 should be done and not cancelled"
    assert (
        task3.done() and not task3.cancelled()
    ), "Task 3 should be done and not cancelled"

    # Verify the results
    assert task1.result() == "success"
    assert task2.result() == "success"
    assert task3.result() == "success"


@pytest.mark.asyncio
async def test_run_tasks_in_cancellation_group_empty_list():
    """Test that run_tasks_in_cancellation_group handles an empty task list gracefully."""
    # This should complete without any errors
    await run_tasks_in_cancellation_group([])


@pytest.mark.asyncio
async def test_run_tasks_in_cancellation_group_mixed_durations():
    """Test that run_tasks_in_cancellation_group works with tasks of different durations."""

    # Create tasks with different durations
    async def short_task():
        await asyncio.sleep(0.1)
        return "short"

    async def medium_task():
        await asyncio.sleep(0.2)
        return "medium"

    async def long_task():
        await asyncio.sleep(0.3)
        return "long"

    task1 = asyncio.create_task(short_task())
    task2 = asyncio.create_task(medium_task())
    task3 = asyncio.create_task(long_task())

    # Run the tasks in a cancellation group
    await run_tasks_in_cancellation_group([task1, task2, task3])

    # Verify all tasks completed successfully
    assert (
        task1.done() and not task1.cancelled()
    ), "Task 1 should be done and not cancelled"
    assert (
        task2.done() and not task2.cancelled()
    ), "Task 2 should be done and not cancelled"
    assert (
        task3.done() and not task3.cancelled()
    ), "Task 3 should be done and not cancelled"

    # Verify the results
    assert task1.result() == "short"
    assert task2.result() == "medium"
    assert task3.result() == "long"


@pytest.mark.asyncio
async def test_run_tasks_in_cancellation_group_with_results_happy_path():
    """Test that run_tasks_in_cancellation_group_with_results successfully returns results when all tasks succeed."""

    # Create mock tasks that will complete successfully
    async def successful_task():
        await asyncio.sleep(0.1)
        return "success"

    task1 = asyncio.create_task(successful_task())
    task2 = asyncio.create_task(successful_task())
    task3 = asyncio.create_task(successful_task())

    # Run the tasks in a cancellation group and get results
    results = await run_tasks_in_cancellation_group_with_results([task1, task2, task3])

    # Verify all tasks completed successfully
    assert (
        task1.done() and not task1.cancelled()
    ), "Task 1 should be done and not cancelled"
    assert (
        task2.done() and not task2.cancelled()
    ), "Task 2 should be done and not cancelled"
    assert (
        task3.done() and not task3.cancelled()
    ), "Task 3 should be done and not cancelled"

    # Verify the results
    assert results == ["success", "success", "success"]


@pytest.mark.asyncio
async def test_run_tasks_in_cancellation_group_with_results_empty_list():
    """Test that run_tasks_in_cancellation_group_with_results handles an empty task list gracefully."""
    # This should complete without any errors and return an empty list
    results = await run_tasks_in_cancellation_group_with_results([])
    assert results == []


@pytest.mark.asyncio
async def test_run_tasks_in_cancellation_group_with_results_mixed_durations():
    """Test that run_tasks_in_cancellation_group_with_results works with tasks of different durations."""

    # Create tasks with different durations
    async def short_task():
        await asyncio.sleep(0.1)
        return "short"

    async def medium_task():
        await asyncio.sleep(0.2)
        return "medium"

    async def long_task():
        await asyncio.sleep(0.3)
        return "long"

    task1 = asyncio.create_task(short_task())
    task2 = asyncio.create_task(medium_task())
    task3 = asyncio.create_task(long_task())

    # Run the tasks in a cancellation group and get results
    results = await run_tasks_in_cancellation_group_with_results([task1, task2, task3])

    # Verify all tasks completed successfully
    assert (
        task1.done() and not task1.cancelled()
    ), "Task 1 should be done and not cancelled"
    assert (
        task2.done() and not task2.cancelled()
    ), "Task 2 should be done and not cancelled"
    assert (
        task3.done() and not task3.cancelled()
    ), "Task 3 should be done and not cancelled"

    # Verify the results
    assert results == ["short", "medium", "long"]


@pytest.mark.asyncio
async def test_run_tasks_in_cancellation_group_with_results_error():
    """Test that run_tasks_in_cancellation_group_with_results handles errors correctly."""

    # Create tasks, one of which will fail
    async def successful_task():
        await asyncio.sleep(0.1)
        return "success"

    async def failing_task():
        await asyncio.sleep(0.1)
        raise ValueError("Task failed")

    task1 = asyncio.create_task(successful_task())
    task2 = asyncio.create_task(failing_task())
    task3 = asyncio.create_task(successful_task())

    results = await run_tasks_in_cancellation_group_with_results([task1, task2, task3])
    counted = Counter(results)

    assert counted["success"] == 2
    assert len([result for result in results if isinstance(result, ValueError)]) == 1

    # Verify all tasks are done or cancelled
    assert task1.done(), "Task 1 should be done"
    assert task2.done(), "Task 2 should be done"
    assert task3.done(), "Task 3 should be done"


@pytest.mark.asyncio
async def test_run_in_subprocess_cancellation_propagation():
    """
    Test that in a group of run_in_subprocess() calls executed in an asyncio.gather() call,
    the cancellation of one coroutine leads to cancellation of all coroutines.
    """

    async def raise_on_non_zero_exit_code(command: str):
        stdout, stderr, exit_code = await run_in_subprocess(command)
        if exit_code != 0:
            raise RuntimeError(f"Command failed with exit code {exit_code}")

    infinite_command = "while true; do sleep 1; done"
    failing_command = "sleep 3; ls /nonexistent_directory"

    task1 = asyncio.create_task(raise_on_non_zero_exit_code(infinite_command))
    task2 = asyncio.create_task(raise_on_non_zero_exit_code(infinite_command))
    task3 = asyncio.create_task(raise_on_non_zero_exit_code(failing_command))

    with pytest.raises(RuntimeError):
        await run_tasks_in_cancellation_group([task1, task2, task3])

    # Verify that all tasks are cancelled or done
    assert task1.cancelled() or task1.done(), "Task 1 should be cancelled or done"
    assert task2.cancelled() or task2.done(), "Task 2 should be cancelled or done"
    assert task3.cancelled() or task3.done(), "Task 3 should be cancelled or done"
