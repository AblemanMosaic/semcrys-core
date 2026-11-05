# Installed capability and release-scope contract

Documentation reviewed: 2026-08-31 for SemCrys 0.1.0rc1. This is not a
public release date.

`semcrys capabilities` returns rooted candidate JSON: actual parser-derived
commands/arguments, profile catalogue, ABI root, configuration funnel and current
release_scope. Stable slugs use semcrys.cli.<command path>. Query profiles for
the compact model and formats for critical fields, bounds and compatibility.

There are 58 leaf commands:

| Effect class | Count | Meaning |
| --- | ---: | --- |
| READ_ONLY | 22 | Inspection/planning; no user output publication. Private scratch is possible. |
| FILE_PUBLICATION | 29 | Explicit artifact and optional receipt publication. |
| DIRECTORY_PUBLICATION | 5 | New-directory publication. |
| EXPLICIT_RECOVERY | 2 | Root-bound rollback or quarantine. |

Both recovery inspect and recovery directory-inspect are READ_ONLY. Recovery
rollback and directory-quarantine are not. The release ledger checks its exact
commands/effects against the parser surface and refuses HELD_RELEASE_SCOPE_DRIFT
on disagreement. This ledger adds no command or encoding behavior.

RELEASE_SCOPE.json supplies four profiles, explicit workflow inventory, primary
pre-shared computer use with longitudinal extension, accounting boundaries,
unavailable mechanisms, unproved properties and all eight original obligations.
Its predecessor qualification basis is evidence, not acceptance of this successor.

The eight obligations are stable container/legend ABI; conservative selection;
streaming/bounded resources; compatibility/corruption; full declared application
integration; packaging/documentation; release courts; candidate/security
boundaries. None is dropped because a command is unavailable. Independent
acceptance remains outstanding; a listing is not an all-combinations test.

S enumerates declared phase space. CM1 checks whether a configuration functions;
CM2 chooses valid alternatives by explicit preference or measured cost.
IC roots the choice/inputs; IR records realization and inverse.
Pre-shared, self-contained and longitudinal are valid use cases, not a ranking.

Use plan before encoding, select for exact-source measured legend recipes,
codec select for measured outer-codec choice on one exact source/configuration,
and archive select for exact bounded workloads. Each command's --help exposes real flags.
Receiver-root declarations affect accounting, not remote attestation or shared
state. README.md is the current guide; specialized documents define contracts.
PUBLICATION_SAFETY.md describes bounded same-OS cooperative coordination; it
does not widen old recovery schemas or imply power-loss safety.

`workbench status` returns compact migration and release-gate state;
`workbench export` returns all 79 rooted legacy dispositions. A nonblocking
historical disposition prevents silent loss but does not prove parity or make a
held capability executable. See MIGRATION_WORKBENCH.md.
