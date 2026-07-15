@echo off
chcp 65001 >nul
title 外文文献追踪工作台

echo 🚀 正在启动工作台...
echo.

cd /d "%~dp0"
start "" http://localhost:8501
.\.venv\Scripts\streamlit.exe run app.py --server.headless true

pause
