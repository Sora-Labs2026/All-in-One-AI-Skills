# Machine images: AMIs, Azure images and Windows builds with Packer

Read this when you build or change virtual machine images (AWS AMIs, Azure managed or Compute Gallery images, Windows images), write Packer templates, track image versions, or clean up old images.

An image build launches a real, billable machine in a real account, runs provisioning on it and stores snapshots that bill until deleted. Validate locally, then run a build only with the user's go-ahead, in a build account or resource group, and check afterwards that nothing was left running.

## When to bake an image

- **Bake** what is slow, large or must be identical everywhere: OS patches, agents (monitoring, security, SSM), language runtimes, hardening baselines. Baked images boot fast and are reproducible.
- **Configure at boot** (cloud-init, user data, a configuration agent) what differs per environment or changes often: endpoints, feature settings. Secrets are fetched at boot from a secret store by the instance's role; never bake them in.
- Managed alternatives exist: EC2 Image Builder and Azure VM Image Builder run pipelines as services, with their own scheduling and distribution. Packer suits teams that build for several platforms or want builds in their own CI.

## Packer basics (HCL2)

```hcl
packer {
  required_plugins {
    amazon = { source = "github.com/hashicorp/amazon", version = "~> 1.3" }
  }
}

variable "region"     { type = string }
variable "git_commit" { type = string }

locals {
  stamp = formatdate("YYYYMMDD-hhmmss", timestamp())
}

source "amazon-ebs" "base" {
  region        = var.region
  instance_type = "t3.small"
  ami_name      = "base-ubuntu-2404-${local.stamp}"
  encrypt_boot  = true                       # encrypted snapshots; add kms_key_id for a customer key
  imds_support  = "v2.0"                     # images launch with IMDSv2 required

  source_ami_filter {
    filters = {
      name                = "ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"
      virtualization-type = "hvm"
      root-device-type    = "ebs"
    }
    owners      = ["099720109477"]           # the publisher's account; never leave owners open
    most_recent = true
  }

  ssh_username  = "ubuntu"
  ssh_interface = "session_manager"          # no inbound SSH; needs the SSM agent and an instance profile
  temporary_iam_instance_profile_policy_document {
    Version = "2012-10-17"
    Statement {
      Effect   = "Allow"
      Action   = ["ssm:UpdateInstanceInformation", "ssmmessages:*", "ec2messages:*"]
      Resource = ["*"]
    }
  }

  tags = {
    source_ami = "{{ .SourceAMI }}"
    git_commit = var.git_commit
    built_by   = "packer"
  }
}

build {
  sources = ["source.amazon-ebs.base"]

  provisioner "shell" {
    inline = [
      "cloud-init status --wait",
      "sudo apt-get update",
      "sudo DEBIAN_FRONTEND=noninteractive apt-get -y upgrade",
    ]
  }

  provisioner "shell" {
    script = "scripts/harden.sh"             # reviewed, versioned script; no curl | sh
  }

  provisioner "shell" {
    inline = ["sudo cloud-init clean --logs", "sudo rm -f /etc/ssh/ssh_host_*", "history -c"]
  }

  post-processor "manifest" {
    output = "packer-manifest.json"          # records the artifact ID for the next pipeline step
  }
}
```

```bash
packer init .
packer fmt -check .
packer validate -var region=eu-west-1 -var git_commit=abc123 .
# Building launches resources; run only with the user's go-ahead:
packer build -var region=eu-west-1 -var git_commit=$(git rev-parse HEAD) .
```

- Pin plugin versions in `required_plugins` and commit the template; `packer init` downloads plugins from the network, so it is a dependency install.
- **Always pin the base image owner** (or publisher, offer and SKU on Azure). A name filter without an owner can match an image anyone published.
- Wait for cloud-init to finish before provisioning, or package locks and half-written files cause flaky builds.
- `-on-error=abort` leaves the build machine running for debugging. That keeps billing and can leave an instance with a temporary key pair reachable; use it only with approval and clean up immediately. The default cleans up.
- Use the communicator over Session Manager (AWS) or keep the temporary security group restricted to the build runner's address; avoid opening SSH or WinRM to `0.0.0.0/0`.

## AWS specifics

- `ami_regions` copies the image to other regions; with encryption, give each region a key (`region_kms_key_ids`). `ami_users` or `ami_org_arns` share the image; sharing with the wrong account exposes everything baked into it.
- Tag images and their snapshots with base image, commit and build time, and publish the new AMI ID somewhere consumers read it (an SSM parameter, an image registry) instead of having them search by name.
- Deregistering an AMI does not delete its snapshots. Retire old images by setting a deprecation time, then deregister and delete their snapshots together, after confirming no launch template, Auto Scaling group or pipeline still references them.
- Amazon Inspector can scan EC2 instances launched from the image; launch one test instance from it and check the findings before promoting the image.

## Azure specifics

```hcl
source "azure-arm" "base" {
  use_azure_cli_auth = true                  # local runs; in CI prefer OIDC or managed identity if the plugin version supports it
  subscription_id    = var.subscription_id

  os_type         = "Linux"
  image_publisher = "Canonical"
  image_offer     = "ubuntu-24_04-lts"
  image_sku       = "server"
  location        = "westeurope"
  vm_size         = "Standard_D2s_v5"

  shared_image_gallery_destination {
    subscription         = var.subscription_id
    resource_group       = "rg-images"
    gallery_name         = "galImages"
    image_name           = "base-ubuntu"     # the image definition must already exist
    image_version        = var.image_version # Major.Minor.Patch, unique per build
    replication_regions  = ["westeurope", "northeurope"]
  }
}
```

- Prefer an Azure Compute Gallery over standalone managed images: versions, replication across regions and sharing. Packer does not create the gallery or the image definition; create those in IaC first.
- Gallery image versions are immutable; generate a new semantic version each build (for example from the pipeline run number) rather than overwriting.
- Generalize as the last provisioner. Linux on Azure: `sudo /usr/sbin/waagent -force -deprovision+user && export HISTSIZE=0 && sync`. Skipping it produces images whose VMs fail provisioning or keep the build user.
- Avoid client secrets in templates or variables files. Use Azure CLI login locally, and federated credentials or a managed identity in CI. Grant the build identity rights on the build resource group and the gallery only, not Contributor on the subscription.
- Packer creates a temporary resource group per build by default; a failed or interrupted build can leave it behind. Check for `pkr-Resource-Group-*` groups after failures.

## Windows images

- Communicator: WinRM over HTTPS (port 5986) with a certificate, or OpenSSH, which Windows Server 2019 and later include. Do not enable unencrypted WinRM or Basic authentication over HTTP; credentials then cross the network in a recoverable form. On Azure the plugin configures WinRM over HTTPS with a temporary certificate.
- Install software from pinned, checksummed sources or an internal repository. Running scripts downloaded at build time (`iex` of a web page) executes whatever the server returns.
- Windows Update makes builds long (often an hour or more) and needs `windows-restart` provisioners between passes; starting from a recently patched marketplace image shortens it.
- Generalize with Sysprep as the final step using the platform's documented method: EC2Launch v2 on AWS, `Sysprep.exe /oobe /generalize /quiet /quit /mode:vm` followed by waiting for the generalized state on Azure. Follow the plugin documentation for the exact command for your OS version.

## Tracking and promoting images

- Record every build's artifact IDs, base image, commit and test results. An image registry such as HCP Packer (the `hcp_packer_registry` block) stores this metadata with channels (`dev`, `production`) and revocation; consumers then resolve "the production image" through a data source instead of a hard-coded ID. An SSM parameter or Key Vault reference per channel is a lighter alternative.
- Promote by moving a channel or parameter after the image passes tests, so rollback is moving it back.
- Rebuild on a schedule (for example weekly) so patches flow in even when nothing else changed, and scan the result.

## Done when

- [ ] `packer fmt -check` and `packer validate` pass, plugins are pinned, and the base image owner or publisher is pinned.
- [ ] No secrets, keys or credentials are baked in; generalization runs last; temporary access is restricted.
- [ ] The build ran only with the user's go-ahead, and the report confirms no leftover instances, resource groups or key pairs.
- [ ] The new image is tagged, recorded and tested before promotion; old images are retired together with their snapshots.

## Pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| Build hangs at "Waiting for SSH" or WinRM | Network path or security group blocks the communicator | Session Manager, a subnet with a route to the runner, or a narrowed temporary rule |
| Image name already exists | Static name | Timestamp or build number in the name |
| Gallery publish fails | Image definition missing or version reused | Create the definition in IaC; unique version per build |
| VMs from the image fail provisioning | Not generalized, or generalized twice | Single final deprovision or Sysprep step |
| Storage bill keeps growing after cleanup | AMIs deregistered, snapshots kept | Delete snapshots with their images |
