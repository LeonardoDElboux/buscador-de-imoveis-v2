@echo off
chcp 65001 >nul
title Publicar Atualizacao no GitHub e Netlify

echo =======================================================
echo    PUBLICADOR AUTOMATICO - RADAR DE IMOVEIS (GITHUB)
echo =======================================================
echo.
echo Este assistente vai sincronizar seus arquivos atualizados
echo e ativar o robo de atualizacao automatica no GitHub.
echo.

cd /d "%~dp0"

where git >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERRO] Git nao encontrado instalado no PATH.
    echo Voce pode subir os arquivos manualmente pelo site github.com.
    pause
    exit /b
)

echo [1/4] Configurando identificacao do Git...
git config user.name "Leonardo DBX"
git config user.email "83027220+LeonardoDElboux@users.noreply.github.com"

if not exist ".git" (
    echo [2/4] Inicializando repositorio Git local...
    git init -b main
    git remote add origin https://github.com/LeonardoDElboux/buscador-de-imoveis-v2.git
) else (
    git remote set-url origin https://github.com/LeonardoDElboux/buscador-de-imoveis-v2.git
)

echo [3/4] Preparando arquivos modificados...
git add -A

echo [4/4] Criando commit e enviando para o GitHub...
git commit -m "feat: catalogo 100%% verificado com atualizacao automatica via GitHub Actions"
git push -u origin main

echo.
echo =======================================================
echo    CONCLUIDO COM SUCESSO!
echo =======================================================
echo O GitHub recebeu os novos arquivos.
echo O Netlify iniciara o deploy automaticamente em instantes!
echo O robo GitHub Actions rodara diariamente para atualizar os imoveis.
echo.
pause
