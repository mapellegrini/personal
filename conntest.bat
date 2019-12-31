@ECHO OFF
IF "%1"=="-h" echo Pings google ten times at five minute intervals and prints the result && exit /B
IF "%1"=="--h" echo Pings google ten times at five minute intervals and prints the result && exit /B
IF "%1"=="--help" echo Pings google ten times at five minute intervals and prints the result && exit /B

:loop
date /t && time /t && ping -w 1000 -n 10 8.8.8.8 | findstr loss
timeout 3 | findstr none
goto loop