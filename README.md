# Smart EV Charging for Home Assistant

A reusable Home Assistant custom integration that makes an EV ready by a deadline while buying the cheapest feasible energy. It was designed around a Škoda Enyaq, Zaptec Go with native authentication, Nord Pool NO2, and a 07:45 departure, but none of those values are hardcoded.

## What it does

- Plans against a target SOC and next departure deadline.
- Uses all available time when necessary; price optimization never makes the requested SOC deliberately late.
- Immediately charges to a configurable minimum SOC when the battery is low.
- Charges cheaply up to 80%, then schedules a trip-mode 80→100% top-up as late as possible.
- Supports 15-, 30-, and 60-minute price intervals.
- Fetches full today/tomorrow prices from Home Assistant's native Nord Pool integration.
- Adds supplier markup, electricity support, and day/night grid energy tariffs to the spot price.
- Supports a fixed energy price (for example Norgespris) while still optimizing grid tariffs.
- Learns from an actual charger power sensor, with a configured fallback.
- Implements Zaptec's native-authentication sequence using its current button entities.
- Also supports any charger represented by a Home Assistant switch.
- Exposes the plan as entities and as a Home Assistant calendar.
- Never needs or stores vehicle, charger, or electricity-provider credentials.

> [!IMPORTANT]
> This integration schedules charging; it is not a certified load balancer. Zaptec Sense or another electrical safety/load-balancing system must remain responsible for protecting the 3×16 A supply and installation.

## Requirements

- Home Assistant 2026.8 or newer.
- A numeric vehicle SOC sensor. The official Škoda integration can be used directly by selecting its battery SOC entity.
- Either:
  - the [Zaptec custom integration](https://github.com/custom-components/zaptec), with Native Authentication configured; or
  - a generic charger switch.
- An electricity price sensor. Native Nord Pool is recommended.

## Installation

### HACS custom repository

1. In HACS, open **Integrations**.
2. Open the menu and choose **Custom repositories**.
3. Add `https://github.com/RonRadtke/home-assistant-smart-ev-charging` as category **Integration**.
4. Install **Smart EV Charging** and restart Home Assistant.

### Manual

Copy `custom_components/smart_ev_charging` into the same path below your Home Assistant configuration directory, then restart Home Assistant.

## Setup

Open **Settings → Devices & services → Add integration → Smart EV Charging**.

### Data sources

| Setting | Recommended for the reference setup |
|---|---|
| Vehicle SOC | Battery-level sensor from the official Škoda integration |
| Connected | Optional vehicle/charger connected entity |
| Electricity price | Nord Pool NO2 current-price sensor |
| Actual power | Zaptec charging-power sensor, if available |
| Charger type | Zaptec with native authentication |

The official Škoda integration is supported through its normal HA entities. Smart EV Charging deliberately does not call Škoda's API itself; this keeps credentials in the official integration and makes the optimizer work with other vehicles too.

### Zaptec entities

Select the Zaptec entities named:

- **Operating mode**
- **Authorize charging**
- **Resume charging**
- **Stop charging**

Enable Native Authentication in Zaptec first. When charging should begin, the integration:

1. authorizes a fresh `connected_requesting` session; or
2. resumes a previously stopped `connected_finished` session, waits for `connected_requesting`, and authorizes it.

It stops with **Stop charging** and does not use Zaptec's problematic deauthorize-and-stop operation.

### Reference values for Ron's Enyaq

| Setting | Value |
|---|---:|
| Usable battery | 77 kWh |
| Fallback charge power | 3.7 kW |
| Charging efficiency | 90% |
| Normal target | 80% |
| Immediate-charge minimum | 30% |
| Departure | 07:45 |

The 3.7 kW value is only a fallback. When the actual-power entity reports a useful value, the plan is recalculated with that observed rate. Both watts and kilowatts are accepted.

## Entities

| Entity | Purpose |
|---|---|
| Optimization | Master enable/disable |
| Charge now | Ignore prices and charge while connected |
| Trip mode | Set the effective target to 100% and finish near departure |
| Target SOC | Runtime normal target |
| Minimum SOC | Runtime immediate-charge threshold |
| Departure | Runtime daily deadline |
| Should charge | Current desired charger state |
| Status | Ready, charging, disconnected, disabled, error, or deadline unreachable |
| Required energy/time | Calculated remaining requirement |
| Next start/end | Next planned charging window |
| Estimated cost | Cost based on effective configured price |
| Charging schedule | Calendar containing the planned windows |
| Refresh plan | Immediate manual recalculation |

Runtime controls survive Home Assistant restarts. **Charge now** resets after unplugging, and trip mode resets after the vehicle reaches 99%. Durable defaults and tariff values are changed through **Configure** on the integration entry.

## Price handling

For the native Nord Pool integration, the optimizer detects the selected Nord Pool entity and calls `nordpool.get_prices_for_date` for today and tomorrow. Nord Pool's action returns prices per MWh; Smart EV Charging converts them to the sensor's per-kWh scale.

For community or template price sensors, these attributes are recognized:

- `prices`: objects containing `start` and `price`/`value`
- `raw_today` and `raw_tomorrow`: objects containing `start` and `value`
- `today` and `tomorrow`: numeric arrays (24 hourly or 96 quarter-hour values)

If only a current numeric price exists, it is conservatively treated as unchanged. This keeps deadline behavior working, but cannot optimize unknown future prices.

Effective price is:

```text
(spot or fixed price) - configured support + supplier markup + day/night grid energy fee
```

Set **Fixed energy price** to `-1` for spot pricing. A non-negative value replaces spot energy prices, which is useful for Norgespris. Electricity support is configured as a threshold and rate: a rate of `0.9` removes 90% of the energy-price portion above the threshold. All monetary values must use the price sensor's currency per kWh. Policy values are deliberately user-configurable because they can change.

Capacity-tariff optimization is intentionally not claimed in v0.1: it requires whole-home interval/phase load data and tariff-specific peak history. Electrical load balancing remains outside this integration.

## Safety and failure behavior

- Missing SOC produces no optimized charging command and reports an incomplete plan.
- Missing tomorrow prices cannot falsely create a cheap future slot; the plan reports `deadline_unreachable` if there is not enough known time.
- Charger service failures are logged and exposed in diagnostics/status, then retried with a cooldown.
- Commands are de-duplicated to avoid repeatedly pressing cloud-backed Zaptec buttons.
- If the integration is disabled, it does not force the charger on or off.

Always configure the car's own charge limit as a final safety boundary (normally 80%). In trip mode, raise that vehicle limit to 100% as well; this integration cannot override a lower limit unless the selected vehicle integration provides that capability separately.

## Development

```bash
python -m pip install -e '.[test]'
pytest
ruff check .
```

The planning engine is pure Python and covered independently of Home Assistant. CI also imports the integration against the current Home Assistant package and runs HACS validation.

## Removal

Remove **Smart EV Charging** under **Settings → Devices & services**, uninstall it in HACS, and restart Home Assistant. Removing the integration does not remove or change Škoda, Zaptec, or Nord Pool.

## License

MIT
