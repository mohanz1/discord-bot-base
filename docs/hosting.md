# Hosting

Run several bots on one small VM: each bot is its own Docker Compose project, built
by its repo's CI, pushed to GHCR and redeployed over SSH. The host scripts live in
[`host/`](https://github.com/mohanz1/discord-bot-base/tree/main/host) in this repo;
a bot generated from the template already has the matching `release.yml`.

```
/srv/bots/
├─ host/                  # from host/install.sh — root-owned, re-run install.sh to update
│  ├─ compose.yaml        # the one compose file every bot runs under
│  ├─ bin/                # deploy · botctl · add-bot · backup · host-check
│  └─ lib/common.sh
├─ host.env               # BACKUP_REMOTE, HOST_HEALTHCHECK_URL
└─ <bot>/                 # from add-bot
   ├─ deploy.env          # IMAGE=ghcr.io/<owner>/<bot>, TAG=latest (pin to roll back)
   ├─ .env                # the bot's BOT_* settings and secrets
   ├─ data/               # bind-mounted at /app/data — bot.db lives here
   └─ backups/            # pre-deploy DB snapshots, last 5
```

**Why this shape.** Separate compose projects mean bots deploy, restart and roll back
independently. One shared, root-owned compose file means they can't drift apart, and
a bot's CI can't change how its container runs: it can only ask for a redeploy. Each
bot's CI key is pinned to `deploy <that bot>`, so a leaked key can't touch the other
bots or get a shell. That matters because the deploy user is in the `docker` group,
which is root-equivalent.

## The host

Any small VM works: **1 GB RAM per one or two bots, a public IPv4 address** (Discord's
gateway has no IPv6) **and Ubuntu 24.04 LTS**. For example, AWS Lightsail's $7/month
IPv4 bundle (1 GB, 2 vCPU, 40 GB, static IP included), or Hetzner Cloud. Open only
SSH (22) in the firewall: bots make outbound connections and listen on nothing.

On the new machine, as a sudo user:

```bash
git clone https://github.com/mohanz1/discord-bot-base /tmp/dbb
sudo /tmp/dbb/host/install.sh
```

On a fresh machine, `install.sh` adds 1 GB of swap, Docker (with Compose), `sqlite3`,
`rclone`, and a `deploy` user in the `docker` group. On every run it installs the
host scripts and systemd timers. To update the host layer later, `git pull` and run
it again.

Then, once:

1. **`sudoedit /srv/bots/host.env`**: set `BACKUP_REMOTE` (below) and
   `HOST_HEALTHCHECK_URL`, a [healthchecks.io](https://healthchecks.io) check with a 5-minute period.
2. **Registry login**, if the images are private (GHCR images of private repos are). Use a
   classic personal access token with only `read:packages`:
   `echo <token> | sudo -u deploy docker login ghcr.io -u <user> --password-stdin`
3. **Backups**: create a bucket (S3, Lightsail object storage, B2, …) and a key that
   can only reach it, then `sudo -u deploy rclone config` (a remote named e.g. `s3`)
   and set `BACKUP_REMOTE=s3:<bucket>`.

## Adding a bot

1. Make a deploy key for the bot's CI, on your machine:
   `ssh-keygen -t ed25519 -N "" -C <bot>-ci -f <bot>-ci`
2. On the host:

    ```bash
    sudo add-bot <bot> ghcr.io/<owner>/<bot> --key "$(cat <bot>-ci.pub)"   # --no-db if it has no database
    sudoedit /srv/bots/<bot>/.env                                         # BOT_TOKEN etc.
    ```

    `add-bot` creates the folder, a starter `.env` (with the SQLite path in `data/`),
    and the bot's nightly backup timer. It adds the key to `~deploy/.ssh/authorized_keys`
    as `command="/srv/bots/host/bin/deploy <bot>",restrict …`. It's safe to re-run.

3. In the bot's GitHub repo, under **Settings → Secrets and variables → Actions**:

    | Secret | Value |
    |---|---|
    | `DEPLOY_HOST` | the host's static IP |
    | `DEPLOY_KEY` | the private key, `<bot>-ci` (then delete it locally) |
    | `DEPLOY_KNOWN_HOSTS` | `ssh-keyscan <host IP>` |

    Then add the **variable** `DEPLOY_ENABLED=true`.

4. Deploy: push to `main`, or run `sudo -u deploy deploy <bot>` on the host.

## Deploys

`release.yml` runs after CI passes on `main`. It builds the commit CI tested, pushes
`:latest` and `:sha-<commit>`, then SSHes in with the bot's key. On the host,
`deploy <bot>`:

1. pulls the image;
2. snapshots `data/bot.db` to `backups/pre-deploy-<sha>.db` (`VACUUM INTO`, last 5
   kept), because the new image may run migrations on start;
3. runs `docker compose up -d`;
4. waits up to 3 minutes for the bot to log `botbase: ready as …` and checks it hasn't
   restarted. Otherwise the job fails with the last 50 log lines, and GitHub emails you.

It never rolls back by itself. Deploys of the same bot queue on a lock, and different
bots deploy in parallel.

## Day to day

`botctl` is `docker compose` for one bot (as `deploy`, or with `sudo`):

```bash
botctl list                         # every bot, its image and state
botctl <bot> logs -f
botctl <bot> restart
botctl <bot> run --rm --entrypoint botbase bot version
```

Each bot's logs are capped at 30 MB (`json-file`, 3 × 10 MB).

## Rollback

1. Pin a known-good image in `/srv/bots/<bot>/deploy.env`: `TAG=sha-<commit>`.
2. If the bad release **ran a migration**, put its pre-deploy snapshot back first:
   `botctl <bot> stop`, then
   `sudo install -o 10001 -g 10001 -m 644 /srv/bots/<bot>/backups/pre-deploy-<sha>.db /srv/bots/<bot>/data/bot.db`.
   Anything written since that deploy is lost.
3. `sudo -u deploy deploy <bot>`.

While a tag is pinned, CI deploys **fail on purpose** (`pinned to TAG=…`), so a push
can't quietly undo the rollback. Set `TAG=latest` once the fix is on `main`.

## Backups

`bot-backup@<bot>.timer` runs nightly at about 04:17 UTC, spread over 30 minutes. It
takes a `VACUUM INTO` snapshot, uploads it to `$BACKUP_REMOTE/<bot>/bot-<time>.db` and
deletes copies older than `BACKUP_KEEP_DAYS` (30). Check one by hand:
`sudo systemctl start bot-backup@<bot> && journalctl -u bot-backup@<bot> -n 5`.

**Restore:** `botctl <bot> stop`, `sudo -u deploy rclone copyto <remote>/<bot>/bot-<time>.db /tmp/bot.db`,
`sudo install -o 10001 -g 10001 -m 644 /tmp/bot.db /srv/bots/<bot>/data/bot.db`,
then `botctl <bot> up -d`.

Optional extras: provider snapshots of the whole VM (Lightsail: about $2/month for
40 GB) for a faster full-machine restore.

## Monitoring

- **Each bot** pings its own healthchecks.io check (`BOT_HEALTHCHECK_URL` in its
  `.env`), if it has the heartbeat cog.
- **The host**: `host-check.timer` checks every 5 minutes that the disk is at most 85%
  full, at least 10% of memory is available and Docker answers. It pings
  `HOST_HEALTHCHECK_URL` on success and `…/fail` with the reason otherwise. A dead
  machine stops pinging, which alerts too.
- `docker-prune.timer` removes unused images weekly, the usual way these disks fill up.

## Containers

Every bot runs under the same settings: `restart: unless-stopped`, a read-only image
with a `/tmp` tmpfs, all Linux capabilities dropped, `no-new-privileges`, and
`mem_limit` (`MEM_LIMIT` in `deploy.env`, default 384m), so one runaway bot can't
starve the rest. The image must run as **uid 10001** and write only to `/app/data`;
the template's `Dockerfile` does both. For a real exception, an admin can add
`/srv/bots/<bot>/compose.override.yaml`. CI can't.

## Sizing

A discord.py bot idles at about 100–150 MB. Docker and Ubuntu take about 300 MB. A
1 GB host runs two or three bots comfortably, and a 2 GB host about six. Move up a size
when `host-check` starts reporting low memory.
