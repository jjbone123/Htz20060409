@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 校园人才快速筛选系统 - 服务运行中
echo ============================================================
echo   轻量化 AI 驱动校园人才快速筛选系统
echo   正在启动本地服务，浏览器将自动打开...
echo   关闭本窗口即停止服务
echo ============================================================
python server.py
if errorlevel 1 (
  echo.
  echo 启动失败！请确认已安装 Python 3，并已安装依赖：
  echo   python -m pip install flask openpyxl requests
  pause
)
