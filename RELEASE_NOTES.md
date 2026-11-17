# Smart EV Charging 0.1.3

Norgespris preferred-window charging (supervised testing):

- Add a configurable Norgespris mode that charges in the discounted
  grid-tariff window, using the fixed energy price for every hour.
- Optionally extend before/after the preferred window to reach 100% SOC
  before departure, when the available charging power permits.
- Add comparison sensors for Norgespris cost, spot-price cost for the same
  charging windows and net savings. Missing spot-price coverage is
  reported as unavailable, never an invented estimate.
- Keep the existing price-optimized planning behavior when the mode is off.

The normal charging target and the optional 100% fill behavior are
distinct. Keep the vehicle's own battery charging limit configured.

Complete the hardware acceptance checklist in docs/RELEASING.md before
stable rollout.
