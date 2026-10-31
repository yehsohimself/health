#!/bin/bash
# Double-click to open Health. Starts the local server if it is not running.
cd "$(dirname "$0")"
if ! curl -s -o /dev/null http://127.0.0.1:8771/; then
  nohup .venv/bin/python pt_sunucu.py > pt.log 2>&1 &
  for i in $(seq 1 30); do sleep 0.5; curl -s -o /dev/null http://127.0.0.1:8771/ && break; done
fi
open http://127.0.0.1:8771/
