@echo off
title CDSI Frontend Server
cd /d "%~dp0dashboard\frontend"
echo Starting CDSI Frontend on http://localhost:3000 ...
call npm.cmd run dev
pause
