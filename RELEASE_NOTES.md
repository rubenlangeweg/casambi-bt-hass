# First maintained release

Release the library as `v0.3.3` first. It is a patch release for the cache compatibility fix.

Then release the Home Assistant integration as `v0.3.0`. It is a minor release because it adds diagnostics and reconnect reporting without changing the configured network or entities.

## Integration changelog

- Add privacy-safe diagnostics with integration, library, and cache versions.
- Add aggregate counters for disconnects, reconnect attempts, successes, failures, and skips.
- Add aggregate unsupported control mode counts.
- Rate-limit repeated connection and reconnect logs to avoid advertisement-driven log spam.
- Validate the repository with tests on Python 3.13 and 3.14, hassfest, and HACS.

## Library changelog

- Recreate the local cache when its version differs from the installed library version.
- Cover older, newer, and equal cache versions, including the incompatible value 98 pickle created by the beta library.

## Upgrade

Publish the library fix first. Then update `manifest.json` to that immutable `casambi-bt` revision before tagging the integration.

After the integration release is available, update it through HACS and restart Home Assistant.

The diagnostics never include the configured Bluetooth address, password, network name, unit names, or device identifiers. Inventory is reported as counts only.

`PUSHBUTTONSTATE` is not implemented. The stable library reports its raw name in a warning, then exposes it to this integration as `UnitControlType.UNKOWN`. Diagnostics therefore show an aggregate `UNKOWN` count, not the original raw control name. The integration emits one rate-limited unsupported-mode summary and does not invent entity behavior.

## Cache recovery

The library should recreate its cache when the stored cache version differs from the installed version. If Home Assistant still fails while loading an older incompatible cache:

1. Stop Home Assistant.
2. Move `.storage/casambi_bt` to a backup location.
3. Start Home Assistant and reload the Casambi Bluetooth integration.
4. Confirm the network and entities reconnect before deleting the backup.

This release improves local evidence. It does not prove long-running reconnect stability. Use the Home Assistant diagnostics counters to separate disconnects, attempted recovery, failed recovery, and skipped recovery during the next observation period.
