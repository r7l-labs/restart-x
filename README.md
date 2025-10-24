# AutoRestart pyspigot plugin (single-file)

This repository contains a pyspigot plugin `main.py` that issues an automatic server restart on a fixed interval (default: every 6 hours).

Features
- Single-file plugin (`main.py`) compatible with typical pyspigot-style plugin lifecycles (provides `on_enable(server)` and `on_disable()`).
- Default restart interval: 6 hours (configurable).
- Tries multiple server APIs to issue a restart/stop: `dispatch_command`, `execute_command`, `console_command`, `run_command`, `shutdown`, `stop`.
- Includes a local test harness when run as a script.

Configuration
- Environment variable: `AUTORESTART_INTERVAL_SECONDS` — set the interval in seconds.
- Server config (best-effort): If your server exposes `get_config()` or a `config` mapping, the plugin looks for either `autorestart_interval_seconds` or `autorestart_interval_hours`.

Installation
1. Copy `main.py` into your pyspigot plugins folder as the plugin entry file (ensure pyspigot loads `main.py` as a plugin).
2. Optionally set interval via environment variable or server config.
3. Restart or reload the server so pyspigot loads the plugin.

Testing locally
- Run the file directly to exercise the built-in test harness (it simulates a server and schedules a short restart):

```bash
python3 main.py
```

Notes
- Because pyspigot implementations vary, this plugin uses a defensive approach to find a suitable API on the `server` object.
- If your pyspigot instance exposes a different API name, adapt the plugin by adding that attribute name to the list tried in `main.py`.

If you'd like, I can adapt this plugin to match your exact pyspigot server API if you paste a short snippet of the server object or the pyspigot plugin docs you have.
