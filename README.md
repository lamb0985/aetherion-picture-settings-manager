# Aetherion Picture Settings Manager

A self-hosted picture settings and calibration manager for AWOL Aetherion projectors, using Android Debug Bridge (ADB) and the projector's native picture settings service.

## Development status

**Pre-release: not yet ready for deployment.** The Docker image has not been published. The application and settings catalog are under development.

Research on Aetherion MAX firmware `V0000.01.00U.Q1015 31` has established 53 accessible signal/profile combinations on one input, with successful batch updates of two-point RGB gains and color temperature. Compatibility with other firmware versions, inputs and models is not established.

Planned features include a Flask WebUI, individual profile editing, selective batch changes, indexed calibration, configuration backups, and change logs.

## Requirements

- An AWOL Aetherion projector with working ADB access.
- A Docker host with Docker Engine and Docker Compose v2.
- Network connectivity from the Docker host/container to the projector's ADB endpoint.
- Wireless debugging enabled and ADB authorization completed on the projector.
- The actual debugging connection port, which may change after a reboot. The pairing port is not necessarily the connection port.

## Docker Compose (planned deployment)

Once the image is published, download [compose.yaml](compose.yaml) and edit the placeholders directly. No .env file is required.

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
      ADB_HOST: YOUR_AETHERION_IP
      ADB_PORT: "YOUR_ADB_PORT"
    volumes:
      - /path/to/config:/config
      - /path/to/backups:/backups
      - /path/to/logs:/logs
```

| Configuration | Description |
| --- | --- |
| ADB_HOST | Projector IP address |
| ADB_PORT | Projector ADB connection port |
| TZ | Timezone; defaults to America/New_York |
| 5055:5055 | Host and container WebUI ports; change the host port if needed |
| /config | Persistent application configuration and planned ADB identity storage |
| /backups | Persistent calibration backups |
| /logs | Persistent application logs |

Replace all three host volume paths with writable directories on your Docker host. Keep the container-side paths unchanged.

After an image is available, deploy using:

```sh
docker compose up -d
docker compose logs -f
```

The planned WebUI address is `http://DOCKER_HOST:5055`.

## ADB preparation

On the projector, enable developer options and wireless debugging where supported. If pairing is required, use the pairing address and code displayed by the projector with `adb pair HOST:PAIRING_PORT`. Connect using `adb connect HOST:ADB_PORT` and verify with `adb devices -l`. ADB credentials belong to the client that created them; the container will require its own authorized identity or an explicitly provisioned identity. Container pairing instructions will be finalized when live ADB support is implemented.

## Safety and limitations

- Keep ADB and the WebUI on a trusted private network. Do not expose either directly to the internet.
- Back up calibration before writing settings.
- The native API is undocumented and firmware-dependent.
- Reading a parameter does not establish that it is writable, independently stored, or supported by every picture profile.
- Signal and profile switching can temporarily affect the displayed picture; do not run concurrent calibration tools or change inputs during a scan.
- Factory calibration and unidentified signal banks are outside the initial scope.
- This is an independent project, not an official AWOL product. Manufacturer APKs, proprietary native libraries, personal calibration data and authentication keys are not distributed here.
