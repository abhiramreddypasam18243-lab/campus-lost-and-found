import asyncio
import logging
import signal
import sys
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [worker] %(message)s",
)
logger = logging.getLogger("worker")

running = True


def handle_stop(sig: int, frame: Any) -> None:
    global running
    logger.info(f"Received signal {sig}, shutting down worker cleanly...")
    running = False


async def run_worker_loop() -> None:
    """Idle worker loop for walking skeleton."""
    logger.info("Smart Campus Lost and Found worker started (walking skeleton mode).")
    while running:
        # In Step 6+, jobs will be claimed with FOR UPDATE SKIP LOCKED
        await asyncio.sleep(2)
    logger.info("Worker stopped.")


def main() -> None:
    signal.signal(signal.SIGINT, handle_stop)
    signal.signal(signal.SIGTERM, handle_stop)
    try:
        asyncio.run(run_worker_loop())
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)


if __name__ == "__main__":
    main()
