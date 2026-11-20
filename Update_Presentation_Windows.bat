@echo off
setlocal EnableExtensions
chcp 65001 >nul
pushd "%~dp0"
if errorlevel 1 goto ERROR_FOLDER
set "PYEXE=.venv\Scripts\python.exe"
if not exist "%PYEXE%" goto ERROR_PY
if not exist "data\raw\regions_2021.geojson" goto ERROR_DATA

echo.
echo [1/2] Redrawing regional maps with corrected Chukotka position...
"%PYEXE%" "src\analyze.py"
if errorlevel 1 goto ERROR_ANALYZE

echo.
echo [2/2] Updating presentation using real 2021 results...
"%PYEXE%" "src\build_materials.py"
if errorlevel 1 goto ERROR_PRESENTATION

echo.
echo SUCCESS: corrected 2021 slides are ready.
echo Open presentation\Team3_Demography_2021.pptx
popd
pause
exit /b 0

:ERROR_FOLDER
echo Cannot access project folder.
goto FAILED
:ERROR_PY
echo Python environment is missing; first run Start_Windows.bat.
goto FAILED
:ERROR_DATA
echo The real GeoJSON has not been downloaded; first run Start_Windows.bat.
goto FAILED
:ERROR_ANALYZE
echo Regional analysis failed. Check the warnings and logs.
goto FAILED
:ERROR_PRESENTATION
echo PowerPoint generation failed.
goto FAILED
:FAILED
popd
pause
exit /b 1
