#!/bin/bash
# export SECRET_KEY="填入你的密钥"
# 启动 Gunicorn（单 worker，避免 session 丢失）
gunicorn -w 1 -b 127.0.0.1:5000 --timeout 600 server:app

