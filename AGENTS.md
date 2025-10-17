# Repository Guidelines

## Project Structure & Module Organization
The PyQt6 entry point is `main.py`, which launches `MainWindow` in `main_window.py`. UI dialogs, styles, and status handling are split across `settings_dialog.py`, `styles.py`, and `workers.py` (threaded background tasks). Domain logic—including Baidu OCR calls, alias building, and comparison helpers—lives in `logic.py`. Excel ingestion is handled by `excel_parser.py`, while reusable scripts (`build_mac.sh`, `build_windows.bat`, `QUICK_BUILD.md`) cover packaging instructions. Current automated checks sit in `test_ocr_parsing.py`; add new test modules alongside it until a dedicated `tests/` package is introduced.

## Build, Test, and Development Commands
Install dependencies with `python3 -m pip install -r requirements.txt`. Run the desktop app locally via `python3 main.py`. For a quick smoke test of the OCR parsing logic execute `python3 test_ocr_parsing.py`, which prints parsed schemes and highlights extraction gaps. macOS and Windows bundles are produced with `./build_mac.sh` and `build_windows.bat` respectively; both scripts call PyInstaller using the pinned `MedicalExamChecker.spec`.

## Coding Style & Naming Conventions
Follow Black-style 4-space indentation and keep imports grouped by standard library, third party, and local modules (see `logic.py`). Use type hints for new functions when signatures cross modules, and prefer descriptive snake_case names for variables, functions, and module-level constants (e.g., `STATUS_ICON`). GUI labels may remain bilingual, but code comments and docstrings should be concise English explanations. Run `pyinstaller` or `pip` commands only from the repository root so relative paths remain correct.

## Testing Guidelines
`test_ocr_parsing.py` currently exercises OCR normalization via prints; extend it or introduce `pytest`-style assertions to prevent regressions in `logic.extract_data_from_ocr_json`. Mirror the naming pattern `test_<feature>.py`, and keep sample OCR payloads close to the tests that use them. Before opening a PR, run all tests (`python3 test_ocr_parsing.py`) and verify GUI workflows manually when changing UI flow or threading behavior.

## Commit & Pull Request Guidelines
The Git history is empty, so please adopt a Conventional Commits style (`feat:`, `fix:`, `chore:`) to make changelogs easy. Write focused commits that touch related files only; include references to user stories or issue IDs in the body when available. Pull requests should summarize user-facing changes, list manual test evidence (CLI output or screenshots), and flag any configuration updates or new dependencies. Confirm that bundled builds succeed if packaging scripts or PyInstaller settings change.

## Configuration & Security Notes
OCR credentials are loaded through `QSettings` (see `MainWindow.processing_thread`), so avoid hardcoding API keys in source files or sample data. When capturing logs, keep them out of version control unless they are sanitized exemplars. Document any new environment variables or settings dialog keys in `QUICK_BUILD.md` or a follow-up configuration note.
