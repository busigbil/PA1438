#!/usr/bin/env bash
RUN_ID="$1"
OUTPUT_DIR="/data/metrics/${RUN_ID}"
mkdir -p "$OUTPUT_DIR"

OUTPUT_FILE="${OUTPUT_DIR}/cgroup_$(date +'%Y-%m-%d_%H-%M-%S').json"
CGROUP_DIR="/sys/fs/cgroup/"
stats=("cpu.stat" "cpu.pressure" "memory.pressure" "io.pressure" "io.stat" "memory.peak")

for stat in "${stats[@]}"
do
    if [[ "$stat" = "memory.peak" ]]
    then
        jq --arg stat_key "$stat" '{ ($stat_key): . }' "$CGROUP_DIR$stat"
    elif [[ "$stat" = "cpu.stat" ]]
    then
        jq -Rs --arg stat_key "$stat" '{ ($stat_key): split("\n") | map(select(length > 0) | split(" ") | { (.[0]): .[1] | tonumber }) | add }' "$CGROUP_DIR$stat"
    else
        jq -Rs --arg stat_key "$stat" '{ ($stat_key): split("\n") | map(select(length > 0) | split(" ") | { (.[0]): (.[1:] | map(split("=") | { (.[0]): .[1] | tonumber }) | add )  }) | add }' "$CGROUP_DIR$stat"
    fi
done | jq -s 'add' > $OUTPUT_FILE
