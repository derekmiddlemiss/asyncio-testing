import asyncio
import logging
from typing import Optional, Tuple

# Create a module-level logger
logger = logging.getLogger(__name__)


async def run_in_subprocess(
    command: str, termination_timeout: float = 3.0
) -> Tuple[str, str, Optional[int]]:
    """
    Run a command in a subprocess using asyncio.

    Args:
        command: The shell command to execute
        termination_timeout: Timeout in seconds to wait for process termination after cancellation

    Returns:
        A tuple containing (stdout, stderr, exit_code)

    Handles asyncio.CancelledError by attempting to gracefully terminate
    the process, waiting for termination_timeout seconds, and then killing it if necessary.
    Also handles cancellation during process creation.
    """
    process = None
    try:
        process = await asyncio.create_subprocess_shell(
            command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()
        # Handle potential decoding errors gracefully
        stdout_str = stdout.decode("utf-8", errors="replace")
        stderr_str = stderr.decode("utf-8", errors="replace")
        return stdout_str, stderr_str, process.returncode
    except asyncio.CancelledError:
        logger.error(
            f"Process running command '{command}' was cancelled, attempting graceful termination"
        )

        if process is None:
            logger.error("Process was cancelled before it could be created")
            raise

        if process.returncode is not None:
            logger.info(
                f"Process already completed with return code {process.returncode}"
            )
            raise

        # Try to terminate gracefully
        process.terminate()

        try:
            # Wait for the specified timeout for the process to terminate
            await asyncio.wait_for(process.wait(), timeout=termination_timeout)
        except asyncio.TimeoutError:
            logger.error("Process did not terminate gracefully, killing it")
            process.kill()

        # Re-raise the CancelledError to propagate it
        raise
