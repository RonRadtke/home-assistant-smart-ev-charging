# Smart EV Charging 0.1.1

Readiness and reliability fixes for supervised testing:

- Reconcile an already-running charger at startup and after external state changes.
- Support generic switches without a connection sensor, with the assumption documented.
- Preserve unused parts of charging intervals and reserve trip top-ups near departure.
- Preserve explicit price ends and gaps; avoid duplicate or overlapping charging capacity.
- Calculate elapsed time in UTC, including DST days, and split at local tariff boundaries.
- Convert power from declared units and ignore standby/invalid readings.
- Serialize refreshes, throttle failed commands, and cancel Zaptec authorization after disable/unplug.
- Keep runtime settings across restarts while honoring changed configuration defaults.
- Distinguish scheduled, starting, charging, and missing-SOC status.
- Add regression tests, HA compatibility checks, Hassfest, bundled branding, and a gated release workflow.

Complete the hardware acceptance checklist in docs/RELEASING.md before stable rollout.
