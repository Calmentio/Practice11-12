@echo off
setlocal EnableExtensions
chcp 65001 >nul
pushd "%~dp0"
if errorlevel 1 goto FOLDER_ERROR

set "VENV_PY=.venv\Scripts\python.exe"
echo.
echo [1/5] Checking Python and virtual environment...
if exist "%VENV_PY%" goto PYTHON_READY
where py >nul 2>nul
if errorlevel 1 goto TRY_PYTHON
py -3 -m venv ".venv"
if exist "%VENV_PY%" goto PYTHON_READY

:TRY_PYTHON
where python >nul 2>nul
if errorlevel 1 goto PYTHON_ERROR
python -m venv ".venv"
if not exist "%VENV_PY%" goto PYTHON_ERROR

:PYTHON_READY
"%VENV_PY%" -c "import sys; sys.exit(sys.version_info < (3, 10))"
if errorlevel 1 goto PYTHON_ERROR
"%VENV_PY%" -m pip --version >nul 2>nul
if not errorlevel 1 goto INSTALL
"%VENV_PY%" -m ensurepip --upgrade
if errorlevel 1 goto PYTHON_ERROR

:INSTALL
echo.
echo [2/5] Installing required Python libraries...
"%VENV_PY%" -m pip install --disable-pip-version-check -r "requirements.txt"
if errorlevel 1 goto PIP_ERROR

echo.
echo [3/5] Downloading 2021 statistical data and map...
"%VENV_PY%" "src\download_sources.py"
if errorlevel 1 goto DATA_ERROR

echo.
echo [4/5] Running real regional analysis...
"%VENV_PY%" "src\analyze.py"
if errorlevel 1 goto ANALYSIS_ERROR

echo.
echo [5/5] Generating report and slides...
"%VENV_PY%" "src\build_materials.py"
if errorlevel 1 goto BUILD_ERROR

echo.
echo SUCCESS. Project finished.
echo Open presentation\Team3_Demography_2021.pptx
echo Open docs\Report_Team3.docx
popd
pause
exit /b 0

:FOLDER_ERROR
echo ERROR: Cannot access the project folder.
goto FAILED
:PYTHON_ERROR
echo ERROR: Python 3.10 or newer is required.
echo Install Python from python.org and enable Add Python to PATH.
echo If .venv was created with the wrong Python, delete the .venv folder and restart.
goto FAILED
:PIP_ERROR
echo ERROR: Python libraries could not be installed. Check the internet connection.
goto FAILED
:DATA_ERROR
echo ERROR: Source data could not be downloaded or extracted.
echo Read README.md, section 2. Install 7-Zip if needed.
goto FAILED
:ANALYSIS_ERROR
echo ERROR: Regional data audit or analysis failed.
echo Check the console messages, source files and results folder.
goto FAILED
:BUILD_ERROR
echo ERROR: Report or presentation generation failed.
goto FAILED
:FAILED
echo.
echo The project has stopped. Please send a screenshot of this window if needed.
popd
pause
exit /b 1
