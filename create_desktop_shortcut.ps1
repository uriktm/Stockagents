# PowerShell script to create a desktop shortcut for Stockagents

$WshShell = New-Object -ComObject WScript.Shell
$DesktopPath = [System.Environment]::GetFolderPath('Desktop')
$ShortcutPath = Join-Path $DesktopPath "Stockagents.lnk"

$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = "wscript.exe"
$Shortcut.Arguments = "`"$PSScriptRoot\run_stockagents.vbs`""
$Shortcut.WorkingDirectory = $PSScriptRoot
$Shortcut.Description = "Stockagents Desktop - ניתוח מניות חכם"
$Shortcut.IconLocation = "shell32.dll,43"  # Stock chart icon
$Shortcut.Save()

Write-Host "✅ קיצור דרך נוצר בהצלחה על שולחן העבודה!" -ForegroundColor Green
Write-Host "📍 מיקום: $ShortcutPath" -ForegroundColor Cyan
