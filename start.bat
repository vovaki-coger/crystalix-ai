@echo off
chcp 65001 > nul
echo Запуск Crystalix AI...

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo Python не найден! Запусти install.bat сначала.
    pause
    exit /b 1
)

python main.py
if %errorlevel% neq 0 (
    echo.
    echo Ошибка запуска. Запусти install.bat если не установил зависимости.
    pause
)
