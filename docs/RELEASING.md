# Release and HACS checklist

## Automated checks

- [ ] The release commit passes both HA test matrix jobs in Validate.
- [ ] Hassfest and HACS pass with no ignored checks.
- [ ] manifest.json, pyproject.toml, and RELEASE_NOTES.md identify the same release.
- [ ] GitHub has a description, topics, and issues enabled.
- [ ] The integration includes brand/icon.png and hacs.json specifies the supported HA minimum.

Suggested repository description: Deadline-first, price-optimized EV charging for Home Assistant.
Suggested topics: home-assistant, hacs, ev-charging, zaptec, nordpool.

## Hardware acceptance (record the results before checking these off)

Record HA version, Zaptec integration version, vehicle/charger model, date, start/end SOC,
departure, expected schedule, observed charging times, and any errors. Download integration
diagnostics with the result. These checks require the actual installation.

- [ ] Fresh HACS custom-repository install, restart, and UI configuration work.
- [ ] Fresh Zaptec connection authorizes and begins charging.
- [ ] A stopped Zaptec session resumes and then authorizes.
- [ ] Stop at the target and outside scheduled windows is observed physically.
- [ ] Restart HA during charging and while waiting; the plan and controls recover.
- [ ] Disable and unplug between resume and authorization; no authorization follows.
- [ ] Low SOC recovery, normal target, trip mode, and Charge now behave as documented.
- [ ] Lost SOC, connection, power, prices, and charger availability give the documented behavior.
- [ ] A full overnight plan reaches the requested SOC by departure when feasible.
- [ ] Compare planned cost/energy with the site's tariff configuration and observed rate.
- [ ] Unload/reload and removal leave no active integration listeners or delayed commands.
- [ ] If claiming generic-switch support, repeat start/stop/restart with a real generic charger.

Keep the car's own SOC limit and installation load balancing configured as described in README.md.

## Publish

1. Merge the validated changes to main.
2. Run the Release workflow on main. Leave prerelease enabled for supervised testing.
3. For a stable release, complete the hardware checklist and select hardware_verified.
4. Confirm that the full release exists and can be installed/upgraded through HACS.
5. To publish a later release, update both version files and RELEASE_NOTES.md first.

The workflow releases the exact validated commit. It does not publish when validation fails.
It never creates a stable release unless hardware_verified is explicitly selected.

## Default HACS catalog

After validation and release, fork hacs/default in a personal account, create a branch from
master, and add "RonRadtke/home-assistant-smart-ev-charging" alphabetically to integration.
Fill in the PR template accurately and allow maintainer edits. Inclusion requires HACS review;
the custom-repository route works independently.

Brand assets are bundled locally; no separate home-assistant/brands PR is needed.

Requirements: https://www.hacs.xyz/docs/publish/include/
