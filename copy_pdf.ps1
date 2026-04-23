$files = Get-ChildItem 'C:\Users\shira_k13727w\OneDrive\DF\アライアンス関連\AIブログ\' | Where-Object { $_.Extension -eq '.pdf' }
$target = $files | Select-Object -First 1
Copy-Item $target.FullName 'C:\Users\shira_k13727w\OneDrive\Desktop\クロード保管用\temp_guide.pdf'
Write-Host "Copied: $($target.Name)"
