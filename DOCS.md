# MERALCO Electricity Rates Add-on

This add-on parses MERALCO's official residential bills PDF every month and exposes the per-kWh rates to Home Assistant. Pick one of two modes:

- `mqtt` (default): Sensors appear automatically in Home Assistant via MQTT discovery. Requires the Mosquitto broker add-on (or any MQTT broker registered with the Supervisor).
- `rest`: The add-on runs a REST API on port 5000. Add `rest:` sensors to `configuration.yaml` to consume them.

## Installation

1. In Home Assistant, go to Settings, then Add-ons, then Add-on store.
2. Open the menu in the top-right corner and choose Repositories.
3. Add `https://github.com/rairulyle/meralco-ph` and click Add.
4. Find MERALCO Electricity Rates in the store and install it.
5. Configure the options below, then start the add-on.

## Options

| Option                  | Default         | Description                                                                                                                                                           |
| ----------------------- | --------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `mode`                  | `mqtt`          | Either `mqtt` (auto-publish sensors via discovery) or `rest` (run the REST API on port 5000).                                                                         |
| `log_level`             | `info`          | Logging verbosity. One of: `trace`, `debug`, `info`, `notice`, `warning`, `error`, `fatal`.                                                                           |
| `scan_interval`         | `86400` (1 day) | How often to re-publish state to MQTT, in seconds. Range: 3600 to 604800. The PDF source only changes monthly, so anything finer is wasted. Used in `mqtt` mode only. |
| `kwh_levels`            | `[200]`         | Which consumption levels to expose as sensors. Valid: 50, 70, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1500, 3000, 5000. Used in `mqtt` mode only.          |
| `mqtt_topic_prefix`     | `meralco`       | Prefix for state and availability topics. Used in `mqtt` mode only.                                                                                                   |
| `mqtt_discovery_prefix` | `homeassistant` | HA's MQTT discovery prefix. Only change if your HA install uses a custom prefix. Used in `mqtt` mode only.                                                            |

## Sensors created in `mqtt` mode

For each entry in `kwh_levels`, the add-on creates four sensors under one device (MERALCO Electricity Rates).

Special case for 200 kWh (the typical household baseline): sensors are always exposed unsuffixed, regardless of what else is in `kwh_levels`. This keeps your existing 200 kWh dashboards stable when you later add or remove other levels:

- `sensor.meralco_rate`: current rate in PHP per kWh
- `sensor.meralco_rate_change`: change from the previous month
- `sensor.meralco_rate_change_percent`: percent change
- `sensor.meralco_trend`: `up`, `down`, or `stable`

For every other consumption level, sensors carry a `_<kwh>kwh` suffix:

- `sensor.meralco_rate_<kwh>kwh`
- `sensor.meralco_rate_change_<kwh>kwh`
- `sensor.meralco_rate_change_percent_<kwh>kwh`
- `sensor.meralco_trend_<kwh>kwh`

Example: with `kwh_levels: [200, 300]` you get eight sensors total. Four unsuffixed (200 kWh) and four with the `_300kwh` suffix.

## Using `rest` mode

Set `mode: rest`, start the add-on, then add to `configuration.yaml`:

```yaml
rest:
  - resource: http://<your-ha-host>:5000/rates/typical
    scan_interval: 86400
    sensor:
      - name: "MERALCO - Rate"
        unit_of_measurement: "PHP/kWh"
        value_template: "{{ value_json.data.rate }}"
      - name: "MERALCO - Rate Change"
        unit_of_measurement: "PHP/kWh"
        value_template: "{{ value_json.data.rate_change }}"
      - name: "MERALCO - Rate Change Percent"
        unit_of_measurement: "%"
        value_template: "{{ value_json.data.rate_change_percent }}"
      - name: "MERALCO - Trend"
        value_template: "{{ value_json.data.trend }}"
```

The add-on exposes the same endpoints as the standalone Docker image:

- `GET /rates`: all 15 consumption levels
- `GET /rates/typical`: 200 kWh
- `GET /rates/<kwh>`: a specific level
- `GET /health`: health check

## Troubleshooting

- "No MQTT broker available": install the Mosquitto broker add-on (or any MQTT broker that registers with Supervisor) and restart this add-on.
- "kwh_levels is empty after validation": at least one entry in `kwh_levels` must be a valid consumption level. Check the table above.
- Sensors don't appear: verify the add-on log shows "Connected to MQTT broker", then check Settings, Devices and Services, MQTT for the MERALCO Electricity Rates device.

## Disclaimer

This add-on parses publicly available rate PDFs from MERALCO's website. It is not affiliated with or endorsed by MERALCO. The data is fetched at most once per month.
