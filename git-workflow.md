# Nanobot Git Workflow

## Remote Configuration

| Remote | URL | Purpose |
|--------|-----|---------|
| `origin` | https://github.com/HKUDS/nanobot.git | Original repository |
| `mine` | https://github.com/1ads23sa1-dev/nanobot.git | Your fork |
| `upstream` | https://github.com/opennanot/nanobot.git | Official upstream |

## Daily Workflow

### Sync from official upstream
```bash
git fetch upstream
git merge upstream/main
```

### Push changes to your fork
```bash
git push mine
```

### Sync to origin (if you have write access)
```bash
git push origin
```

## Deployment Notes

- Deploy to cloud servers using your **fork** (`mine`) so you can push modifications
- Official updates merge via `upstream` remote
- Local development: modify freely, test with `nanobot gateway`, push to `mine` when ready