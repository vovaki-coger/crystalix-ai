@echo off
chcp 65001 > nul
echo ========================================
echo   Crystalix AI - Установка зависимостей
echo ========================================
echo.

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ОШИБКА] Python не найден!
    echo Скачай Python с https://python.org и установи с галочкой "Add to PATH"
    pause
    exit /b 1
)

echo [OK] Python найден
echo.
echo Устанавливаю зависимости...
pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo.
    echo [ОШИБКА] Не удалось установить пакеты
    pause
    exit /b 1
)

echo.
echo ========================================
echo [OK] Установка завершена!
echo.
echo Убедись что Ollama запущена и есть модель llava:
echo   ollama pull llava
echo.
echo Потом запускай start.bat
echo ========================================
pause
