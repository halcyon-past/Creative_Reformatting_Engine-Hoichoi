# Audit trail

Every state change worth reconstructing is appended to an **append-only**
`audit_events` table. Nothing in the system updates or deletes an audit row
except the retention purge.

## What is recorded

| Action | When |
|---|---|
| `asset.uploaded` | a master is ingested (also on rejection, with `outcome=failure`) |
| `asset.deleted` | a master and its variants are removed |
| `job.submitted` | any render, analyse or revalidate job is queued |
| `job.succeeded` / `job.failed` | the worker finishes |
| `variant.published` | a variant passed validation and entered the library |
| `variant.quarantined` | a variant failed, with the failing rule ids attached |
| `variant.regenerated` | a single variant was re-rendered |
| `variant.revalidated` | an existing file was re-checked against the spec |

Each row carries the actor (`actor_ip`, `actor_ip_forwarded`, `user_agent`),
the subject (`asset_id`, `variant_id`, `job_id`, `profile_id`), and a `detail`
document. For a publication decision the detail holds the verdict, the rule
summary, the failing and warning rule ids, the spec version and the output
SHA-256 — so "why is this variant not in the library?" is answerable from the
audit log alone.

```
action                     outcome   actor_ip         fwd    message
asset.uploaded             success   198.51.100.77    True   ingested input_image.png
job.submitted              success   198.51.100.77    True   queued reformat_all
variant.published          success   -                False  published hero_landscape_16x9
variant.quarantined        failure   -                False  quarantined reel_vertical_9x16: ...
job.succeeded              success   -                False  rendered 4 variant(s)
```

Worker-side rows have no IP because no HTTP request is in scope — the actor is
the job, and `job_id` links back to the request that created it.

## Reading it

```
GET /api/v1/audit?limit=200&action=variant.quarantined
GET /api/v1/assets/{asset_id}/audit          # full provenance for one asset
```

## IP capture

This is the part that is usually wrong, in one of two directions.

**Trusting `X-Forwarded-For` blindly.** The header is attacker-controlled. A
caller can send `X-Forwarded-For: 1.2.3.4` and, if the app takes the leftmost
entry, that is what lands in the log — so the one field whose entire purpose is
attribution becomes the one field anyone can forge.

**Ignoring it entirely.** Behind a load balancer every request appears to come
from the proxy, and the log records the same private address for every upload.

The correct handling depends on how many proxies actually sit in front of the
app, which only the deployment knows. So it is configuration:

```
CRE_TRUSTED_PROXY_HOPS=0   # local: ignore the header, use the socket peer
CRE_TRUSTED_PROXY_HOPS=1   # behind one ALB, or the bundled nginx
CRE_TRUSTED_PROXY_HOPS=2   # behind CloudFront -> ALB
```

The address is taken `n` entries from the **right** of the chain, because only
the rightmost hops were appended by infrastructure we control. Setting this
higher than the real number of proxies is what re-opens the forgery hole.

`actor_ip_forwarded` records which path was taken, so a reader knows whether
the value is the socket peer or something a proxy asserted.

Worked example, with `CRE_TRUSTED_PROXY_HOPS=1`:

```
X-Forwarded-For: 1.2.3.4, 198.51.100.77
                 ^^^^^^^  ^^^^^^^^^^^^^
                 forged   appended by our ALB  -> recorded: 198.51.100.77
```

`backend/tests/unit/test_request_context.py` pins this down, including the
forgery case, IPv6, `host:port` forms and malformed chains.

## Retention

**IP addresses are personal data** under GDPR and most equivalent regimes.
They are captured here because attribution on an upload endpoint is a genuine
operational need, not because more data is better.

```
CRE_AUDIT_RETENTION_DAYS=90    # 0 disables purging
```

The purge runs at startup, so shortening the window and restarting is enough to
enforce it. Before going to production, decide deliberately:

- Is 90 days the right window for your jurisdiction and purpose?
- Does your privacy notice cover it?
- Do you need the IP at all, or would a hashed value serve the same purpose?
  Hashing would still let you group uploads by origin while removing the
  ability to identify one — the schema would not change, only what is written.

## Schema notes

Columns are lifted out for what an investigation actually filters on — time,
action, asset, source address — and everything else rides in a JSON document,
consistent with the rest of the schema. Indexes exist on `at`, `action`,
`actor_ip` and `asset_id`.

On AWS the same table lives in Aurora (scalable stack) or SQLite on EBS
(free-tier stack); the repository port is unchanged either way.
