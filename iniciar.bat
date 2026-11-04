@echo off
rem Liga a Academia Tecnica. Basta dar dois cliques neste arquivo.
rem Para mudar a porta, troque o numero abaixo.
set PORTA=8000
rem Esconde o aviso em ingles do runserver, que nao e um erro.
set DJANGO_RUNSERVER_HIDE_WARNING=true

cd /d "%~dp0"
if exist venv\Scripts\activate.bat call venv\Scripts\activate.bat

set CONFIGURAR=nao
if not exist .env set CONFIGURAR=sim
if exist .env findstr /B /C:"DJANGO_SITE_URL=" .env >nul || set CONFIGURAR=sim
if %CONFIGURAR%==sim (
    echo.
    echo Falta configurar o sistema neste computador. Responda as perguntas.
    python manage.py configurar_servidor
    if errorlevel 1 goto erro
)

echo.
echo Atualizando o banco de dados...
python manage.py migrate --noinput
if errorlevel 1 goto erro

echo.
echo Ligando a Academia Tecnica na porta %PORTA%.
echo NAO feche esta janela: fechar a janela desliga o sistema.
echo.
python manage.py runserver 0.0.0.0:%PORTA%

:erro
echo.
echo O sistema parou. Tire uma foto desta janela e envie para o suporte.
pause
