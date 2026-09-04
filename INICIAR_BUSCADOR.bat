@echo off
chcp 65001 > nul
title Buscador de Imoveis - Centralizador de Locacao
echo =======================================================
echo          INICIANDO O BUSCADOR DE IMÓVEIS (V2)
echo =======================================================
echo.

cd /d "%~dp0"

REM Verifica se o ambiente virtual existe, se não, cria com uv
if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Criando ambiente virtual Python com uv...
    uv venv --python 3.12 .venv
    echo [2/3] Instalando dependencias necessarias...
    uv pip install -r requirements.txt --python .venv\Scripts\python.exe
)

echo [3/3] Iniciando servidor local do Buscador...
echo.
echo Servidor disponivel em:
echo    -> http://127.0.0.1:8000
echo    -> http://localhost:8000
echo.
echo Pressione Ctrl+C nesta janela caso queira encerrar o sistema.
echo.

REM Aguarda 2 segundos e abre o navegador diretamente no IP local 127.0.0.1 (evita erro de resolucao IPv6 no Opera/Chrome)
start "" /b cmd /c "timeout /t 2 /nobreak > nul && start http://127.0.0.1:8000"

REM Inicia o servidor ouvindo em 0.0.0.0 para aceitar conexoes de localhost e 127.0.0.1
".venv\Scripts\python.exe" -m uvicorn app:app --host 0.0.0.0 --port 8000

pause
