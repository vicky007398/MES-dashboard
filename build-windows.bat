@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv-build\Scripts\python.exe" (
    py -3 -m venv .venv-build || exit /b 1
)
".venv-build\Scripts\python.exe" -m pip install -r requirements.txt "pyinstaller>=6,<7" || exit /b 1
".venv-build\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile ^
    --name MES-Dashboard ^
    --add-data "app.py:." ^
    --hidden-import app ^
    --collect-all streamlit ^
    --collect-submodules uvicorn ^
    --collect-submodules openpyxl ^
    --hidden-import xlrd ^
    --copy-metadata openpyxl ^
    --copy-metadata xlrd ^
    --copy-metadata altair ^
    windows_launcher.py || exit /b 1
echo Built dist\MES-Dashboard.exe
