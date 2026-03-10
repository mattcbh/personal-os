# GCP Infrastructure (Inbox Triage v2)

Terraform scaffolding for the cloud deployment target:

- Cloud Run services: `triage-api`, `triage-worker`
- Cloud Tasks queues: run/draft/send/reconcile
- Cloud SQL Postgres instance
- Cloud Scheduler AM/PM triggers
- Secret Manager placeholders for OAuth/API credentials
- Cloud Storage artifacts bucket

## Bootstrap

```bash
cd ~/Obsidian/personal-os/core/automation/triage_v2/infra/gcp
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform plan
terraform apply
```

## Notes

- Scheduler HTTP targets assume Cloud Run endpoint auth is handled at the platform layer.
- Secrets are created as containers only; add secret versions with real values after apply.
- Production hardening should add VPC, private service networking, and least-privilege IAM bindings.
