# Aetherion Picture Settings Manager

A self-hosted picture settings and calibration manager for AWOL Aetherion projectors, using Android Debug Bridge (ADB) and the projector's native picture settings service.

## Development status

**Pre-release development build.** The source can be built locally. The Docker Hub image is available. The current application provides persistent device configuration, a source-specific settings catalog, live ADB context checks and a picture mode scanner. Live adjustment and batch editing are not enabled.

Research on Aetherion MAX firmware `V0000.01.00U.Q1015 31` has established 53 accessible signal/profile combinations on one input, with successful batch updates of two-point RGB gains and color temperature. Compatibility with other firmware versions, inputs and models is not established.

A previous research scan reported 53 profiles, 89 general parameters per profile, and 101 indexed adjustment records per profile (10,070 records in total). This is a record count, not a guarantee that all values are writable or independently stored.

Implemented: Flask WebUI with GitHub-linked banner, saved device selection and endpoint editing, SQLite snapshots by device and source, categorized JSON import, indexed calibration browsing, live context and cancellable scanning. Planned: standalone parameter discovery, scan resume, individual profile editing, batch changes, backup management, change logs and WebUI wireless pairing.

## Requirements

- An AWOL Aetherion projector with working ADB access.
- A Docker host with Docker Engine and Docker Compose v2.
- Network connectivity from the Docker host/container to the projector's ADB endpoint.
- Wireless debugging enabled and ADB authorization completed on the projector.
- The actual debugging connection port, which may change after a reboot. The pairing port is not necessarily the connection port.

## Docker Compose

Download [compose.yaml](compose.yaml) and replace the three host volume paths. No .env file or ADB environment variables are required.

```yaml
services:
  aetherion-picture-settings-manager:
    image: lamb0985/aetherion-picture-settings-manager:latest
    container_name: aetherion-picture-settings-manager
    restart: unless-stopped
    ports:
      - "5055:5055"
    environment:
      TZ: America/New_York
    volumes:
      - /path/to/config:/config
      - /path/to/backups:/backups
      - /path/to/logs:/logs
```

| Configuration | Description |
| --- | --- |
| TZ | Timezone; defaults to America/New_York |
| 5055:5055 | Host and container WebUI ports |
| /config | Persistent SQLite database (apsm.db), legacy catalog and authorized ADB keys (.android) |
| /backups | Reserved persistent calibration backup directory |
| /logs | Reserved persistent application log directory |
| ADB_HOST / ADB_PORT | Optional legacy initialization variables; saved WebUI devices take precedence |

Deploy or update:

```sh
docker compose pull
docker compose up -d
```

Open `http://DOCKER_HOST:5055`. Enter a device name, IP address and ADB connection port in the device manager, then choose **Save & select** and **Connect / refresh**. The selected device and endpoint persist across container restarts. Add further devices using **New device**. Editing an existing device's port retains its saved snapshots.

For an existing deployment with valid ADB_HOST and ADB_PORT, the application initializes the first saved device from those values and attempts to migrate its legacy catalog.json. Keep the existing /config volume and authorized ADB keys. Do not delete the legacy catalog.

## ADB preparation

On the projector, enable developer options and wireless debugging where supported. If pairing is required, use the pairing address and code displayed by the projector with `adb pair HOST:PAIRING_PORT`. Connect using `adb connect HOST:ADB_PORT` and verify with `adb devices -l`. ADB credentials belong to the client that created them; the container will require its own authorized identity or an explicitly provisioned identity. The container stores its ADB identity under `/config/.android` via `HOME=/config`. After deploying the container, run `docker compose exec aetherion-picture-settings-manager adb pair HOST:PAIRING_PORT` if wireless debugging requires pairing. Then use Connect / refresh in the WebUI. A pairing code may be requested interactively. Do not expose the ADB server port.

## Safety and limitations

- Keep ADB and the WebUI on a trusted private network. Do not expose either directly to the internet.
- Back up calibration before writing settings.
- The native API is undocumented and firmware-dependent.
- Reading a parameter does not establish that it is writable, independently stored, or supported by every picture profile.
- Signal and profile switching can temporarily affect the displayed picture; do not run concurrent calibration tools or change inputs during a scan.
- Factory calibration and unidentified signal banks are outside the initial scope.
- This is an independent project, not an official AWOL product. Manufacturer APKs, proprietary native libraries, personal calibration data and authentication keys are not distributed here.

## Build from source (development)

Clone this repository, replace the host volume paths in compose.yaml, then run:

```sh
docker build -t lamb0985/aetherion-picture-settings-manager:latest .
docker compose up -d --pull never
```

Open the WebUI, save and select a device, and import a discovery scanner export using the JSON file chooser. The first scan currently requires this seed catalog. Select **Scan Current Picture Modes** to scan known signal/profile combinations on the active source. Progress and cancellation are available. A completed, validated scan replaces the SQLite snapshot for that device and source; an unsuccessful scan does not replace it. Select a stored source using the database source selector. Keep original exports separately.

The Connect / refresh button queries the selected device's current source, signal and picture mode without changing picture settings. The scanner temporarily writes signal, picture mode and calibration index selectors and attempts to restore them. Do not change source or restart the container during a scan. Restoration can fail if connectivity or source changes; check the reported status and verify the projector context manually in that case. The scanner has not yet been verified on physical hardware in this release.

The raw availability state and range tuple are retained rather than treated as universal write permissions or defaults. Menu labels in an imported snapshot reflect the scanner's mappings; firmware-specific menu variants may differ.

## Development tests

```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

CI runs the tests and attempts a Docker build. Physical projector connectivity and calibration writes require separate hardware verification.

