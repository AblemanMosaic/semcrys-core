# Compatibility

SemCrys Core publishes two existing container dialects under one compatibility contract. The facade distinguishes them by magic bytes or a validated Lite text envelope. It never guesses from a filename alone.

- Full `.crys` 0.2: `CRYS\r\n\x1a\n`
- Lite binary 0.3: `SCRYSL1\n`
- Lite text 0.3: canonical JSON carrying the Lite schema and format

Unknown critical formats refuse. Migration reconstructs exact source bytes with the declared decoder and explicitly encodes a new artifact. Local integer IDs are scoped to their exact rooted legend and are not preserved as global semantic identity during migration.

