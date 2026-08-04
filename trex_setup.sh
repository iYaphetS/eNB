#!/usr/bin/env bash
set -euo pipefail

version=v3.08
project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
default_home="$project_dir/.tools/trex/$version"
trex_home=${TREX_HOME:-$default_home}

check_home() {
    local path=$1
    local name
    for name in t-rex-64 trex-console dpdk_setup_ports.py; do
        if [[ ! -x "$path/$name" ]]; then
            echo "TRex $version not found at $path" >&2
            echo "Run: $0 install" >&2
            return 1
        fi
    done
    echo "TRex ready: $path"
}

case ${1:-check} in
    check)
        check_home "$trex_home"
        ;;
    install)
        if [[ -e "$trex_home" ]]; then
            check_home "$trex_home"
            exit
        fi
        command -v curl >/dev/null || { echo 'curl is required' >&2; exit 1; }
        command -v tar >/dev/null || { echo 'tar is required' >&2; exit 1; }
        archive=$(mktemp --suffix=.tar.gz)
        trap 'rm -f "$archive"' EXIT
        mkdir -p "$(dirname -- "$trex_home")"
        curl --fail --location --output "$archive" \
            "https://trex-tgn.cisco.com/trex/release/$version.tar.gz"
        tar -xzf "$archive" -C "$(dirname -- "$trex_home")"
        check_home "$trex_home"
        printf 'Run: export TREX_HOME=%q\n' "$trex_home"
        ;;
    *)
        echo "usage: $0 [check|install]" >&2
        exit 2
        ;;
esac
