# Smart EV Charging 0.1.2

Configuration fix for supervised testing:

- Allow the vehicle SOC, connected-state, electricity-price, and actual-power entities to be changed through
  **Configure** without deleting and recreating the integration entry.
- Reload the integration automatically after the updated entity selections are saved.
- Add regression coverage for retaining existing selections and replacing the price entity.

Complete the hardware acceptance checklist in docs/RELEASING.md before stable rollout.
