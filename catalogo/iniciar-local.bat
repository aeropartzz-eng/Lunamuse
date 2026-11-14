@echo off
cd /d "%~dp0"
where python >nul 2>nul
if %errorlevel%==0 (
  start "AeroPartz Catalogo" http://localhost:8000
  python -m http.server 8000
  goto :eof
)
where py >nul 2>nul
if %errorlevel%==0 (
  start "AeroPartz Catalogo" http://localhost:8000
  py -m http.server 8000
  goto :eof
)
echo Python nao encontrado. Abra index.html diretamente ou instale Python 3 para testar arquivos GLB locais.
pause
