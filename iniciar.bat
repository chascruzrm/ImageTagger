@echo off
rem Inicia ImageTagger. Sin argumentos monitorea el directorio indicado en
rem config.ini ([GENERAL] directorio_monitoreo); opcionalmente se puede indicar
rem otro directorio: iniciar.bat C:\ruta\a\monitorear
setlocal
cd /d "%~dp0"

rem Si existe el entorno virtual .venv se usa su Python; si no, el del PATH.
set "PYTHON=python"
if exist ".venv\Scripts\python.exe" set "PYTHON=.venv\Scripts\python.exe"

"%PYTHON%" --version >nul 2>nul
if errorlevel 1 (
    echo No se encontro Python. Instalelo o cree el entorno virtual .venv (ver README.md^).
    pause
    exit /b 1
)

rem -u: salida sin búfer, para que se vea al instante aunque no haya consola
rem (por ejemplo en el panel Output de la extensión Code Runner de VS Code).
rem PYTHONIOENCODING: acentos correctos cuando la salida va a un panel o archivo.
set PYTHONIOENCODING=utf-8
"%PYTHON%" -u main.py %*
if errorlevel 1 (
    echo.
    echo La aplicacion termino con errores.
    pause
)
endlocal
