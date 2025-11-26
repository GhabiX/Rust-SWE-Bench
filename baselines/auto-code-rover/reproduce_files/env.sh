#!/bin/bash
set -ex
apt-get update
apt-get install -y software-properties-common  && add-apt-repository ppa:deadsnakes/ppa -y  && apt-get update  && apt-get install -y python3.11 python3.11-venv python3.11-dev pip

python3.11 -m venv /workspace/rta-venv

source /workspace/rta-venv/bin/activate

python3.11 -m pip install langchain langchain-openai openai langchain_community loguru


# python3 /RTAgent/src/rta_main.py

