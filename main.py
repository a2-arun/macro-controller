"""Entry point."""

import logging
import sys

from core.logging_setup import configure


def main() -> int:
    configure()
    logger = logging.getLogger(__name__)
    logger.info("starting Macro Controller")

    try:
        from ui.app import MacroControllerApp

        MacroControllerApp().run()
    except Exception:
        logger.exception("fatal error during startup")
        return 1

    logger.info("exited cleanly")
    return 0


if __name__ == "__main__":
    sys.exit(main())
