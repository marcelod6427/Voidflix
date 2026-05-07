@echo off
title VOIDFLIX - Servidor Local
color 5F
echo.
echo  ==============================================
echo    VOIDFLIX - Iniciando servidor local...
echo  ==============================================
echo.

:: Verifica se Python esta instalado
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERRO] Python nao encontrado!
    echo  Instale o Python em: https://python.org/downloads
    echo  Lembre de marcar "Add to PATH" durante a instalacao.
    echo.
    pause
    exit /b
)

:: Verifica se o server.py existe na mesma pasta
if not exist "%~dp0server.py" (
    echo  [ERRO] server.py nao encontrado!
    echo  Certifique-se de que este arquivo .bat esta na mesma
    echo  pasta que o server.py e o index.html.
    echo.
    pause
    exit /b
)

:: Verifica se o index.html existe na mesma pasta
if not exist "%~dp0index.html" (
    echo  [ERRO] index.html nao encontrado!
    echo  Certifique-se de que este arquivo .bat esta na mesma
    echo  pasta que o server.py e o index.html.
    echo.
    pause
    exit /b
)

echo  Todos os arquivos encontrados. Iniciando...
echo.
echo  Acesse: http://localhost:8765
echo  Para encerrar: feche esta janela ou pressione Ctrl+C
echo.
echo  -----------------------------------------------

:: Muda para o diretorio do .bat antes de rodar o Python
cd /d "%~dp0"
python server.py
pause
