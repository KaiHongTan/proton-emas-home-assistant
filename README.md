# Proton e.MAS for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Home Assistant custom integration that connects to the **Proton e.MAS** cloud API — the same
endpoints used by the official Proton e.MAS mobile app — to poll vehicle telemetry and issue
remote commands (door locks, climate preconditioning, seat ventilation, window vent mode).

## ⚠️ Important Disclaimer

- This integration communicates with **undocumented, reverse-engineered cloud endpoints** that
  are not part of any public API. They may change or be shut down at any time without notice.

- You use a **Bearer token intercepted from the official mobile app**. Sharing the same
  authentication session with the app is **required** — the cloud backend only allows **one
  active login session per account**. If you attempt to log in separately (e.g. with username
  and password), the mobile app will be logged out, and vice versa.

- Tokens **expire approximately every 30 days** (or whenever you re-login on the mobile app).
  When that happens the integration will show an authentication error and you must repeat the
  token-capture process to obtain a fresh Bearer token.

- Remote control features (unlock, climate, vent windows) can affect your vehicle's physical
  state. **Use with caution**, especially on public roads or in confined spaces.

- There is a **theoretical risk** that Proton may detect non-app usage patterns and block your
  account, device, or VIN from accessing the cloud API. This has not been reported but cannot
  be ruled out.

- **You are responsible** for securing your Home Assistant instance (updates, MFA, backups, HTTPS)
  since the Bearer token grants the same vehicle-control privileges as the mobile app.

## Compatible Vehicles

| Model | Status |
|-------|--------|
| **Proton e.MAS 7 (BEV)** | Verified & working |
| **Proton e.MAS 5** | In development — not yet tested |
| **Proton e.MAS 7 (PHEV)** | In development — not yet tested |

Contributions of captured API traffic from e.MAS 5 or e.MAS 7 PHEV users are welcome to help
extend compatibility.

## Installation

### Option 1: HACS (one-click)

If you have [HACS](https://hacs.xyz/) installed:

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=KaiHongTan&repository=proton-emas-home-assistant&category=integration)

Or add this repository manually in HACS:
1. **HACS → Integrations → ⋮ (menu) → Custom repositories**
2. Paste `https://github.com/KaiHongTan/proton-emas-home-assistant` and select **Integration**
3. Click **Add**, find "Proton e.MAS", install, and restart Home Assistant

### Option 2: Manual installation

1. Copy the folder `custom_components/proton_emas/` from this repo into your Home Assistant
   `config/custom_components/` directory.
2. Restart Home Assistant.
3. Go to **Settings → Devices & services → Add Integration → Proton e.MAS**.

> **"Invalid handler specified" after manual install?**  
> This integration requires Home Assistant **2026.4.0 or later**. If you're on an older
> version, update HA first.

## Getting Your VIN & Bearer Token

Both values must be captured from the official Proton e.MAS mobile app using an HTTPS proxy.
**This is required because only one active session is allowed per account** — you cannot log
in separately without kicking the mobile app out.

### Prerequisites

- A Mac or PC running an HTTPS debugging proxy:
  - **Proxyman** (macOS, recommended — free tier is sufficient)
  - **mitmproxy** (cross-platform, open source)
  - **Charles Proxy** (cross-platform, paid)
- Your iPhone or Android phone on the same Wi-Fi network

### Step-by-step (Proxyman on macOS)

1. **Install Proxyman** from [proxyman.io](https://proxyman.io/). The free version works for
   one-time capture.

2. **Enable HTTPS decryption** — Proxyman prompts you to install its root CA certificate on
   first launch. Follow the setup wizard.

3. **Configure your phone's proxy:**
   - Open Proxyman, note your Mac's IP and the proxy port (shown in the toolbar, typically `9090`).
   - On your phone: **Settings → Wi-Fi → tap the ⓘ on your network → Configure Proxy → Manual**.
   - Set **Server** to your Mac's IP address, **Port** to `9090`.
   - **Save**.

4. **Install the Proxyman CA certificate on your phone:**
   - Open Safari on your phone, go to `http://proxy.man/ssl` (Proxyman shows this URL).
   - Download and install the certificate profile.
   - On iOS: **Settings → General → About → Certificate Trust Settings** — enable full trust
     for the Proxyman CA.
   - On Android: **Settings → Security → Trusted credentials → Install from storage** — select
     the downloaded certificate.

5. **Capture the traffic:**
   - Ensure the Proton e.MAS app is logged in and working normally.
   - Open Proxyman and start a new session (⌘K to clear old traffic, ⌘R to start recording).
   - On your phone, open the Proton e.MAS app, let it refresh the vehicle status.
   - In Proxyman, find requests to `emas-app.acotech.my:8443`.

6. **Extract the credentials:**
   - Click any request to `emas-app.acotech.my:8443` in the left panel.
   - In the **Request** tab, copy the **Authorization** header value (everything after `Bearer `) — this is your **Bearer token**.
   - In the **Body** tab, find the `"vin"` field — copy this value. It is a 17-character
     identifier like `L6TE21SB0XX000001`.

7. **Clean up:**
   - Disable the Wi-Fi proxy on your phone.
   - Optionally remove the Proxyman CA certificate from your phone's trust store.

### Important: token lifecycle

- The captured token is the **exact same session** your mobile app uses. As long as the app
  stays logged in, the token works. If you log out of the app, or log in on another device,
  the captured token stops working.
- Tokens expire approximately **every 30 days**. The integration will show an authentication
  error (unreachable or 401). You must repeat the capture process to get a fresh token.
- **Re-authentication in Home Assistant:** go to the integration entry → **Configure** →
  choose **Re-authenticate** (or **Update token** on newer HA versions) → paste the new
  Bearer token.

## Configuration

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| VIN | Yes | — | 17-character vehicle identification number |
| Bearer Token | Yes | — | JWT captured from the mobile app |
| Name | No | `Proton e.MAS XXXXXX` | Friendly name for the device |
| Poll interval | No | `120` | Seconds between status polls (30–3600) |

Advanced options (available after setup via **Configure**) allow overriding the API base URL,
tenant/client IDs, and app version strings — useful if the mobile app updates its headers.

## Entities

Each vehicle creates one **Device** in Home Assistant with the following entities:

### Sensors (battery, range, diagnostics)
- Battery level (HV traction pack, %)
- 12V battery level (%)
- HV voltage (V)
- Range — battery only, at 100% SoC, distance to empty (km)
- Average / trip power consumption (kWh/100km)
- Trip average fuel consumption
- DC charge current/voltage, charge current/voltage, discharge current/voltage
- Exterior / interior temperature (°C)
- Interior PM2.5 (µg/m³)
- Speed, average speed (km/h)
- Odometer (km)
- Altitude (m), heading (°)
- Tyre pressures (kPa) & temperatures (°C) — all four wheels
- Days to service, distance to service
- Time to fully charged / time to target discharged (min) — **disabled by default**
- ECU warnings & extra warnings (raw JSON) — **disabled by default**
- Diagnostic: usage mode, power source, power mode, fuel type, gear auto status
- Diagnostic: latitude, longitude, vent details, telemetry timestamps
- Charging state (AC/DC charging, completed, stopped, error, …) — created only if your
  vehicle reports `chargerState`
- Charging power (W), computed from charge voltage × charge current
- Telemetry timestamp (when the car last reported) and token expiry (from the JWT)
- Diagnostic raw values for fields still being validated: central locking, charge-port lid,
  scheduled-charge status, charging start time

### Binary Sensors
- Pre-climate active, defrost active, air blower active
- Engine running, charger connected, GPS trusted
- Door open (LF, RF, LR, RR), trunk open, hood open, sunroof open
- Seatbelt (driver, passenger, driver rear, passenger rear)
- Charging, tyre pressure/temperature warnings (created only if reported)

### Controls
| Type | Name | Description |
|------|------|-------------|
| Lock | Door locks | Remote unlock (`RDU-ON`) / lock (`RDL-OFF`) |
| Switch | Remote climate | Cabin preconditioning (uses temperature & duration numbers below) |
| Switch | Driver seat ventilation | Toggle driver seat vent fan |
| Switch | Passenger seat ventilation | Toggle passenger seat vent fan |
| Switch | Window vent | Breathable / crack mode for all windows |
| Switch | Charging | Start (`RCS-ChargingStart`) / stop (`RCS-ChargingStop`) charging; unavailable when unplugged |
| Number | Remote climate temperature | Target °C for remote climate (16–30) |
| Number | Remote climate duration | Minutes remote climate stays on (5–30) |
| Button | Refresh status | Immediate cloud poll |
| Button | Horn and lights | `RHL-HornAndLight` |
| Button | Flash lights | `RHL-LIGHT` |

The door lock shows **locking / unlocking** until telemetry confirms the change. Commands
are sent one at a time, and failures show the backend's error message.

### Device Tracker
- Vehicle GPS location (latitude/longitude) — only reported when `posCanBeTrusted` is `true`.

## Services

### `proton_emas.refresh_vehicle`

Immediate status poll. Omit `vin` to refresh all configured vehicles.

```yaml
service: proton_emas.refresh_vehicle
data:
  vin: "YOUR_VIN"
```

### `proton_emas.remote_climate_start`

Start preconditioning with explicit temperature and duration.

```yaml
service: proton_emas.remote_climate_start
data:
  vin: "YOUR_VIN"
  temperature: 22
  duration: 15
```

## iOS Live Activity (Charging)

See [`samples/live-activities/`](samples/live-activities/) for a companion Home Assistant
automation that displays a charging Live Activity on your iPhone — showing battery level,
charge power, and estimated time remaining, using the integration's charging sensors.

## Token expiry and diagnostics

A **Token expires** sensor shows when the token expires (its `loginTime` plus `timeout`,
30 days after you logged in to the app), and a repair issue appears 3 days before. When the token is rejected, Home Assistant prompts you to
re-authenticate automatically.

**Settings → Devices & services → Proton e.MAS → ⋮ → Download diagnostics** produces a
redacted status dump (token, VIN and coordinates removed). Attaching one to an issue is
the easiest way to help add support for e.MAS 5 / PHEV.

## Troubleshooting

**"Invalid authentication" during setup?**  
The token has expired or was captured incorrectly. Repeat the Proxyman capture process
(step-by-step above) with the mobile app freshly logged in.

**Vehicle unreachable or polling fails after working for weeks?**  
The token likely expired (~30 day cycle). Go to the integration → **Configure** →
**Re-authenticate** with a fresh token.

**Mobile app says "logged out on another device"?**  
Normal — the cloud backend allows only one session. Re-log into the mobile app, then
re-capture the new token for Home Assistant.

## Development

```bash
python3 -m compileall custom_components/proton_emas
pip install -r requirements_test.txt
pytest
```

Contributions, bug reports, and captured API payloads for untested vehicle models are welcome.
