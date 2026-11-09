#!/usr/bin/env bash
RUN_ID="$1"
OUTPUT_DIR="/var/tmp/proc-stats/${RUN_ID}"
mkdir -p "$OUTPUT_DIR"

OUTPUT_FILE="${OUTPUT_DIR}/proc_$(date +'%Y-%m-%d_%H-%M-%S').json"
PROC_DIR="/proc/net/"
stats=("netstat" "snmp" "dev")

for stat in "${stats[@]}"
do
    if [[ "$stat" = "dev" ]]
    then
        awk -F"|" '
        NR == 1 {
            gsub(/^[ \t]+|[ \t]+$/, "", $2)
            gsub(/^[ \t]+/, "", $3)
            direction["receive"] = $2
            direction["transmit"] = $3
            next
        }
        NR == 2 {
            split($2, receive_fields, " ")
            split($3, transmit_fields, " ")
            next
        }
        NR > 2 {
            FS = ":"

            gsub(/^[[:space:]]+/,"")
            split($2, value_fields, " ")

            receive_len = length(receive_fields)

            for (i = 1; i <= receive_len; i++) {
                print  $1 "\t" direction["receive"] "\t" receive_fields[i] "\t" value_fields[i]
            }

            transmit_start = receive_len + 1
            transmit_len = length(transmit_fields)

            for (i = 1; i <= transmit_len; i++ ) {
                print $1 "\t" direction["transmit"] "\t" transmit_fields[i] "\t" value_fields[transmit_start]
                transmit_start++
            }
        }
        ' "$PROC_DIR$stat" |
        jq -Rs --arg stat_key "$stat" '{ ($stat_key): split("\n") | map(select(length > 0) | split("\t")) | group_by(.[0]) | map( {(.[0][0]): group_by(.[1]) | map( {(.[0][1]): (map({(.[2]): .[3] | tonumber }) | add) }) | add }) | add } '
    else
        awk -F: '
        !($1 in headers) {headers[$1] = $2; next}
        {
            split(headers[$1], header_fields, " ")
            split($2, value_fields, " ")
            for (i = 1; i <= length(header_fields); i++) {
                print $1 "\t" header_fields[i] "\t" value_fields[i]

            }
        }
        ' "$PROC_DIR$stat" |
        jq -Rs --arg stat_key "$stat" '{ ($stat_key): split("\n") | map(select(length > 0) | split("\t")) | group_by(.[0]) | map( {(.[0][0]): (map({ (.[1]): .[2] | tonumber}) | add ) }) | add }'

    fi
done | jq -s 'add' > $OUTPUT_FILE
