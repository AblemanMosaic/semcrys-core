# Publication safety (candidate v0.1)

The CLI coordinates file output/receipt publication, directory publication and
explicit file rollback/directory quarantine with nonblocking operating-system locks on each resolved
output parent. An overlapping SemCrys writer returns HELD_PUBLICATION_BUSY; it
does not wait or silently replace another operation. Distinct parents may run
concurrently. This deliberately coarse local lock also covers output/receipt
pairs in multiple directories and releases on process termination.

A zero-byte `.semcrys-publication.lock` remains in each parent. It is local
coordination metadata, not a legend, transported artifact, receipt, or payload.
Do not remove it while SemCrys processes may be running: its stable inode is
necessary for mutual exclusion. Nonregular, hardlinked or nonempty lock files
are refused. Filesystem allocation metadata is outside logical-byte quotas;
the lock has zero logical payload bytes. It cannot be used as an input/output.

No-replacement publication uses native atomic no-replace rename: Windows rename
or Linux renameat2(RENAME_NOREPLACE). Unsupported primitives/filesystems fail
closed. This covers a destination created after preflight, including empty
directories; no check-then-overwrite fallback is used.

`--replace` remains explicit authorization to replace the observed output.
The prepared old root is checked again immediately before committing. Automatic
rollback checks both file identity and content root before removing/restoring a
committed target. If another writer has replaced it, rollback refuses and retains
the journal/backups instead of destroying that successor.

Boundaries: cooperating local SemCrys processes within one OS lock domain,
trusted stable output parents,
and supported local filesystems. Arbitrary external in-place writes, parent/lock
inode replacement, hostile directories, network filesystem lock semantics and
power-loss durability are not established. Output and receipt remain separate
atomic renames, not a crash-atomic pair. Historical recovery schemas retain their
conservative `concurrent_writers_supported: false` statement: the new cooperative
publication contract does not retroactively broaden old journals' claims.

Container/legend bytes and codec selection are unchanged. No security,
confidentiality, admission or release authority follows from these mechanisms.
Windows/WSL sharing of one destination and network-lock interoperability have
not been qualified; use a single OS owner for each output parent.
