@echo off
setlocal EnableExtensions
chcp 65001 >nul
pushd "%~dp0"
if errorlevel 1 goto FOLDER_ERROR
set "VENV_PY=.venv\Scripts\python.exe"
if exist "%VENV_PY%" goto INSTALL
where py >nul 2>nul
if errorlevel 1 goto TRY_PYTHON
py -3 -m venv ".venv"
if exist "%VENV_PY%" goto INSTALL
:TRY_PYTHON
where python >nul 2>nul
if errorlevel 1 goto PYTHON_ERROR
python -m venv ".venv"
if not exist "%VENV_PY%" goto PYTHON_ERROR
:INSTALL
echo Installing required Python libraries...
"%VENV_PY%" -m pip install --disable-pip-version-check -r "requirements.txt"
if errorlevel 1 goto RUN_ERROR
echo Running DEMO using fictional example values...
"%VENV_PY%" "src\analyze.py" --demo
if errorlevel 1 goto RUN_ERROR
"%VENV_PY%" "src\build_materials.py" --demo
if errorlevel 1 goto RUN_ERROR
echo DEMO complete. This is NOT actual regional data.
popd
pause
exit /b 0
:FOLDER_ERROR
echo ERROR: Could not open project folder.
goto FAILED
:PYTHON_ERROR
echo ERROR: Python 3.10 or newer is required.
goto FAILED
:RUN_ERROR
echo ERROR: DEMO setup or processing failed. See above.
goto FAILED
:FAILED
popd
pause
exit /b 1
