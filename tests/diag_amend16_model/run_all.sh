#!/bin/bash
# Every variant of the model, each in a process of its own.  Usage: run_all.sh PYTHON
cd "$(dirname "$0")"; mkdir -p out; echo "start $(date -u +%FT%TZ)" > out/when.txt
for v in spec no_detection no_reread asked_is_enough no_lapse receipt_time carry_over names_new_only no_count_rule owner; do
  "$1" -B model.py $v >> out/model_run.txt 2>&1; echo "$v exit $? $(date -u +%T)" >> out/when.txt
done
echo "end $(date -u +%FT%TZ)" >> out/when.txt
