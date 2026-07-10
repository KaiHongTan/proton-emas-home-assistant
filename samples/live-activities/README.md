# Charging Live Activity (iOS)

A Home Assistant automation and helper script that displays a **Live Activity** on your
iPhone while your Proton e.MAS is charging — showing battery level, charge power, and
estimated time remaining.

## What you get

- A persistent lock-screen and Dynamic Island widget during charging
- Displays current SoC, AC or DC charge power (kW), and a countdown timer
- Automatically starts when `charger_connected` turns on and DC charge current exceeds 5 A
- Clears when charging completes (SoC ≥ 99%) or is interrupted

## How it works

The automation in `ev-charging.yaml` triggers on state changes of the integration's
charging sensors (`charge_current`, `dc_charge_current`, `time_to_fully_charged`,
`battery_level`) and uses a `notify.mobile_app_*` action with the `live_activity` key
available in the [Home Assistant Companion app for iOS](https://companion.home-assistant.io/).

## Setup

1. Install the Companion app on your iPhone and configure push notifications.

2. In `ev-charging.yaml`, replace `REPLACEME` with your phone's mobile app device name:
   ```yaml
   mobile_app_iphone: notify.mobile_app_iphone  # find yours in Developer Tools → Services → Notifications
   ```

3. Update the entity `variables:` section to match your integration entity names. The default
   prefix `e_mas_7` should be changed to `YOUR_DEVICE_ENTITY_PREFIX` as shown in your HA.

4. Copy the automation YAML into HA (Settings → Automations & Scenes → ⋮ → Paste YAML).

## Testing without a real charging session

Use `mock-charging.sh` to simulate charging states and verify the Live Activity triggers:

```bash
chmod +x mock-charging.sh
export HA_URL="http://homeassistant.local:8123"
export HA_TOKEN="YOUR_LONG_LIVED_ACCESS_TOKEN"

./mock-charging.sh start     # simulate charging at 45%
./mock-charging.sh bump      # increment SoC by 1%
./mock-charging.sh complete  # simulate reaching 100%
./mock-charging.sh unplug    # clear the Live Activity
```

> Disable the Proton e.MAS integration entry while testing with `mock-charging.sh` so real
> polling doesn't overwrite the simulated states.

## Caveats

- The Companion app must have an active push notification connection (open the app at least
  once after HA restart).
- Live Activities have platform limitations — the activity may be replaced by iOS in some
  situations (e.g. another app's Live Activity or system alerts).
- `time_to_fully_charged` is **disabled by default** in the integration. Enable it in
  Settings → Devices & Services → Proton e.MAS → Entities.
