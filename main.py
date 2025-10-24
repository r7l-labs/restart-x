from __future__ import annotations

import threading
import time
import os
from typing import Any, Optional


class SimpleLogger:
    def __init__(self, prefix: str = "AutoRestart"):
        self.prefix = prefix

    def _log(self, level: str, *parts: object) -> None:
        msg = " ".join(str(p) for p in parts)
        print(f"[{self.prefix}] [{level}] {msg}")

    def info(self, *parts: object) -> None:
        self._log("INFO", *parts)

    def warning(self, *parts: object) -> None:
        self._log("WARN", *parts)

    def error(self, *parts: object) -> None:
        self._log("ERROR", *parts)

    def exception(self, *parts: object) -> None:
        # keep simple: print parts; in real environment, server.logger.exception preferred
        self._log("EXC", *parts)


class AutoRestartPlugin:
    """Single-file plugin that restarts the server at a configured interval.

    Behavior/contract:
    - on_enable(server): start a repeating timer that issues a restart command every interval.
    - on_disable(): cancel timer.

    Configuration sources (checked in order):
    - environment variable `AUTORESTART_INTERVAL_SECONDS`
    - server-provided config: `get_config()` or `config` attribute (best-effort)
    - default: 6 hours
    """

    DEFAULT_SECONDS = 6 * 60 * 60

    def __init__(self):
        self.server: Optional[Any] = None
        self.logger: Optional[Any] = None
        self.interval_seconds: int = self.DEFAULT_SECONDS
        self._timer: Optional[threading.Timer] = None
        self._stopped = True

    # ------- plugin lifecycle expected by pyspigot --------
    def on_enable(self, server: Any) -> None:
        """Called by pyspigot when plugin is enabled. `server` is the host server object."""
        self.server = server
        self.logger = getattr(server, "logger", None) or SimpleLogger()

        # try to load configuration
        self._load_config()

        self._stopped = False
        self.logger.info(f"AutoRestart enabled. Interval: {self.interval_seconds} seconds")
        self._schedule_restart()

    def on_disable(self) -> None:
        """Called by pyspigot when plugin is disabled."""
        self._stopped = True
        if self._timer:
            self._timer.cancel()
            self._timer = None
        if self.logger:
            self.logger.info("AutoRestart disabled; timer cancelled")

    # ------- internal helpers --------
    def _load_config(self) -> None:
        # 1) Environment variable override
        env = os.getenv("AUTORESTART_INTERVAL_SECONDS")
        if env:
            try:
                self.interval_seconds = int(env)
                self.logger.info("Interval loaded from env AUTORESTART_INTERVAL_SECONDS")
                return
            except Exception:
                self.logger.warning("Invalid AUTORESTART_INTERVAL_SECONDS; ignoring")

        # 2) Try to read server config (best-effort)
        try:
            cfg = None
            if hasattr(self.server, "get_config") and callable(self.server.get_config):
                cfg = self.server.get_config()
            elif hasattr(self.server, "config"):
                cfg = getattr(self.server, "config")

            if cfg:
                # support either seconds or hours as keys
                if isinstance(cfg, dict):
                    if "autorestart_interval_seconds" in cfg:
                        self.interval_seconds = int(cfg["autorestart_interval_seconds"])
                        self.logger.info("Interval loaded from server config: seconds")
                        return
                    if "autorestart_interval_hours" in cfg:
                        self.interval_seconds = int(cfg["autorestart_interval_hours"]) * 3600
                        self.logger.info("Interval loaded from server config: hours")
                        return
        except Exception as e:
            # non-fatal; keep default
            if self.logger:
                self.logger.warning("Failed to read server config for AutoRestart:", e)

        # default remains

    def _schedule_restart(self) -> None:
        if self._stopped:
            return
        # cancel existing timer if any
        if self._timer:
            try:
                self._timer.cancel()
            except Exception:
                pass
        self._timer = threading.Timer(self.interval_seconds, self._do_restart)
        # won't block shutdown of host process
        self._timer.daemon = True
        self._timer.start()
        if self.logger:
            self.logger.info(f"Next restart scheduled in {self.interval_seconds} seconds")

    def _do_restart(self) -> None:
        """Issue the restart command using the best-guess server API, then reschedule."""
        if self._stopped:
            return

        try:
            issued = False
            # find a callable command issuer on the server
            if self.server is not None:
                # common API names tried in order
                for name in ("dispatch_command", "execute_command", "console_command", "run_command"):
                    cmd = getattr(self.server, name, None)
                    if callable(cmd):
                        try:
                            cmd("restart")
                            issued = True
                            self.logger.info(f"Issued restart via {name}(\"restart\")")
                            break
                        except TypeError:
                            # some call signatures may differ; try with server as first arg
                            try:
                                cmd(self.server, "restart")
                                issued = True
                                self.logger.info(f"Issued restart via {name}(server, \"restart\")")
                                break
                            except Exception:
                                pass

                # fallback to stop/shutdown
                if not issued:
                    for name in ("shutdown", "stop"):
                        fn = getattr(self.server, name, None)
                        if callable(fn):
                            try:
                                fn()
                                issued = True
                                self.logger.info(f"Called server.{name}() as fallback restart")
                                break
                            except Exception:
                                pass

            if not issued:
                self.logger.warning("Could not find a supported API to issue restart; no action taken")

        except Exception as e:
            if self.logger:
                self.logger.exception("Exception while trying to restart:", e)
        finally:
            # schedule next run unless disabled
            self._schedule_restart()


# ------------------ optional quick test harness ------------------
if __name__ == "__main__":
    # Simulate a server object for local testing
    class DummyServer:
        def __init__(self):
            self.logger = SimpleLogger(prefix="DummyServer")
            self.commands = []

        def dispatch_command(self, cmd: str) -> None:
            self.logger.info("dispatch_command received:", cmd)
            self.commands.append(cmd)

        def get_config(self):
            # test shorter interval for demo
            return {"autorestart_interval_seconds": 5}

    print("Starting AutoRestartPlugin test harness (will schedule a restart in 5s)...")
    plugin = AutoRestartPlugin()
    server = DummyServer()
    plugin.on_enable(server)

    # run a short loop to let timers fire
    try:
        time.sleep(12)
    except KeyboardInterrupt:
        pass
    plugin.on_disable()
    print("Test harness complete. Commands issued:", server.commands)
