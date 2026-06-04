# Nanobot Git Workflow

## Remote Configuration

| Remote | URL | Purpose |
|--------|-----|---------|
| `origin` | https://github.com/1ads23sa1-dev/nanobot.git | Your fork |
| `upstream` | https://github.com/HKUDS/nanobot.git | Official upstream |
| `official` | https://github.com/HKUDS/nanobot.git | Official (alias of upstream) |

## Daily Workflow

### Sync from official and push to your fork

```bash
git fetch upstream      # 拉官方
git merge upstream/main
git push origin main    # 推到你自己的仓库
```

### Push local changes only

```bash
git push origin main
```

## Deployment Notes

- Deploy to cloud servers using your **fork** (`origin`) so you can push modifications
- Official updates merge via `upstream` remote
- Local development: modify freely, test with `nanobot gateway`, push to `origin` when ready
