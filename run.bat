@echo off
@chcp 65001 >nul

cd /d "%~dp0"
title PUBG Convenience Overlay Launcher

echo ========================================================
echo   [PUBG Convenience Overlay] 배틀그라운드 편의 오버레이
echo ========================================================
echo.
echo * 배틀그라운드 화면 설정: 반드시 '전체 창모드'로 설정하세요!
echo * 배틀아이(BattlEye) 정지 위험 0%% (메모리 비접근 순수 투명 윈도우)
echo.
echo [단축키 안내]
echo   - TAB (누르는 동안) : 파밍 부착물 및 소모품 체크 HUD
echo   - F1                : 중앙 조준점(크로스헤어) On / Off
echo   - F2                : 자기장(블루존) 페이즈 타이머 시작/전환
echo   - F3                : 수류탄 쿠킹 타이머 (5초 카운트다운 및 경고음)
echo   - F4                : 총기 세팅 프리셋 변경 (M4+DMR / 베릴 / 5탄 등)
echo   - F5 / F6           : 주무기1 / 주무기2 부착물 획득 체크 토글
echo   - F7                : 새 게임 시작 (파밍 및 타이머 초기화)
echo   - F9                : 오버레이 프로그램 종료
echo.
echo [INFO] 시스템 환경 점검 중...

where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] 시스템에 Python이 설치되어 있지 않거나 PATH에 등록되지 않았습니다.
    echo https://www.python.org 에서 Python을 설치해 주세요.
    echo.
    pause
    exit /b 1
)

echo [INFO] 오버레이를 실행합니다...
echo ========================================================
python "%~dp0pubg_overlay.py" %*
if errorlevel 1 (
    echo ========================================================
    echo [ERROR] 프로그램이 비정상 종료되었습니다.
    pause
    exit /b 1
)
echo ========================================================
echo [INFO] 프로그램이 정상적으로 종료되었습니다.
exit /b 0
