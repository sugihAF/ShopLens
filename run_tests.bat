@echo off
cd /d D:\Codes\ShopLens\app\api
python -m pytest tests/test_gather.py -v --tb=short
pause
