#!/bin/bash
export $(grep -v '^#' .env | xargs)
./venv/bin/python mcp_server.py
