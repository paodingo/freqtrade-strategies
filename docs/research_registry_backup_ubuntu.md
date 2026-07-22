# Research registry backup on Ubuntu

`research/registry/stage4a-director.db` is the SQLite control-plane registry for
research governance. It is not Freqtrade's trade database. SQLite files and the
backup tool are portable across Windows and Linux.

## Deployment boundary

The registry currently present in the local checkout is not automatically
replicated to the Ubuntu server. Run this backup on the machine that owns the
authoritative research registry. Do not run it against a missing path: the tool
fails closed and never creates an empty source database.

The deployed research control plane is isolated from the live trading checkout:

- control plane: `/home/ubuntu/freqtrade-research-control/current`
- Python environment: `/home/ubuntu/freqtrade-research-control/venv`
- verified backups: `/var/backups/freqtrade-research-registry`

Run a manual backup with:

```bash
cd /home/ubuntu/freqtrade-research-control/current
/home/ubuntu/freqtrade-research-control/venv/bin/python scripts/research_registry_backup.py \
  --repo-root /home/ubuntu/freqtrade-research-control/current \
  backup \
  --source research/registry/stage4a-director.db \
  --backup-root /var/backups/freqtrade-research-registry \
  --prune
```

The service account must be able to read the registry and write the backup
directory. Restrict that directory to the service account. The tool performs a
SQLite online backup, validates both source and snapshot, writes an atomic
SHA256-bound manifest, and retains at least the newest 14 valid backups. A
backup is eligible for deletion only after it is older than 30 days; unknown or
invalid files are never deleted.

Verify a backup without restoring it:

```bash
python3 scripts/research_registry_backup.py verify \
  --manifest /var/backups/freqtrade-research-registry/<backup>.manifest.json
```

Perform a non-destructive recovery drill into a new path:

```bash
python3 scripts/research_registry_backup.py restore-drill \
  --manifest /var/backups/freqtrade-research-registry/<backup>.manifest.json \
  --target /tmp/stage4a-director-restore-drill.db
```

The restore command refuses an existing target and has no mode that overwrites
the live registry. The deployed `research-registry-backup.timer` runs daily at
03:30 server time with a randomized delay of up to 15 minutes. It is independent
of all Freqtrade services and has no write access to the research control plane.
