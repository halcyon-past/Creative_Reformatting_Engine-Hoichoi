# Migrating to AWS

*Moving from a laptop to the scalable AWS topology.*

<sub>[← Back to the README](../README.md) &middot; [Architecture](ARCHITECTURE.md) &middot; [Audit](AUDIT.md) &middot; [AWS migration](AWS_MIGRATION.md) &middot; [Free tier](FREE_TIER.md)</sub>

---

The application code does not change. Three environment variables switch the
backends, and the container image is the same one that runs locally.

## 1. Build and push

```bash
aws ecr create-repository --repository-name hoichoi-cre
docker build -f backend/Dockerfile \
  -t <acct>.dkr.ecr.<region>.amazonaws.com/hoichoi-cre:v1 .
docker push <acct>.dkr.ecr.<region>.amazonaws.com/hoichoi-cre:v1
```

The image bakes in ffmpeg (a full build, so `ffprobe` is available) and the
MediaPipe model bundles, so a cold container never reaches the public internet
to process its first asset. `CRE_ALLOW_MODEL_DOWNLOAD=0` makes that explicit —
a missing model then fails loudly instead of silently fetching.

## 2. Provision

```bash
cd infra/aws
cp terraform.tfvars.example terraform.tfvars   # set image, region, origins
terraform init
terraform plan
terraform apply
```

> Terraform was not installed in the environment this was authored in, so the
> configuration has **not** been validated or planned. Review before applying.

What it creates: VPC (2 AZs, one NAT, S3 gateway endpoint), S3 media bucket
(versioned, encrypted, lifecycle rules), SQS plus DLQ, Aurora Serverless v2
PostgreSQL, an ECS Fargate cluster with separate API and worker services, an
ALB, autoscaling, and CloudWatch alarms on DLQ depth and queue age.

## 3. Configure

`terraform output runtime_environment` prints exactly what to set. The task
definitions already carry it:

```
CRE_STORAGE_BACKEND=s3
CRE_QUEUE_BACKEND=sqs
CRE_S3_BUCKET=<bucket>
CRE_SQS_QUEUE_URL=<url>
CRE_DATABASE_HOST=<aurora endpoint>
```

Database credentials arrive from Secrets Manager as `CRE_DB_USERNAME` and
`CRE_DB_PASSWORD`; `Settings.sqlalchemy_url` assembles the DSN, URL-encoding
the password.

## 4. Schema

The SQLAlchemy metadata is created on startup, which is acceptable for a first
deploy. Beyond that, add Alembic and run migrations as a one-off ECS task before
the service rolls.

## Topology

```
          CloudFront ──► S3 (rendered media)
               │
          ALB ─┴─► ECS API service  ──enqueue──►  SQS ──► ECS worker service
                        │                                        │
                        └────────► Aurora Serverless v2 ◄────────┘
```

The API never renders. It ingests, enqueues and serves metadata, so a burst of
uploads does not make the UI unresponsive.

## Operational notes

- **DLQ alarm.** Anything in the dead-letter queue means a render failed three
  times. The message body carries the `job_id`; the job row carries the error.
- **Queue-age alarm.** Fires when the oldest message exceeds 30 minutes, which
  means the worker tier is not keeping up or is crash-looping.
- **Worker scale-in is slow on purpose.** A task killed mid-render loses the
  work and the job is redelivered after the visibility timeout.
- **Graceful shutdown.** The worker entrypoint handles SIGTERM so an in-flight
  render is not killed mid-write, which would leave a partial object in S3.

## What is intentionally not done

- **DynamoDB repository.** The port exists and `build_repository` raises a clear
  `NotImplementedError` pointing at Aurora. Relational fits the access pattern
  (list variants by asset, find by asset and profile), and the JSON document
  columns already absorb schema churn.
- **Lambda for rendering.** A 90-second master exceeds comfortable Lambda limits
  once analysis and a full-rate encode are included, and the vision models make
  the package large. Fargate is the right shape.
- **Per-AZ NAT gateways.** One is sufficient until this is multi-AZ critical,
  and S3 traffic — the bulk of the data movement — already bypasses it via the
  gateway endpoint.

---

<div align="center">

**Creative Reformatting Engine** — built by [Aritro Saha](https://openworld.aritro.cloud)

[openworld.aritro.cloud](https://openworld.aritro.cloud)

</div>
