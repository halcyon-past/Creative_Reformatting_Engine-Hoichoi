# Running on the AWS Free Tier

*Running the whole system inside the AWS Free Tier, and what that actually costs you.*

<sub>[← Back to the README](../README.md) &middot; [Architecture](ARCHITECTURE.md) &middot; [Audit](AUDIT.md) &middot; [AWS migration](AWS_MIGRATION.md) &middot; [Free tier](FREE_TIER.md)</sub>

---

`infra/aws/free-tier/` provisions the whole system inside the Free Tier. It is
a deliberately different shape from `infra/aws/` (the scalable stack), because
several services used there have no free tier at all.

| Concern | Scalable stack | Free-tier stack | Why |
|---|---|---|---|
| Compute | ECS Fargate | **EC2 `t2.micro`** | Fargate has no free tier; EC2 micro gives 750 h/month |
| Database | Aurora Serverless v2 | **SQLite on EBS** | Aurora has no free tier at any size |
| Egress | NAT Gateway | **public subnet** | NAT is ~$32/month and never free |
| Ingress | Application Load Balancer | **nginx on the instance** | ALB free hours expire and LCUs bill from day one |
| Secrets | Secrets Manager | **SSM Parameter Store** | Secrets Manager is paid; Parameter Store standard is free |
| Queue | SQS | **SQS** | unchanged — 1M requests/month is *always* free |
| Storage | S3 | **S3** | unchanged — 5 GB for 12 months |

The application code is identical. Only the environment differs.

## Deploy

```bash
# 1. build and push both images
aws ecr create-repository --repository-name hoichoi-cre
aws ecr create-repository --repository-name hoichoi-cre-web
docker build -f backend/Dockerfile  -t <acct>.dkr.ecr.<region>.amazonaws.com/hoichoi-cre:v1 .
docker build -f frontend/Dockerfile -t <acct>.dkr.ecr.<region>.amazonaws.com/hoichoi-cre-web:v1 .
docker push <acct>.dkr.ecr.<region>.amazonaws.com/hoichoi-cre:v1
docker push <acct>.dkr.ecr.<region>.amazonaws.com/hoichoi-cre-web:v1

# 2. provision
cd infra/aws/free-tier
cp terraform.tfvars.example terraform.tfvars   # set the two image URIs
terraform init && terraform plan && terraform apply
```

`terraform output app_url` gives the address. Shell in without opening port 22:

```bash
aws ssm start-session --target $(terraform output -raw instance_id)
```

> Terraform was not installed in the environment this was authored in, so the
> configuration has **not** been through `validate` or `plan`. Review it first.

## Before you deploy

Check credentials and permissions first — every check is dry-run or read-only
and creates nothing:

```bash
python scripts/aws_preflight.py --profile <your-profile> --region us-east-1
```

The principal running Terraform needs more than the runtime roles the stack
creates for itself. `infra/aws/deployer-policy.json` has the scoped set;
`AdministratorAccess` is simpler and defensible for a first deploy.

The instance role includes **ECR pull permissions**, which are easy to miss: the
user-data runs `aws ecr get-login-password` and `docker run` at boot, and
without them the instance comes up healthy while serving nothing. Terraform will
not catch that — it is a runtime failure, not a plan error. After the first boot,
confirm the containers actually started:

```bash
aws ssm start-session --target $(terraform output -raw instance_id)
docker ps        # expect cre-api and cre-web
```

## What "free" actually means here

**Always free, indefinitely:**
- SQS — 1M requests/month. At this workload the queue genuinely costs nothing.
- CloudWatch alarms — 10 of them. Two are configured.
- S3 Gateway VPC endpoint.
- Elastic IP, while attached to a running instance.

**Free for 12 months from account creation, then billed:**
- EC2 750 h/month of `t2.micro` — enough for one instance running continuously.
  After 12 months, roughly **$8–9/month**.
- EBS 30 GB.
- S3 5 GB storage, 20k GET, 2k PUT.
- Data transfer out, 100 GB/month.

## The three things that will actually bite you

**1. `t2.micro` is 1 vCPU and 1 GB of RAM.** Decoding 1080p video with the
MediaPipe models loaded does not comfortably fit in either. The user-data
provisions 2 GB of swap and pins `CRE_WORKER_CONCURRENCY=1`, which makes it work
rather than crash — but renders are slow, and a 30 s reel takes several minutes.
If you are doing anything beyond evaluation, set `instance_type = "t3.small"`
(2 vCPU / 2 GB, not free, about $15/month). Nothing else changes.

Note the instance type is region-dependent for Free Tier eligibility: the
allowance covers **`t2.micro` in regions where it exists** — which includes
`us-east-1`, the default here — and `t3.micro` only where t2 is unavailable.
Setting `t3.micro` in `us-east-1` would quietly fall outside the allowance.

**2. S3's 5 GB fills fast.** The test video alone is 280 MB. A handful of
masters exceeds the allowance, and S3 then bills silently. The lifecycle rule
expires masters after `expire_masters_after_days` (default 7) on the reasoning
that a variant can be re-rendered from a fresh upload. **Tune this before you
rely on it** — if you need masters kept, set it to 0 and budget for storage.

**3. CPU credits.** `t2.micro` is burstable. Sustained rendering drains the
credit balance, after which the instance is throttled to its baseline and
renders slow to a crawl. The `cpu-credits-low` alarm fires before that happens.
`t2` defaults to **standard** mode (a hard throttle, no surprise bill); `t3`
defaults to **unlimited**, which bills for surplus credits — if you switch
families, set `credit_specification` deliberately.

## Reducing cost further

- `CRE_ANALYSIS_FPS=6` (already set) roughly halves analysis time versus 10.
- `CRE_MAX_REEL_SOURCE_SECONDS=60` (already set) caps how much of a long master
  is analysed.
- Stop the instance when idle; the Elastic IP stays attached and the address is
  preserved. EBS still bills, but within the 30 GB allowance that is free for
  the first 12 months.

## Monitoring the bill

Free Tier does not stop charges — it discounts them. Set a budget alarm before
deploying anything:

```bash
aws budgets create-budget --account-id <acct> \
  --budget '{"BudgetName":"cre","BudgetLimit":{"Amount":"5","Unit":"USD"},"TimeUnit":"MONTHLY","BudgetType":"COST"}'
```

`terraform output free_tier_notes` restates the limits and what to watch.

---

<div align="center">

**Creative Reformatting Engine** — built by [Aritro Saha](https://openworld.aritro.cloud)

[openworld.aritro.cloud](https://openworld.aritro.cloud)

</div>
