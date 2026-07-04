@echo off
chcp 65001 >nul
echo.
echo   📖 SAT Vocabulary Story Generator
echo   ==================================
echo.
echo   启动后浏览器打开: http://localhost:8888
echo   按 F5 刷新 → 换新故事
echo   关闭此窗口 → 停止服务器
echo.
cd /d "%~dp0"
start "" http://localhost:8888
C:\Users\tntsg\AppData\Local\Programs\Python\Python313\python.exe story_server.py
pause
