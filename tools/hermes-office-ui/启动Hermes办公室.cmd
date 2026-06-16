@echo off
chcp 65001 >nul
title 启动 Hermes办公室
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-hermes-office.ps1"
