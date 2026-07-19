@echo off
echo Starting MotionRunner Expo...
start "" scrcpy --window-title MotionRunner-Expo --max-size 1080
timeout /t 2 >nul
python main.py
pause
