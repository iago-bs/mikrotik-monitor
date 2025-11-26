@echo off
echo ========================================
echo   MikroTik Monitor - Build EXE
echo ========================================
echo.

REM Verificar se está na pasta raiz do projeto
if not exist "backend\app.py" (
    echo ERRO: Execute este script da pasta raiz do projeto!
    pause
    exit /b 1
)

echo [1/3] Instalando PyInstaller...
pip install pyinstaller
if %ERRORLEVEL% NEQ 0 (
    echo ERRO ao instalar PyInstaller
    pause
    exit /b 1
)

echo.
echo [2/3] Gerando executavel...
pyinstaller --onefile ^
    --add-data "public;public" ^
    --add-data "backend\.env;backend" ^
    --icon=NONE ^
    --name MikroTikMonitor ^
    --noconsole ^
    backend\app.py

if %ERRORLEVEL% NEQ 0 (
    echo ERRO ao gerar executavel
    pause
    exit /b 1
)

echo.
echo [3/3] Finalizando...
if exist "dist\MikroTikMonitor.exe" (
    echo.
    echo ========================================
    echo   BUILD CONCLUIDO COM SUCESSO!
    echo ========================================
    echo.
    echo Executavel gerado em: dist\MikroTikMonitor.exe
    echo.
    echo IMPORTANTE:
    echo O arquivo .env ja esta incluido no executavel
    echo Execute dist\MikroTikMonitor.exe e acesse http://localhost:5000
    echo.
) else (
    echo ERRO: Executavel nao foi gerado
)

pause
