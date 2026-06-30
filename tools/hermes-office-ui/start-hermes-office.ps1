# Hermes办公室 一键启动脚本
# 用法：右键 start-hermes-office.cmd 或 启动Hermes办公室.cmd 运行

$ErrorActionPreference = 'Continue'
$OfficeDir = $PSScriptRoot
$OfficeUrl = 'http://127.0.0.1:8787/hermes-office.html?v=start'

function Test-LocalPort {
    param([int]$Port)
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $async = $client.BeginConnect('127.0.0.1', $Port, $null, $null)
        $ok = $async.AsyncWaitHandle.WaitOne(700, $false)
        if ($ok) {
            $client.EndConnect($async)
            $client.Close()
            return $true
        }
        $client.Close()
        return $false
    } catch {
        return $false
    }
}

Write-Host '========================================' -ForegroundColor Cyan
Write-Host ' Hermes办公室 启动器' -ForegroundColor Cyan
Write-Host '========================================' -ForegroundColor Cyan

if (Test-LocalPort 8642) {
    Write-Host '[1/3] Hermes Gateway / API Server 已在 8642 运行。' -ForegroundColor Green
} else {
    Write-Host '[1/3] 正在启动 Hermes Gateway：hermes gateway run' -ForegroundColor Yellow
    Start-Process powershell -ArgumentList @('-NoExit', '-ExecutionPolicy', 'Bypass', '-Command', 'hermes gateway run')
    Start-Sleep -Seconds 8
    if (Test-LocalPort 8642) {
        Write-Host '      Gateway/API Server 已启动。' -ForegroundColor Green
    } else {
        Write-Host '      警告：暂未检测到 8642，请看新打开的 Gateway 窗口日志。' -ForegroundColor Red
    }
}

if (Test-LocalPort 8787) {
    Write-Host '[2/3] Hermes办公室 本地桥服务已在 8787 运行。' -ForegroundColor Green
} else {
    Write-Host '[2/3] 正在启动 Hermes办公室 本地桥服务：python office-server.py' -ForegroundColor Yellow
    Start-Process powershell -WorkingDirectory $OfficeDir -ArgumentList @('-NoExit', '-ExecutionPolicy', 'Bypass', '-Command', 'python office-server.py')
    Start-Sleep -Seconds 3
    if (Test-LocalPort 8787) {
        Write-Host '      本地桥服务已启动。' -ForegroundColor Green
    } else {
        Write-Host '      警告：暂未检测到 8787，请看新打开的 Office Bridge 窗口日志。' -ForegroundColor Red
    }
}

Write-Host '[3/3] 打开 Hermes办公室 页面。' -ForegroundColor Yellow
Start-Process $OfficeUrl

Write-Host ''
Write-Host '如果页面显示未连接，请 Ctrl+F5 强制刷新，或确认两个窗口不要关闭：' -ForegroundColor Gray
Write-Host '  1) Hermes Gateway 窗口' -ForegroundColor Gray
Write-Host '  2) Hermes办公室 本地桥服务窗口' -ForegroundColor Gray
Write-Host ''
Write-Host "页面地址：$OfficeUrl" -ForegroundColor Cyan
Write-Host ''
Read-Host '启动命令已执行，按 Enter 关闭这个启动器窗口'