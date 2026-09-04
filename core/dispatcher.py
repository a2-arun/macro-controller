"""Key dispatch — the piece that was missing.

Before this module, `ActionHandler.execute_macro` was never called from
anywhere: `toggle_macro_mode` flipped a boolean and recoloured a label, and
`self.keyboard_listener` was assigned None and never assigned again. The
application could not run a macro. This is that missing half.

Design notes, because two of these are safety-critical:

1.  *One-shot arming.* Entering macro mode captures exactly one key, fires the
    matching macro, and disarms. A persistent mode that swallows every
    keystroke is hostile: the user's keyboard stops working and the only way
    out is the hotkey they may have just forgotten.

2.  *Watchdog timeout.* The listener runs with suppress=True, which means
    keystrokes do not reach the focused application. If anything goes wrong
    while armed, the user has effectively lost their keyboard. A hard timeout
    guarantees the capture always ends, even if the UI thread is wedged.

3.  *Thread affinity.* pynput callbacks arrive on the listener's own thread.
    Nothing here touches Tk directly; state changes are reported through a
    callback that the UI is responsible for marshalling onto its main thread.
"""

from __future__ import annotations

import logging
import threading
from typing import Callable, Optional

from pynput import keyboard

logger = logging.getLogger(__name__)

# Hard ceiling on how long the keyboard can be captured.
ARM_TIMEOUT_SECONDS = 5.0


class MacroDispatcher:
    """Captures a single keypress while armed and resolves it to a macro.

    Parameters
    ----------
    resolve:
        Given a key label, return the macro's action list, or None if no macro
        is bound to that key.
    execute:
        Run an action list. Called on a worker thread, never the UI thread.
    on_state_change:
        Notified with (armed: bool, reason: str) whenever arming state changes.
        Called from a background thread -- the UI must marshal it.
    """

    def __init__(
        self,
        resolve: Callable[[str], Optional[list]],
        execute: Callable[[list], None],
        on_state_change: Callable[[bool, str], None],
    ) -> None:
        self._resolve = resolve
        self._execute = execute
        self._on_state_change = on_state_change

        self._lock = threading.RLock()
        self._listener: Optional[keyboard.Listener] = None
        self._timer: Optional[threading.Timer] = None

    # ------------------------------------------------------------------ state

    @property
    def is_armed(self) -> bool:
        with self._lock:
            return self._listener is not None

    def toggle(self) -> None:
        if self.is_armed:
            self.disarm("toggled off")
        else:
            self.arm()

    # ------------------------------------------------------------------- arming

    def arm(self) -> None:
        """Begin capturing the next keystroke."""
        with self._lock:
            if self._listener is not None:
                return

            try:
                self._listener = keyboard.Listener(
                    on_press=self._on_press, suppress=True
                )
                self._listener.start()
            except Exception:
                # Starting a global hook can fail (permissions, another hook
                # holding the slot). Fail loudly but leave the keyboard alone.
                logger.exception("could not start the key listener")
                self._listener = None
                self._notify(False, "listener failed to start")
                return

            self._timer = threading.Timer(ARM_TIMEOUT_SECONDS, self._on_timeout)
            self._timer.daemon = True
            self._timer.start()

        logger.info("macro mode armed")
        self._notify(True, "armed")

    def disarm(self, reason: str = "disarmed") -> None:
        """Stop capturing. Safe to call repeatedly and from any thread."""
        with self._lock:
            timer, self._timer = self._timer, None
            listener, self._listener = self._listener, None

        if timer is not None:
            timer.cancel()

        if listener is not None:
            try:
                listener.stop()
            except Exception:
                logger.exception("error stopping the key listener")

        logger.info("macro mode disarmed (%s)", reason)
        self._notify(False, reason)

    def shutdown(self) -> None:
        """Release the keyboard on application exit."""
        self.disarm("shutting down")

    # ---------------------------------------------------------------- internals

    def _on_timeout(self) -> None:
        logger.info("arm window expired after %.1fs", ARM_TIMEOUT_SECONDS)
        self.disarm("timed out")

    def _on_press(self, key) -> bool:
        """Handle one suppressed keystroke. Returning False stops the listener."""
        label = self._key_label(key)

        # Escape is always an unconditional way out.
        if key == keyboard.Key.esc:
            self._defer_disarm("cancelled")
            return False

        if label is None:
            # A bare modifier: stay armed and wait for a real key, rather than
            # burning the one-shot on Shift.
            return True

        actions = None
        try:
            actions = self._resolve(label)
        except Exception:
            logger.exception("failed to resolve macro for key %r", label)

        if actions:
            logger.info("firing macro %r (%d actions)", label, len(actions))
            worker = threading.Thread(
                target=self._run_macro,
                args=(label, list(actions)),
                daemon=True,
                name=f"macro-{label}",
            )
            worker.start()
            self._defer_disarm(f"fired {label!r}")
        else:
            logger.info("no macro bound to key %r", label)
            self._defer_disarm(f"no macro for {label!r}")

        return False

    def _run_macro(self, label: str, actions: list) -> None:
        try:
            self._execute(actions)
        except Exception:
            logger.exception("macro %r failed", label)

    def _defer_disarm(self, reason: str) -> None:
        """Tear down off the callback thread.

        Calling listener.stop() from inside its own callback can deadlock on
        some backends, so hand the teardown to a short-lived thread.
        """
        threading.Thread(
            target=self.disarm, args=(reason,), daemon=True, name="disarm"
        ).start()

    def _notify(self, armed: bool, reason: str) -> None:
        try:
            self._on_state_change(armed, reason)
        except Exception:
            logger.exception("state-change callback raised")

    @staticmethod
    def _key_label(key) -> Optional[str]:
        """Normalise a pynput key into the string used as a macro binding.

        Returns None for keys that should not consume the one-shot window
        (bare modifiers).
        """
        modifiers = {
            keyboard.Key.shift, keyboard.Key.shift_r, keyboard.Key.shift_l,
            keyboard.Key.ctrl, keyboard.Key.ctrl_r, keyboard.Key.ctrl_l,
            keyboard.Key.alt, keyboard.Key.alt_r, keyboard.Key.alt_l,
            keyboard.Key.cmd, keyboard.Key.cmd_r, keyboard.Key.cmd_l,
        }
        if key in modifiers:
            return None

        char = getattr(key, "char", None)
        if char:
            return char.lower()

        name = getattr(key, "name", None)
        if name:
            return f"<{name}>"

        return None
