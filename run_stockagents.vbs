Set objShell = CreateObject("WScript.Shell")
objShell.CurrentDirectory = "d:\projects\Stockagents"
objShell.Run "py desktop_app.py", 0, False
