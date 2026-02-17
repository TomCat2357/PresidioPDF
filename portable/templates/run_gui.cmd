@echo off
setlocal
cd /d "%~dp0"
.\python\pythonw.exe -m src.gui_pyqt.main %*
