Set WshShell = CreateObject("WScript.Shell")
strStartup = WshShell.SpecialFolders("Startup")
Set oShellLink = WshShell.CreateShortcut(strStartup & "\請求書メール通知.lnk")
oShellLink.TargetPath = "pythonw.exe"
strArg = Chr(34) & "C:\Users\shira_k13727w\OneDrive\Desktop\クロード保管用\18【請求書の通知メール】\invoice_notifier.py" & Chr(34)
oShellLink.Arguments = strArg
oShellLink.WorkingDirectory = "C:\Users\shira_k13727w\OneDrive\Desktop\クロード保管用\18【請求書の通知メール】"
oShellLink.Description = "請求書メール通知システム"
oShellLink.Save
WScript.Echo "done"
