#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
uvicorn backend.main:app --reload --port 8000
