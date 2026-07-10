#!/bin/bash
# Mock a Proton e.MAS charging session by setting entity states via the HA REST API.
#
# Usage:
#   ./mock-charging.sh start     — simulate AC charging at 45% SoC, 5.5 kW, 120 min remaining
#   ./mock-charging.sh bump      — increment SoC by 1% (triggers an update push)
#   ./mock-charging.sh complete  — simulate charging complete (dc drops, SoC = 100%, ttf = 0)
#   ./mock-charging.sh stop      — simulate charge interruption (dc drops, SoC stays low, clears activity)
#   ./mock-charging.sh unplug    — simulate unplug (charger_connected off, clears immediately)
#
# Prerequisites:
#   - A long-lived access token: HA Profile → Long-Lived Access Tokens → Create Token
#   - Set HA_URL and HA_TOKEN env vars (or edit the defaults below):
#
#       export HA_URL="http://192.168.x.x:8123"
#       export HA_TOKEN="ey..."
#
#   - Make executable: chmod +x mock-charging.sh
#
# Note: Manually set states persist until the next real poll from the integration
# (default ~120 s). Disable the Proton e.MAS config entry for uninterrupted testing.

HA_URL="${HA_URL:-http://homeassistant.local:8123}"
HA_TOKEN="${HA_TOKEN:-YOUR_LONG_LIVED_ACCESS_TOKEN}"

ENTITY_PREFIX="e_mas_7"

set_state() {
  local entity_id="$1"
  local state="$2"
  local resp
  resp=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
    "${HA_URL}/api/states/${entity_id}" \
    -H "Authorization: Bearer ${HA_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{\"state\": \"${state}\"}" 2>&1)
  if [ "$resp" = "200" ] || [ "$resp" = "201" ]; then
    printf "  %-55s = %s\n" "$entity_id" "$state"
  else
    printf "  %-55s = FAIL (HTTP %s)\n" "$entity_id" "$resp"
  fi
}

get_state() {
  curl -s "${HA_URL}/api/states/$1" \
    -H "Authorization: Bearer ${HA_TOKEN}" \
    2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin)['state'])" 2>/dev/null
}

case "${1:-}" in
  start)
    echo "Mocking AC charging session (45% SoC, ~5.5 kW, 120 min remaining)..."
    set_state "binary_sensor.${ENTITY_PREFIX}_charger_connected" "on"
    set_state "sensor.${ENTITY_PREFIX}_battery_level" "45"
    set_state "sensor.${ENTITY_PREFIX}_charge_current" "23.5"
    set_state "sensor.${ENTITY_PREFIX}_charge_voltage" "234"
    set_state "sensor.${ENTITY_PREFIX}_dc_charge_current" "12.5"
    set_state "sensor.${ENTITY_PREFIX}_dc_charge_voltage" "393"
    set_state "sensor.${ENTITY_PREFIX}_time_to_fully_charged" "120"
    echo ""
    echo "Live Activity should appear on your phone within ~5s."
    echo "Run './mock-charging.sh bump' to simulate SoC increasing."
    ;;

  bump)
    current=$(get_state "sensor.${ENTITY_PREFIX}_battery_level")
    if [ -z "$current" ] || [ "$current" = "None" ]; then
      echo "ERROR: can't read current battery_level. Check HA_URL/HA_TOKEN."
      exit 1
    fi
    new=$(python3 -c "print(min(round(float('$current')+1, 1), 100.0))")
    echo "Bumping SoC: ${current}% -> ${new}%"
    set_state "sensor.${ENTITY_PREFIX}_battery_level" "$new"
    if python3 -c "exit(0 if float('$new') >= 99.0 else 1)"; then
      set_state "sensor.${ENTITY_PREFIX}_time_to_fully_charged" "0"
      echo "SoC >= 99%, also cleared ttf to trigger 'Charging Complete' evaluation."
    fi
    echo "Update should push to the Live Activity within ~5s."
    ;;

  complete)
    echo "Mocking charging complete (dc drops, SoC = 100%, ttf = 0)..."
    set_state "sensor.${ENTITY_PREFIX}_charge_current" "0.0"
    set_state "sensor.${ENTITY_PREFIX}_charge_voltage" "0.0"
    set_state "sensor.${ENTITY_PREFIX}_dc_charge_current" "0.4"
    set_state "sensor.${ENTITY_PREFIX}_time_to_fully_charged" "0"
    set_state "sensor.${ENTITY_PREFIX}_battery_level" "100"
    echo ""
    echo "Live Activity should show 'Charging Complete · 100%' within ~5s."
    echo "Run './mock-charging.sh unplug' to clear it."
    ;;

  stop)
    echo "Mocking charge interruption (currents drop, SoC unchanged, clears activity)..."
    set_state "sensor.${ENTITY_PREFIX}_charge_current" "0.0"
    set_state "sensor.${ENTITY_PREFIX}_charge_voltage" "0.0"
    set_state "sensor.${ENTITY_PREFIX}_dc_charge_current" "0.4"
    set_state "sensor.${ENTITY_PREFIX}_time_to_fully_charged" "0"
    echo ""
    echo "Live Activity should clear within ~5s (SoC < 99 → interrupted, not complete)."
    echo "For 'Charging Complete' instead, run './mock-charging.sh complete'."
    ;;

  unplug)
    echo "Mocking unplug (charger_connected -> off)..."
    set_state "binary_sensor.${ENTITY_PREFIX}_charger_connected" "off"
    echo ""
    echo "Live Activity should clear within ~5s."
    ;;

  *)
    echo "Usage: $0 {start|bump|complete|stop|unplug}"
    echo ""
    echo "  start     — simulate AC charging (45% SoC, 5.5 kW, 120 min remaining)"
    echo "  bump      — increment SoC by 1% (triggers a Live Activity update)"
    echo "  complete  — simulate charging complete (SoC = 100%, shows 'Charging Complete')"
    echo "  stop      — simulate charge interruption (SoC unchanged, clears activity)"
    echo "  unplug    — simulate unplug (charger_connected -> off, clears immediately)"
    exit 1
    ;;
esac
