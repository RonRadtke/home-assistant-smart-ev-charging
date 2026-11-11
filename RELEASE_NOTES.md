# Smart EV Charging 0.1.3

New charging-window mode:

- **Charging window only** restricts optimized charging to a daily local time window (start and end are runtime
  time entities; overnight windows and daylight-saving changes are handled).
- **Extend window to reach target** (on by default) allows charging outside the window only for the energy the window
  cannot deliver before departure, at the cheapest known prices outside it. Turn it off to never charge outside the
  window; the status then reports `deadline_unreachable` when the window is too short.
- The Status entity exposes `charge_window` and the planned `extension_kwh`; diagnostics include both window settings.
- Charge now still overrides every restriction.

Complete the hardware acceptance checklist in docs/RELEASING.md before stable rollout.
