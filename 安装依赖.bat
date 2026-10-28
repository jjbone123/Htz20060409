@echo off
chcp 65001 >nul
echo 正在安装所需依赖（flask / openpyxl / requests）...
python -m pip install flask openpyxl requests
echo.
echo 安装完成。双击「启动系统.bat」即可运行。
pause
