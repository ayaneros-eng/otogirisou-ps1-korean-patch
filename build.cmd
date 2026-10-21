@echo off
setlocal
cd /d "%~dp0"
set "CSC=%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if not exist "%CSC%" set "CSC=%WINDIR%\Microsoft.NET\Framework\v4.0.30319\csc.exe"
if not exist "%CSC%" (
  echo .NET Framework C# compiler not found.
  exit /b 1
)
"%CSC%" /nologo /utf8output /target:winexe /platform:anycpu /optimize+ /reference:System.Windows.Forms.dll /reference:System.Drawing.dll /reference:System.Runtime.Serialization.dll /resource:mdec-vlc.txt,mdec-vlc.txt /resource:patch.json,patch.json /resource:Otogirisou_KO_R152.otopatch,patch.otopatch /out:Otogirisou_Korean_Patcher.exe Patcher.cs SourceDelta.cs
exit /b %ERRORLEVEL%
