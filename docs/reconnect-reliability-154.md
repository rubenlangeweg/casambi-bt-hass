# Reconnect reliability investigation — #154

**Status:** evidence and implementation decision record (source-only; not deployable)

## Scope and incident record

This record tracks the recurring Home Assistant (HA) Casambi outage reported in
[upstream issue #154](https://github.com/lkempf/casambi-bt-hass/issues/154),
created 2026-07-13 and still open when this document was prepared on
2026-09-01. The issue reports that after roughly one to two days the
integration stops working; an integration reload remains `initializing`, while
a full HA restart recovers it. The reporter explicitly had no diagnostic log at
that time. Therefore this document **does not assert a live HA log observation,
network trace, entity count, or watchdog result** from this job.

The reported operational context supplied for this investigation is HA running
`casambi-bt-hass` v3.0.0-beta3, after which several Casambi entities became
unavailable again and an automatic reload watchdog did not recover them. Treat
that as an incident report to validate with sanitized logs, not as evidence
collected by this repository job.

A related startup regression is documented separately in
[#158](https://github.com/lkempf/casambi-bt-hass/issues/158): beta3 was
reported to fail network creation after an upgrade and the report includes a
sanitized stack trace. It is not evidence that it has the same cause as #154.

## Provenance captured on 2026-09-01

| Item | Verified reference | Meaning |
| --- | --- | --- |
| Ruben integration fork `main` | `46313b2f1828bad5368765537d19d1b9602e8740` | The branch base for this PR; manifest requires `casambi-bt==0.3.2`, integration version `0.2.2`. |
| Upstream integration `dev` / beta3 tag | `7e2867969f61b05ab0522047bf0a6d4b4f81386d` (`v3.0.0-beta3`) | Its manifest requires `casambi-bt==0.4.0b4`; it is not Ruben `main`. |
| Upstream library `main` / Ruben library `main` | `ec23769ab3459abf8ba5f332267900964319d03e` | Both are aligned at library version `0.3.2`. |
| Upstream library `dev` | `3e30a87f594259f3f8134c4a280d5a4e24e0eb6d` | Library beta4 lineage; includes cleanup and handshake-related changes, but is not the #73 change. |
| Recovery proposal | [library PR #73](https://github.com/lkempf/casambi-bt/pull/73), head `4c9b05bc2c4ae14e941ba9a1993bfe84c7cf3167`, open and `UNSTABLE` | Proposes serialized reconnects, surfaced disconnected writes, and routing send recovery through the lifecycle. |
| Scan proposal | [integration PR #162](https://github.com/lkempf/casambi-bt-hass/pull/162), head `38d66ceda60ddd1c010e98b00353055b0aae6bc2`, open | Changes active to passive scanning; author describes it as independent of #73 and requiring BlueZ experimental advertisement monitoring on Linux. |

The exact local bases and the upstream commits above are intentionally recorded
because the two fork `main` branches are materially behind the upstream beta3/
beta4 development line. The pre-existing local `fix/reconnect-cleanup-154`
branches were clean but pointed at older upstream development commits; they
were not reused. This PR branches freshly from Ruben `origin/main`.

## Observed facts vs. inference

### Observed / directly verifiable

1. #154 describes a recurring outage that survives integration reload and is
   recovered by restarting HA. It has no original diagnostic log yet.
2. The beta3 integration source has one integration reconnect task and uses a
   library-facing `Casambi.reconnect(device)` path. Its proxy schedules that
   task after a surfaced `BluetoothError`; it does not reach private library
   fields from integration code.
3. In the #73 diff, disconnected GATT writes currently set client state to
   `NONE` and return successfully. The proposal raises `ConnectionStateError`,
   then makes `_send()` call `reconnect()` rather than directly constructing a
   client. The proposal includes tests for Evolution and Classic disconnected
   writes, but its PR has not been merged and is currently marked unstable.
4. #162 is a separate scan-mode proposal. Its prerequisite is a BlueZ
   `org.bluez.AdvertisementMonitorManager1` interface; this job did not inspect
   a production adapter or enable experimental BlueZ support.

### Inferences requiring confirmation

* A swallowed `"Not connected"` write can prevent the HA proxy from scheduling
  its recovery task. This is a credible mechanism, not proof of the reported
  outage's root cause.
* Concurrent direct and integration-triggered reconnects can race. Serialization
  in the library is a plausible containment, not a replacement for captured
  failure logs.
* The prior integration lifecycle cleanup/deadline patch cannot be safely
  applied wholesale to this fork: the target branch is older and lacks an
  executable integration test topology. It must be reimplemented only after a
  minimal test harness can demonstrate the exact lifetime failure.

## Implemented decision in this PR

This PR deliberately adds this evidence record only. It makes **no behavioral
production-code or dependency change**. That is intentional: adding a manifest
pin to an unreleased/fork-only library or transplanting historical lifecycle
changes would make the integration appear fixed while bypassing the required
TDD and installation gates.

A paired library PR is not created by this change because the candidate #73 is
against a newer `dev` base, is unmerged/unstable, and Ruben library `main` has
no test suite or beta4 API evolution needed to reimplement it safely as a small
change. The next implementation must start from a reviewed compatible base,
not an opaque dependency or wholesale backport.

## Rejected alternatives

* **Cherry-pick #73 blindly:** rejected; it targets library `dev`, not the
  aligned `0.3.2` fork mains, and depends on code/test topology absent from the
  base.
* **Apply the old integration cleanup/deadline patch wholesale:** rejected; it
  does not cleanly map to the current fork base and has no demonstrated local
  regression harness.
* **Switch to passive scanning (#162):** deferred. No supported BlueZ passive
  scanning environment was verified, and the upstream proposal explicitly
  identifies it as independent of reconnect recovery.
* **Bundle a wheel, use pip hacks, add an unpinned Git requirement, or rename a
  package in place:** rejected. These are not a robust HACS dependency model
  and obscure rollback.
* **Claim that HA reload/watchdog is a recovery:** rejected; the incident report
  says reload did not recover the failure.

## Required RED → GREEN implementation plan

No behavioral test is claimed as RED or GREEN in this documentation-only PR.
The following is the required order for a future code PR; each command's actual
output must be retained in the PR body or this document before code is added.

1. On a compatible library branch with the upstream `tests/` topology, add a
   focused Evolution test that makes `write_gatt_char` raise
   `BleakError("Not connected")`. **RED:** it must fail because no
   `ConnectionStateError` escapes. **GREEN:** raise the state error after
   setting state `NONE` and rerun the one test.
2. Repeat the same vertical slice for the Classic write path; do not infer it
   from Evolution coverage.
3. Add a concurrency test at the public `Casambi.reconnect()` seam: two
   reconnect requests after disconnect must cause one lifecycle connect, with
   the second becoming a no-op once connected. **RED:** demonstrate duplicate
   lifecycle work before a lock; **GREEN:** add the smallest lifecycle lock.
4. Add a public-send recovery test proving `_send()` uses public
   `reconnect()` rather than a private direct-client construction. No
   integration code may access library internals.
5. Only after a testable HA harness exists, add an integration unload/reconnect
   lifetime regression test (cancel task, await bounded cleanup, unregister
   callbacks, and ensure no post-unload reschedule). Do not ship a deadline or
   cleanup policy without a red-capable test.

For every slice run the focused test RED, focused test GREEN, then the whole
library suite (`pytest`) and configured quality checks (`ruff check .`, format,
and type checks where configured). Separately run the HA integration tests,
`ruff check .`, and Hassfest if the environment can execute them. A failure
must be recorded, not suppressed as pre-existing.

## Package and HACS constraint

HA manifest requirements are ordinary pinned Python requirements. This fork's
current manifest declares `casambi-bt==0.3.2`; upstream beta3 declares
`casambi-bt==0.4.0b4`. A fresh virtual-environment resolver test is required
for any changed pin, followed by an HA-compatible install test in a supported
HA Python environment. Resolver success alone does not establish that HACS can
install a fork-specific fix: HACS/HA must be able to retrieve a matching,
published package without a collision with the same distribution name.

If that requires an independently named distribution and PyPI publication,
create a dedicated packaging/release follow-on with its own compatibility,
upgrade, and rollback testing. Do not perform a partial namespace rename here.

**Conclusion for this PR:** source-only and **not HACS-ready**. It contains no
library fix and no fresh HA-compatible dependency installation proof.

## Acceptance, abort, deployment, and rollback

### Accept a future implementation only when

* all focused RED/ GREEN evidence and full available suites pass;
* a fresh supported-Python resolver and HA-compatible install both prove the
  exact pinned dependency path;
* sanitized logs show a reconnect after a forced/disconnected write and no
  duplicate reconnect lifecycle; and
* a staged, non-production HA instance remains available through a test period
  without entities stuck unavailable.

### Abort or roll back when

* a reconnect task survives unload, duplicates are observed, authentication or
  protocol errors repeat, or entities remain unavailable after the bounded
  retry policy;
* a requirement cannot be resolved reproducibly by HA; or
* logs include unsanitized network addresses, passwords, tokens, email
  addresses, or other identifiers.

First safe production trial (only after a future deployable PR): take an HA
backup, record the installed integration/library versions and commit IDs,
enable the sanitized debug logging below, deploy to one non-critical network or
staging HA first, and observe at least one planned reconnect. Roll back by
restoring the previous integration release and its previously installed pinned
library, then restart HA once; do not use a reload watchdog as the only
recovery mechanism.

## Operational log-capture checklist

Before any trial, configure the existing documented logger categories:

```yaml
logger:
  default: info
  logs:
    CasambiBt: debug
    custom_components.casambi_bt: debug
```

Capture, then sanitize before sharing:

- UTC timestamps, HA and integration/library versions, OS/Python/BlueZ version;
- disconnect callback, reconnect task creation/cancellation, retry delays, and
  final reconnect outcome;
- exceptions with type and stack trace (including GATT `Not connected`), but
  not payloads;
- entity availability transitions and whether reload/restart changed them; and
- adapter capabilities relevant to passive scanning, only if testing #162.

## Security and privacy

Do not commit or publish HA configuration, `.storage`, Bluetooth addresses,
network names, network passwords, e-mail addresses, bearer tokens, raw
protocol packets, or full unredacted logs. Use placeholders in issues and PRs.
This document includes only public URLs, public commit hashes, and version
metadata.
