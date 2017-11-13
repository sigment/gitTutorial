@Echo Off
Rem
echo "Broadlink RM2 python plugin install for Win"
echo " this need to be run with admin right "
Rem
Rem 
rem pre-request installation 
rem
Echo ""
Echo ""
Echo "Search python version"
python --version | find "3.4"
if errorlevel 1 goto py35
set py=34
goto suite
:py35
python --version | find "3.5"
if errorlevel 1 goto py36
set py=35
goto suite
:py36
python --version | find "3.6"
if errorlevel 1 goto errorpy
set py=36
goto suite
:suite
REM
echo " main module used by the plugin"
REM
echo "Python version : " %py%
:Crypto
if "%py%"=="34" goto crypto34
goto broadlink
:crypto34
rem
echo "crypto installation for 3.4"
rem no more required since v3
rem pycrypto-2.6.1.win32-py3.4.exe
:broadlink
pip install broadlink
if errorlevel 1 goto errorbroadlink
goto domoticz
REM
echo "Copy plugin.py to location"
REM
:domoticz
if not exist "%ProgramFiles(x86)%\Domoticz" goto errordomoticz
if exist "%ProgramFiles(x86)%\Domoticz\plugins\BroadlinkRM2" goto errorplugin
xcopy plugin.py "%ProgramFiles(x86)%\Domoticz\plugins\BroadlinkRM2\" /s /e  /y
if errorlevel 1 goto errorxcopy
xcopy plugin_send.py "%ProgramFiles(x86)%\Domoticz\plugins\BroadlinkRM2\" /s /e  /y
if errorlevel 1 goto errorxcopy
xcopy plugin_send.cmd "%ProgramFiles(x86)%\Domoticz\plugins\BroadlinkRM2\" /s /e  /y
if errorlevel 1 goto errorxcopy
xcopy plugin_http.cmd "%ProgramFiles(x86)%\Domoticz\plugins\BroadlinkRM2\" /s /e  /y
if errorlevel 1 goto errorxcopy
xcopy plugin_http.py "%ProgramFiles(x86)%\Domoticz\plugins\BroadlinkRM2\" /s /e  /y
if errorlevel 1 goto errorxcopy

if not exist c:\Domoticz mklink /j c:\Domoticz "c:Program Files (x86)\Domoticz"
sc query domoticz
if errorlevel 1 goto end
REM
echo "re start Domoticz service"
REM
sc stop domoticz
timeout 5
sc start domoticz
timeout 5

goto end

:errorpy
color 4
Echo ""
echo "ERROR: required python is missing"
pause
exit 1
:errorbroadlink
color 4
Echo ""
echo "ERROR: broadlink installation error"
pause
exit 4
:errordomoticz
color 4
Echo ""
echo "ERROR: location domoticz does not exist"
pause
exit 5
:errorplugin
color 4
Echo ""
echo "ERROR: plugin already exist"
pause
exit 6
:errorxcopy
color 4
Echo ""
echo "ERROR: copy plugin error"
pause
exit 7

:end
Echo ""
echo "installation finished successfully"