@echo off
rem Inicia ImageTagger. Sin argumentos monitorea el directorio indicado en
rem config.ini ([GENERAL] directorio_monitoreo); opcionalmente se puede indicar
rem otro directorio: iniciar.bat C:\ruta\a\monitorear
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo No se encontro Python. Instalelo y asegurese de que este en el PATH.
    pause
    exit /b 1
)

rem -u: salida sin búfer, para que se vea al instante aunque no haya consola
rem (por ejemplo en el panel Output de la extensión Code Runner de VS Code).
rem PYTHONIOENCODING: acentos correctos cuando la salida va a un panel o archivo.
set PYTHONIOENCODING=utf-8
python -u main.py %*
if errorlevel 1 (
    echo.
    echo La aplicacion termino con errores.
    pause
)
endlocal
