#!/usr/bin/env bash
set -euo pipefail

HOST=""
PORTS="443,5671,8883"
COMMAND=""
CONDITION="normal"
COMMENT="edge-study-cloud-outage"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      HOST="$2"
      shift 2
      ;;
    --ports)
      PORTS="$2"
      shift 2
      ;;
    show|apply|clear)
      COMMAND="$1"
      shift
      ;;
    --condition)
      CONDITION="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [[ -z "$COMMAND" ]]; then
  echo "Usage: $0 --host <iot-hub-host> [--ports 443,5671,8883] show|clear|apply --condition <condition>" >&2
  exit 2
fi

default_iface() {
  ip route show default | awk '{print $5; exit}'
}

resolve_ips() {
  if [[ -z "$HOST" ]]; then
    return
  fi
  getent ahostsv4 "$HOST" | awk '{print $1}' | sort -u
}

iface_for_host() {
  local first_ip
  first_ip="$(resolve_ips | head -n 1 || true)"
  if [[ -z "$first_ip" ]]; then
    default_iface
  else
    ip route get "$first_ip" | awk '{for(i=1;i<=NF;i++){if($i=="dev"){print $(i+1); exit}}}'
  fi
}

clear_rules() {
  local iface="$1"
  sudo tc qdisc del dev "$iface" root 2>/dev/null || true
  while sudo iptables -S OUTPUT | grep -q "$COMMENT"; do
    local rule
    rule="$(sudo iptables -S OUTPUT | grep "$COMMENT" | head -n 1 | sed 's/^-A OUTPUT /-D OUTPUT /')"
    sudo iptables $rule
  done
}

show_rules() {
  local iface="$1"
  echo "# interface: $iface"
  sudo tc qdisc show dev "$iface" || true
  sudo tc filter show dev "$iface" || true
  sudo iptables -S OUTPUT | grep "$COMMENT" || true
}

apply_netem() {
  local iface="$1"
  local netem_args="$2"
  clear_rules "$iface"
  sudo tc qdisc replace dev "$iface" root handle 1: prio
  sudo tc qdisc replace dev "$iface" parent 1:3 handle 30: netem $netem_args
  IFS=',' read -ra port_array <<< "$PORTS"
  for ip in $(resolve_ips); do
    for port in "${port_array[@]}"; do
      sudo tc filter add dev "$iface" protocol ip parent 1:0 prio 3 u32 \
        match ip dst "$ip"/32 \
        match ip protocol 6 0xff \
        match ip dport "$port" 0xffff \
        flowid 1:3
    done
  done
}

apply_outage() {
  local iface="$1"
  clear_rules "$iface"
  IFS=',' read -ra port_array <<< "$PORTS"
  for ip in $(resolve_ips); do
    for port in "${port_array[@]}"; do
      sudo iptables -A OUTPUT -p tcp -d "$ip" --dport "$port" -m comment --comment "$COMMENT" -j DROP
    done
  done
}

IFACE="$(iface_for_host)"
case "$COMMAND" in
  show)
    show_rules "$IFACE"
    ;;
  clear)
    clear_rules "$IFACE"
    show_rules "$IFACE"
    ;;
  apply)
    case "$CONDITION" in
      delay_200ms)
        apply_netem "$IFACE" "delay 200ms"
        ;;
      packet_loss_*)
        LOSS="${CONDITION#packet_loss_}"
        apply_netem "$IFACE" "loss ${LOSS}%"
        ;;
      cloud_outage_block)
        apply_outage "$IFACE"
        ;;
      *)
        echo "Unsupported condition: $CONDITION" >&2
        exit 2
        ;;
    esac
    show_rules "$IFACE"
    ;;
esac
