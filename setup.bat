@echo off
echo ================================================
echo    MUSE AI Bot — O'rnatish
echo ================================================
echo.

echo [1/3] Kutubxonalar o'rnatilmoqda...
py -m pip install -r requirements.txt
if errorlevel 1 (
    echo XATO: O'rnatishda muammo!
    pause
    exit /b 1
)

echo.
echo [2/3] .env faylini tekshirish...
if not exist .env (
    echo XATO: .env fayli topilmadi!
    echo Iltimos .env faylini to'ldiring.
    pause
    exit /b 1
)

echo.
echo [3/3] Bot ishga tushirilmoqda...
echo ================================================
echo Bot ishga tushdi! To'xtatish uchun Ctrl+C bosing
echo ================================================
py bot.py

pause
