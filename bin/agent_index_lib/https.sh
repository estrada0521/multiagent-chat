#!/usr/bin/env bash

set -euo pipefail

if [[ -n "${AGENT_INDEX_HTTPS_SH:-}" ]]; then
  return 0
fi
AGENT_INDEX_HTTPS_SH=1

detect_local_ip() {
  python3 - <<'PYEOF'
import socket

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
try:
    sock.connect(("8.8.8.8", 80))
    print(sock.getsockname()[0])
except OSError:
    pass
finally:
    sock.close()
PYEOF
}

detect_local_host_name() {
  local local_name=""
  if command -v scutil >/dev/null 2>&1; then
    local_name="$(scutil --get LocalHostName 2>/dev/null || true)"
  fi
  if [[ -z "$local_name" ]]; then
    local_name="$(hostname 2>/dev/null || true)"
    local_name="${local_name%%.*}"
  fi
  printf '%s\n' "$local_name"
}

read_local_https_extra_names() {
  local extra_names_file="${AGENT_WINDOW_CERTS_DIR:-$HOME/.agent-window/state/certs}/local-https-extra-names.txt"
  local line=""
  [[ -f "$extra_names_file" ]] || return 0
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%%#*}"
    line="${line//$'\r'/}"
    line="$(printf '%s' "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    [[ -n "$line" ]] || continue
    printf '%s\n' "$line"
  done < "$extra_names_file"
}

cert_has_san_entry() {
  local cert_file="$1"
  local san_kind="$2"
  local san_value="$3"
  python3 - "$cert_file" "$san_kind" "$san_value" <<'PYEOF'
import ipaddress
import ssl
import sys

cert_file, san_kind, san_value = sys.argv[1:4]
try:
    decoded = ssl._ssl._test_decode_cert(cert_file)
except Exception:
    sys.exit(1)

for entry_kind, entry_value in decoded.get("subjectAltName", ()):
    if entry_kind != san_kind:
        continue
    if san_kind == "IP Address":
        try:
            if ipaddress.ip_address(entry_value) == ipaddress.ip_address(san_value):
                sys.exit(0)
        except ValueError:
            pass
        continue
    if entry_value == san_value:
        sys.exit(0)
sys.exit(1)
PYEOF
}

ensure_repo_https_cert() {
  local cert_dir="${AGENT_WINDOW_CERTS_DIR:-$HOME/.agent-window/state/certs}"
  local cert_file="$cert_dir/cert.pem"
  local key_file="$cert_dir/key.pem"
  local archive_dir="$cert_dir/archive"
  local current_ip local_name ts
  local required_missing=0
  local names=()
  local extra_name=""
  local name

  command -v mkcert >/dev/null 2>&1 || return 0

  current_ip="$(detect_local_ip || true)"
  local_name="$(detect_local_host_name)"

  names=("localhost" "127.0.0.1" "::1")
  [[ -n "$current_ip" ]] && names+=("$current_ip")
  if [[ -n "$local_name" ]]; then
    names+=("$local_name")
    [[ "$local_name" != *.local ]] && names+=("${local_name}.local")
  fi
  while IFS= read -r extra_name; do
    [[ -n "$extra_name" ]] || continue
    names+=("$extra_name")
  done < <(read_local_https_extra_names)

  if [[ -f "$cert_file" && -f "$key_file" ]]; then
    for name in "${names[@]}"; do
      if [[ "$name" == *:* || "$name" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        cert_has_san_entry "$cert_file" "IP Address" "$name" || required_missing=1
      else
        cert_has_san_entry "$cert_file" "DNS" "$name" || required_missing=1
      fi
      [[ "$required_missing" -eq 0 ]] || break
    done
  else
    required_missing=1
  fi

  if [[ "$required_missing" -eq 1 ]]; then
    mkdir -p "$cert_dir"
    mkdir -p "$archive_dir"
    ts="$(date +%Y%m%d-%H%M%S)"
    [[ -f "$cert_file" ]] && cp "$cert_file" "$archive_dir/cert.pem.${ts}"
    [[ -f "$key_file" ]] && cp "$key_file" "$archive_dir/key.pem.${ts}"
    mkcert -cert-file "$cert_file" -key-file "$key_file" "${names[@]}" >/dev/null
  fi

  if [[ -f "$cert_file" && -f "$key_file" ]]; then
    export MULTIAGENT_CERT_FILE="$cert_file"
    export MULTIAGENT_KEY_FILE="$key_file"
  fi
}

port_serves_expected_url() {
  local scheme="$1"
  local port="$2"
  local path="$3"
  python3 - "$scheme" "$port" "$path" <<'PYEOF'
import http.client
import ssl
import sys

scheme = sys.argv[1]
port = int(sys.argv[2])
path = sys.argv[3]

try:
    if scheme == "https":
        conn = http.client.HTTPSConnection(
            "127.0.0.1",
            port,
            timeout=1.2,
            context=ssl._create_unverified_context(),
        )
    else:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=1.2)
    conn.request("GET", path, headers={"Host": f"127.0.0.1:{port}"})
    resp = conn.getresponse()
    resp.read(1)
    conn.close()
    if 200 <= resp.status < 500:
        sys.exit(0)
except Exception:
    pass
sys.exit(1)
PYEOF
}

list_listening_pids() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -nP -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true
    return 0
  fi
  if command -v fuser >/dev/null 2>&1; then
    fuser "$port"/tcp 2>/dev/null | tr ' ' '\n' | sed '/^$/d' || true
    return 0
  fi
  return 0
}

pid_listens_on_port() {
  local pid="$1"
  local port="$2"
  [[ -n "$pid" && -n "$port" ]] || return 1
  if command -v lsof >/dev/null 2>&1; then
    lsof -nP -a -p "$pid" -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
    return $?
  fi
  local seen
  seen="$(list_listening_pids "$port" | tr '\n' ' ')"
  [[ " $seen " == *" $pid "* ]]
}

wait_for_port_to_clear() {
  local port="$1"
  local attempts="${2:-50}"
  local delay="${3:-0.1}"
  local listeners
  local i
  for i in $(seq 1 "$attempts"); do
    listeners="$(list_listening_pids "$port")"
    if [[ -z "${listeners//[[:space:]]/}" ]]; then
      return 0
    fi
    sleep "$delay"
  done
  return 1
}
