@echo off
echo Activando entorno virtual de Unisimon Scraper...
call venv\Scripts\activate.bat
echo.
echo Entorno virtual activado exitosamente!
echo.
echo Para ejecutar el scraper:
echo   python -m lms_agent_scraper.cli run
echo.
echo Para desactivar el entorno:
echo   deactivate
echo.
cmd /k
