@echo off
@chcp 65001 >nul
setlocal enabledelayedexpansion

cd /d "%~dp0"
title PUBG Convenience Overlay Launcher

echo ========================================================
echo   [PUBG Convenience Overlay] 배틀그라운드 편의 오버레이
echo ========================================================
echo.
echo * 배틀그라운드 화면 설정: 반드시 '전체 창모드'로 설정하세요!
echo * 배틀아이 정지 위험 0%% [메모리 비접근 순수 투명 윈도우]
echo.
echo [단축키 안내]
echo   - TAB [누르는 동안] : 파밍 부착물 및 소모품 체크 HUD
echo   - F1                : 중앙 조준점[크로스헤어] On / Off
echo   - F2                : 자기장[블루존] 페이즈 타이머 시작/전환
echo   - F3                : 수류탄 쿠킹 타이머 [5초 카운트다운 및 경고음]
echo   - F4                : 총기 세팅 프리셋 변경 [M4+DMR / 베릴 / 5탄 등]
echo   - F5 / F6           : 주무기1 / 주무기2 부착물 획득 체크 토글
echo   - F7                : 새 게임 시작 [파밍 및 타이머 초기화]
echo   - F8                : OCR 화면 자동인식 On / Off 토글
echo   - ~ [물결표]        : 맵별 차량 및 비밀방 위치 지도 HUD 토글
echo   - F10               : 맵 선택 변경 [태이고/데스턴/론도/에란겔/미라마]
echo   - F9                : 오버레이 프로그램 종료
echo.
echo [1/3] 파이썬 런타임 환경 점검 중...

set "PY_EXEC="
call :CHECK_PYTHON

if "!PY_EXEC!"=="" (
    echo.
    echo ========================================================
    echo [안내] PC에 Python이 설치되어 있지 않습니다.
    echo 오버레이 실행에 필요한 공식 Python 환경을 자동 설치합니다.
    echo ========================================================
    echo.
    call :INSTALL_PYTHON
    call :CHECK_PYTHON
)

if "!PY_EXEC!"=="" (
    echo.
    echo [ERROR] 파이썬 자동 설치에 실패했습니다.
    echo 수동으로 https://www.python.org 에서 Python을 설치해 주세요.
    echo [설치 시 'Add Python to PATH' 및 'tcl/tk and IDLE' 체크 필수]
    echo.
    pause
    exit /b 1
)

echo [2/3] 실행 환경 확인 완료: !PY_EXEC!
echo [3/3] PUBG 오버레이를 시작합니다...
echo ========================================================
!PY_EXEC! "%~dp0pubg_overlay.py" %*
if errorlevel 1 (
    echo ========================================================
    echo [ERROR] 프로그램 실행 중 오류가 발생했습니다.
    pause
    exit /b 1
)
echo ========================================================
echo [INFO] 프로그램이 정상적으로 종료되었습니다.
exit /b 0

REM ========================================================
REM 서브루틴: 파이썬 검사
REM ========================================================
:CHECK_PYTHON
where python >nul 2>&1
if not errorlevel 1 (
    python -c "import tkinter, ctypes" >nul 2>&1
    if not errorlevel 1 (
        set "PY_EXEC=python"
        exit /b 0
    )
)

where py >nul 2>&1
if not errorlevel 1 (
    py -3 -c "import tkinter, ctypes" >nul 2>&1
    if not errorlevel 1 (
        set "PY_EXEC=py -3"
        exit /b 0
    )
)

for /d %%D in ("%LocalAppData%\Programs\Python\Python3*") do (
    if exist "%%D\python.exe" (
        "%%D\python.exe" -c "import tkinter, ctypes" >nul 2>&1
        if not errorlevel 1 (
            set "PY_EXEC=%%D\python.exe"
            exit /b 0
        )
    )
)
exit /b 0

REM ========================================================
REM 서브루틴: 파이썬 무인 자동 설치
REM ========================================================
:INSTALL_PYTHON
where winget >nul 2>&1
if not errorlevel 1 (
    echo [INFO] Windows 패키지 관리자 winget 으로 Python을 설치합니다...
    winget install Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
    if not errorlevel 1 exit /b 0
)

echo [INFO] python.org 공식 설치 프로그램을 다운로드합니다...
set "TEMP_INSTALLER=%TEMP%\python_installer_%RANDOM%.exe"
where curl.exe >nul 2>&1
if not errorlevel 1 (
    curl.exe -L -o "!TEMP_INSTALLER!" "https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe"
) else (
    powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object System.Net.WebClient).DownloadFile('https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe', '!TEMP_INSTALLER!')"
)

if exist "!TEMP_INSTALLER!" (
    echo [INFO] 파이썬 무인 자동 설치 진행 중 [약 30초 소요]...
    start /wait "" "!TEMP_INSTALLER!" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_tcltk=1 SimpleInstall=1
    del /f /q "!TEMP_INSTALLER!" >nul 2>&1
)
exit /b 0
