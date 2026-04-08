$path = 'C:\Users\shira_k13727w\OneDrive\Desktop\サーバー起動.bat'
$enc932 = [System.Text.Encoding]::GetEncoding(932)

$content = "@echo off`r`n"
$content += "cd /d `"C:\Users\shira_k13727w\OneDrive\Desktop\クロード保管用\01営業管理システム【della score】`"`r`n"
$content += "title サーバー起動`r`n"
$content += "tasklist /fi `"imagename eq php.exe`" 2>nul | find /i `"php.exe`" >nul`r`n"
$content += "if errorlevel 1 (`r`n"
$content += "  start /min `"PHP`" php -S localhost:8080`r`n"
$content += "  timeout /t 2 /nobreak >nul`r`n"
$content += ")`r`n"
$content += "echo.`r`n"
$content += "echo サーバーが起動しました。トンネル接続中...`r`n"
$content += "echo.`r`n"
$content += ":loop`r`n"
$content += "ssh -R 80:localhost:8080 nokey@localhost.run`r`n"
$content += "timeout /t 3 /nobreak >nul`r`n"
$content += "goto loop`r`n"

$bytes = $enc932.GetBytes($content)
[System.IO.File]::WriteAllBytes($path, $bytes)
Write-Host "完了"
