#!/bin/bash
#
# Nazi Zombies: Portable
# Output Matching Test for NSZ generation.
# Designed to run in Ubuntu 24.04 Docker container.
#
set -o errexit
set -o xtrace

PYTHON_PATH=$(which python3)
MD5_PATH=$(which md5sum)
OUTPUT_PATH="/tmp"
REPO_ROOT=$(dirname "${BASH_SOURCE[0]}")/../
cd "${REPO_ROOT}"

#
# run_output_matching_test()
# ----
# Actual test logic.
#
function run_output_matching_test()
{
    local had_failure="0"

    # Iterate through every map file..
    while read -r map_file; do
        local pretty_name=$(basename ${map_file} .map)
        ${PYTHON_PATH} spawn_zone_tool.py "tests/maps/${pretty_name}.map" --output "${OUTPUT_PATH}/${pretty_name}.nsz"

        if [[ $(${MD5_PATH} "tests/nszs/${pretty_name}.nsz" "${OUTPUT_PATH}/${pretty_name}.nsz" | awk '{print $1}' | uniq | wc -l) == 1 ]]; then
            echo "[INFO]: [${pretty_name}] PASS"
        else
            echo "[ERROR]: [${pretty_name}] FAIL"
            had_failure="1"
        fi
    done < <(find tests/maps/ -type f -name "*.map")

    if [[ "${had_failure}" != "0" ]]; then
        exit 1
    fi
}

#
# main()
# ----
# Entry point.
#
function main()
{
    run_output_matching_test;
    echo "[INFO]: Done! :)"
}

main;