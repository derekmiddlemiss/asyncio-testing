import pytest
import asyncio
import logging
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
    mock_log_error = mocker.patch('src.shell.run_in_subprocess.logger.error')

    # Cancel the task
    task.cancel()

    # Verify the task was cancelled
    with pytest.raises(asyncio.CancelledError):
        await task

    # Verify logging was called with the expected message
    mock_log_error.assert_any_call(f"Process running command '{command}' was cancelled, attempting graceful termination")


@pytest.mark.asyncio
async def test_run_in_subprocess_cancellation_during_creation(mocker):
    """Test that run_in_subprocess correctly handles task cancellation during process creation."""
    command = "echo 'This will never run'"

    # Create a delayed version of create_subprocess_shell that will raise CancelledError
    async def delayed_create_subprocess_shell(*args, **kwargs):
        # Simulate the function being cancelled during process creation
        raise asyncio.CancelledError()

    # Mock the logger to verify it's called
    mock_log_error = mocker.patch('src.shell.run_in_subprocess.logger.error')

    # Patch the create_subprocess_shell function to use our delayed version
    mocker.patch('asyncio.create_subprocess_shell', delayed_create_subprocess_shell)

    # Verify the task is cancelled
    with pytest.raises(asyncio.CancelledError):
        await run_in_subprocess(command)

    # Verify logging was called with the expected message
    mock_log_error.assert_any_call(f"Process running command '{command}' was cancelled, attempting graceful termination")
    # We don't expect the "Process was cancelled before it could be created" message
    # because the process variable is never assigned, so the check for None is never reached
