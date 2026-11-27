# Repository map

- `src/`: Python runtime, registry synchronization, storage, security and recovery.
- `frontend/`: typed desktop UI sources.
- `static/`: authenticated loopback desktop UI resources.
- `desktop/`: native Tauri host.
- `windows/` and `linux/`: operating-system packaging.
- `tests/`: runtime and release regression tests.
- `tools/`: maintenance, acceptance and release utilities.
- `branding/` and `docs/`: visual references and documentation.
- `.github/workflows/`: CI, snapshot restoration and release verification.

From the root, run `python -m pip install -e . --no-deps` before direct module imports or tests, or set PYTHONPATH to the absolute src directory. The source launcher is src/tvrtk_scraper.py. START-WINDOWS.bat and start-linux.sh retain their original root paths.
