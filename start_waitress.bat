@echo off
title Waitress Server - Wanderers Web
cd /d c:\wanderers_web

REM Start the default Waitress server
waitress-serve --host=0.0.0.0 --port=8181 --threads=30 --backlog=2048 --recv-bytes=16384 --send-bytes=32768 run:app > NUL 2>&1

REM Use this command to enable login:
REM waitress-serve --host=0.0.0.0 --port=8181 --threads=12 --backlog=2048 --recv-bytes=16384 --send-bytes=32768 run:app
