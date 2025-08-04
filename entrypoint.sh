#!/bin/bash
set -e

echo ">> Generating lookup data..."
python generate_lookup_and_update_nlu.py

echo ">> Training Rasa model..."
rasa train

echo ">> Starting Supervisor..."
exec supervisord -c supervisord.conf