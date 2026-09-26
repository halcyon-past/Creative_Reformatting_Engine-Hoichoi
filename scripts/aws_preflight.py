"""Check AWS credentials and permissions before attempting a deploy.

Shells out to the AWS CLI rather than importing boto3, so it runs without the
``[aws]`` extra installed.

Every permission check is a **dry run** or a read-only call -- nothing here
creates, modifies or deletes anything.

    python scripts/aws_preflight.py
    python scripts/aws_preflight.py --region us-east-1 --profile personal
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys

GREEN, RED, YELLOW, DIM, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"
OK, FAIL, WARN = f"{GREEN}ok{RESET}", f"{RED}FAIL{RESET}", f"{YELLOW}warn{RESET}"


def run(args: list[str], profile: str | None, region: str | None) -> tuple[int, str, str]:
    cmd = ["aws", *args]
    if profile:
        cmd += ["--profile", profile]
    if region:
        cmd += ["--region", region]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90, check=False)
    except FileNotFoundError:
        return 127, "", "aws CLI not found"
    except subprocess.TimeoutExpired:
        return 124, "", "timed out"
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def main() -> int:
    ap = argparse.ArgumentParser(description="Pre-deploy AWS check")
    ap.add_argument("--profile", default=None)
    ap.add_argument("--region", default="us-east-1")
    args = ap.parse_args()

    print(f"AWS preflight  {DIM}region={args.region} "
          f"profile={args.profile or 'default'}{RESET}\n")

    failures = 0
    warnings = 0

    # ---- tooling --------------------------------------------------------- #
    if shutil.which("aws") is None:
        print(f"[{FAIL}] AWS CLI not on PATH")
        print("        Install: https://aws.amazon.com/cli/")
        return 1
    code, out, _ = run(["--version"], None, None)
    print(f"[{OK}] AWS CLI  {DIM}{out.split()[0] if out else ''}{RESET}")

    for tool, hint in (("terraform", "https://developer.hashicorp.com/terraform/install"),
                       ("docker", "https://docs.docker.com/get-docker/")):
        if shutil.which(tool) is None:
            print(f"[{WARN}] {tool} not on PATH  {DIM}{hint}{RESET}")
            warnings += 1
        else:
            print(f"[{OK}] {tool}")

    # ---- identity -------------------------------------------------------- #
    code, out, err = run(["sts", "get-caller-identity", "--output", "json"],
                         args.profile, args.region)
    if code != 0:
        print(f"\n[{FAIL}] No usable credentials")
        print(f"        {err.splitlines()[0] if err else 'unknown error'}")
        print("\n        Fix: aws configure --profile <name>")
        print("        See docs/DEPLOYMENT.md for where to get the keys.")
        return 1

    identity = json.loads(out)
    arn = identity["Arn"]
    account = identity["Account"]
    print(f"\n[{OK}] Authenticated")
    print(f"        account {account}")
    print(f"        {arn}")
    if ":root" in arn:
        print(f"[{WARN}] These are ROOT credentials. Create an IAM user instead;")
        print(f"        root access keys cannot be scoped or easily rotated.")
        warnings += 1

    # ---- region sanity --------------------------------------------------- #
    code, out, _ = run(["ec2", "describe-availability-zones", "--output", "json"],
                       args.profile, args.region)
    if code == 0:
        zones = [z["ZoneName"] for z in json.loads(out).get("AvailabilityZones", [])]
        print(f"[{OK}] Region {args.region} reachable  {DIM}{len(zones)} AZs{RESET}")
        for needed in ("us-east-1a", "us-east-1b"):
            if args.region == "us-east-1" and needed not in zones:
                print(f"[{WARN}] {needed} not available to this account; "
                      f"edit availability_zones in infra/aws/variables.tf")
                warnings += 1
    else:
        print(f"[{FAIL}] Cannot describe AZs in {args.region} (ec2:DescribeAvailabilityZones)")
        failures += 1

    # ---- permissions, all dry-run or read-only --------------------------- #
    print(f"\n{DIM}Permission checks (dry-run / read-only){RESET}")
    checks: list[tuple[str, list[str]]] = [
        ("ec2:RunInstances",
         ["ec2", "run-instances", "--dry-run", "--image-id", "ami-00000000000000000",
          "--instance-type", "t2.micro"]),
        ("ec2:CreateVpc", ["ec2", "create-vpc", "--dry-run", "--cidr-block", "10.50.0.0/16"]),
        ("ec2:CreateSecurityGroup",
         ["ec2", "create-security-group", "--dry-run",
          "--group-name", "cre-preflight", "--description", "preflight"]),
        ("s3:ListAllMyBuckets", ["s3api", "list-buckets"]),
        ("sqs:ListQueues", ["sqs", "list-queues"]),
        ("iam:ListRoles", ["iam", "list-roles", "--max-items", "1"]),
        ("ecr:DescribeRepositories", ["ecr", "describe-repositories", "--max-items", "1"]),
        ("logs:DescribeLogGroups", ["logs", "describe-log-groups", "--limit", "1"]),
        ("cloudwatch:DescribeAlarms", ["cloudwatch", "describe-alarms", "--max-records", "1"]),
    ]

    for label, argv in checks:
        code, _, err = run(argv, args.profile, args.region)
        lowered = err.lower()
        # A dry-run that gets as far as "would have succeeded" is a pass.
        if code == 0 or "dryrunoperation" in lowered or "request would have succeeded" in lowered:
            print(f"  [{OK}]   {label}")
        elif "unauthorized" in lowered or "accessdenied" in lowered or "not authorized" in lowered:
            print(f"  [{FAIL}] {label}  {DIM}access denied{RESET}")
            failures += 1
        elif "invalidamiid" in lowered or "does not exist" in lowered:
            # Permission was granted; the placeholder resource simply is not real.
            print(f"  [{OK}]   {label}")
        else:
            first = err.splitlines()[0][:90] if err else "unknown"
            print(f"  [{WARN}] {label}  {DIM}{first}{RESET}")
            warnings += 1

    # ---- ECR repositories ------------------------------------------------ #
    print(f"\n{DIM}Container repositories{RESET}")
    for repo in ("hoichoi-cre", "hoichoi-cre-web"):
        code, _, _ = run(["ecr", "describe-repositories", "--repository-names", repo],
                         args.profile, args.region)
        if code == 0:
            print(f"  [{OK}]   {repo}")
        else:
            print(f"  [{WARN}] {repo} does not exist yet")
            print(f"        aws ecr create-repository --repository-name {repo} "
                  f"--region {args.region}")
            warnings += 1

    # ---- verdict --------------------------------------------------------- #
    print()
    if failures:
        print(f"{RED}{failures} blocking problem(s).{RESET} "
              f"Attach infra/aws/deployer-policy.json (or AdministratorAccess) "
              f"and re-run.")
        return 1
    if warnings:
        print(f"{YELLOW}Ready, with {warnings} thing(s) to sort out above.{RESET}")
        return 0
    print(f"{GREEN}Ready to deploy.{RESET}")
    print(f"  cd infra/aws/free-tier && terraform init && terraform plan")
    return 0


if __name__ == "__main__":
    sys.exit(main())
