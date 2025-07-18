import asyncio
import logging
from typing import Tuple


# Create a module-level logger
logger = logging.getLogger(__name__)


async def run_in_subprocess(command: str) -> Tuple[str, str, int]:
    """
    Run a command in a subprocess using asyncio.

    Args:
        command: The shell command to execute

    Returns:
        A tuple containing (stdout, stderr, exit_code)

    Handles asyncio.CancelledError by attempting to gracefully terminate
    the process, waiting a few seconds, and then killing it if necessary.
    Also handles cancellation during process creation.
    """
    try:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        try:
            stdout, stderr = await process.communicate()
            return (
                stdout.decode('utf-8'),
                stderr.decode('utf-8'),
                process.returncode
            )
        except asyncio.CancelledError:
            logger.error(f"Process running command '{command}' was cancelled, attempting graceful termination")

            # Try to terminate gracefully
            process.terminate()

            try:
                # Wait for a few seconds for the process to terminate
                await asyncio.wait_for(process.wait(), timeout=3.0)
            except asyncio.TimeoutError:
                logger.error(f"Process did not terminate gracefully, killing it")
                process.kill()

            # Re-raise the CancelledError to propagate it
            raise
    except asyncio.CancelledError:
        # This handles cancellation during process creation
        logger.error(f"Process running command '{command}' was cancelled, attempting graceful termination")
        logger.error(f"Process was cancelled before it could be created")

        # Re-raise the CancelledError to propagate it
        raise
