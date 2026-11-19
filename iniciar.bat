@echo off
rem Inicia ImageTagger sin consola (pythonw). Sin argumentos monitorea el
rem directorio indicado en config.ini ([GENERAL] directorio_monitoreo);
rem opcionalmente se puede indicar otro directorio: iniciar.bat C:\ruta\a\monitorear
rem Los errores de inicio se muestran en un cuadro de diálogo.
setlocal
cd /d "%~dp0"

rem Si existe el entorno virtual .venv se usa su Python; si no, el del PATH.
set "PYTHON=pythonw"
if exist ".venv\Scripts\pythonw.exe" set "PYTHON=.venv\Scripts\pythonw.exe"

"%PYTHON%" --version >nul 2>nul
if errorlevel 1 (
    echo No se encontro Python. Instalelo o cree el entorno virtual .venv (ver README.md^).
    pause
    exit /b 1
)

rem start: lanza la aplicación y el .bat termina enseguida, así la consola se
rem cierra en lugar de quedar abierta y vacía mientras la aplicación corre.
start "" "%PYTHON%" main.py %*
endlocal
