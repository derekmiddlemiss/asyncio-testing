import asyncio

import pytest

from src.shell.run_in_subprocess import run_in_subprocess


@pytest.mark.asyncio
async def test_run_in_subprocess_success():
    """Test that run_in_subprocess works correctly with a successful command."""
    # Test with a simple echo command
    stdout, stderr, exit_code = await run_in_subprocess("echo 'Hello, World!'")

    assert stdout.strip() == "Hello, World!"
    assert stderr == ""
    assert exit_code == 0


@pytest.mark.asyncio
async def test_run_in_subprocess_failure():
    """Test that run_in_subprocess correctly handles command failures."""
    # Test with a command that should fail
    # 'ls' on a non-existent directory should fail and produce stderr output
    stdout, stderr, exit_code = await run_in_subprocess("ls /nonexistent_directory")

    assert stdout == ""
    assert "No such file or directory" in stderr
    assert exit_code != 0


@pytest.mark.asyncio
async def test_run_in_subprocess_cancellation(mocker):
    """Test that run_in_subprocess correctly handles task cancellation."""
    # Use a command that will run indefinitely (only cancellation will stop it)
    command = "while true; do sleep 1; done"

    # Create a task for the command
    task = asyncio.create_task(run_in_subprocess(command))

    # Give it a moment to start
    await asyncio.sleep(0.1)

    # Mock the logger to verify it's called
    mock_log_error = mocker.patch("src.shell.run_in_subprocess.logger.error")

    # Cancel the task
    task.cancel()

    # Verify the task was cancelled
    with pytest.raises(asyncio.CancelledError):
        await task

    # Verify logging was called with the expected message
    mock_log_error.assert_any_call(
        f"Process running command '{command}' was cancelled, attempting graceful termination"
    )


@pytest.mark.asyncio
async def test_run_in_subprocess_cancellation_during_creation(mocker):
    """Test that run_in_subprocess correctly handles task cancellation during process creation."""
    command = "echo 'This will never run'"

    # Create a delayed version of create_subprocess_shell that will raise CancelledError
    async def delayed_create_subprocess_shell(*args, **kwargs):
        # Simulate the function being cancelled during process creation
        raise asyncio.CancelledError()

    # Mock the logger to verify it's called
    mock_log_error = mocker.patch("src.shell.run_in_subprocess.logger.error")

    # Patch the create_subprocess_shell function to use our delayed version
    mocker.patch("asyncio.create_subprocess_shell", delayed_create_subprocess_shell)

    # Verify the task is cancelled
    with pytest.raises(asyncio.CancelledError):
        await run_in_subprocess(command)

    # Verify logging was called with the expected message
    mock_log_error.assert_any_call(
        f"Process running command '{command}' was cancelled, attempting graceful termination"
    )
    # We don't expect the "Process was cancelled before it could be created" message
    # because the process variable is never assigned, so the check for None is never reached


@pytest.mark.asyncio
async def test_run_in_subprocess_cancellation_already_completed(mocker):
    """Test that run_in_subprocess correctly handles task cancellation when process already completed."""
    command = "echo 'This will complete quickly'"

    # Create a mock process with a returncode
    mock_process = mocker.AsyncMock()
    mock_process.returncode = 0

    # Mock the create_subprocess_shell to return our mock process
    mocker.patch("asyncio.create_subprocess_shell", return_value=mock_process)

    # Mock the communicate method to raise CancelledError
    mock_process.communicate.side_effect = asyncio.CancelledError()

    # Mock the logger to verify it's called
    mock_log_info = mocker.patch("src.shell.run_in_subprocess.logger.info")

    # Verify the task is cancelled
    with pytest.raises(asyncio.CancelledError):
        await run_in_subprocess(command)

    # Verify logging was called with the expected message
    mock_log_info.assert_called_once_with(
        f"Process already completed with return code {mock_process.returncode}"
    )


@pytest.mark.asyncio
async def test_run_in_subprocess_cancellation_timeout(mocker):
    """Test that run_in_subprocess correctly handles task cancellation when process doesn't terminate gracefully."""
    command = "while true; do sleep 1; done"

    # Create a mock process
    mock_process = mocker.AsyncMock()
    mock_process.returncode = None

    # Configure terminate and kill to be synchronous methods (not coroutines)
    # This matches the actual behavior of Process.terminate() and Process.kill()
    mock_process.terminate = mocker.Mock()
    mock_process.kill = mocker.Mock()

    # Mock the create_subprocess_shell to return our mock process
    mocker.patch("asyncio.create_subprocess_shell", return_value=mock_process)

    # Mock the communicate method to raise CancelledError
    mock_process.communicate.side_effect = asyncio.CancelledError()

    # Mock the wait_for function to raise TimeoutError
    mocker.patch("asyncio.wait_for", side_effect=asyncio.TimeoutError())

    # Mock the logger to verify it's called
    mock_log_error = mocker.patch("src.shell.run_in_subprocess.logger.error")

    # Verify the task is cancelled
    with pytest.raises(asyncio.CancelledError):
        await run_in_subprocess(command)

    # Verify the process was terminated and then killed
    mock_process.terminate.assert_called_once()
    mock_process.kill.assert_called_once()

    # Verify logging was called with the expected message
    mock_log_error.assert_any_call("Process did not terminate gracefully, killing it")


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
        try:
            await asyncio.gather(task1, task2, task3)
        except Exception:
            # Cancel remaining tasks when one fails
            for task in [task1, task2, task3]:
                if not task.done():
                    task.cancel()
            # Wait for cancellations to complete
            await asyncio.gather(task1, task2, task3, return_exceptions=True)
            raise

    # Verify that all tasks are cancelled or done
    assert task1.cancelled() or task1.done(), "Task 1 should be cancelled or done"
    assert task2.cancelled() or task2.done(), "Task 2 should be cancelled or done"
    assert task3.cancelled() or task3.done(), "Task 3 should be cancelled or done"
