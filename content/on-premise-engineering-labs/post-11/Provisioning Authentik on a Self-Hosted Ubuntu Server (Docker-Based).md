---
title: "Provisioning Authentik for SSO on a Self-Hosted Ubuntu Server (Docker-Based)"
date: 2025-04-28
tags: ["Authentik", "SSO", "Docker", "Docker Compose", "Home Lab", "Ubuntu Server", "Authentication"]
categories: ["On-Premise Engineering Labs"]
draft: false
---

This guide documents the step-by-step process used to provision an [Authentik](https://goauthentik.io) identity provider server on a self-hosted Ubuntu Server using Docker and Docker Compose. This setup is suitable for advanced home lab environments and follows production-grade containerization practices.

## Prerequisites

- A fresh or existing Ubuntu 22.04 or 24.04 LTS server.
- `sudo` privileges on the system.
- Static IP and DNS configuration recommended.
- System updates applied.

---

## Step 1: Install Docker Engine

Follow the official Docker post-install guide to install and configure Docker for non-root use:

**Reference**: [Docker Post-install Guide](https://docs.docker.com/engine/install/linux-postinstall/)

```bash
# Update and install required packages
sudo apt update && sudo apt upgrade -y
sudo apt install -y ca-certificates curl gnupg

# Add Docker's official GPG key
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Add the Docker repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Optional: Add your user to the docker group to avoid using sudo with every docker command
sudo usermod -aG docker $USER
newgrp docker
```

---

## Step 2: Install Docker Compose (Standalone)

Authentik uses `docker-compose.yml` to manage multi-container services.

**Reference**: [Docker Compose Install Guide](https://docker-docs.uclv.cu/compose/install/)

```bash
# Download Docker Compose binary
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
  -o /usr/local/bin/docker-compose

# Set permissions
sudo chmod +x /usr/local/bin/docker-compose

# Verify installation
docker-compose version
```

---

## Step 3: Create Authentik Directory and Configuration

**Reference**: [Authentik Docker Install Guide](https://docs.goauthentik.io/docs/install-config/install/docker-compose)

```bash
# Create and navigate to the installation directory
mkdir -p ~/authentik
cd ~/authentik

#Download the official docker-compose.yml
curl -o docker-compose.yml https://goauthentik.io/docker-compose.yml

#Create an .env file to override confiugration values
cat <<EOF > .env
AUTHENTIK_SECRET_KEY=$(openssl rand -hex 32)
POSTGRES_PASSWORD=$(openssl rand -hex 16)
AUTHENTIK_EMAIL__FROM="admin@example.com"
AUTHENTIK_EMAIL__HOST="localhost"
EOF
```

---

## Step 4: Start Authentik Services

Start the containers using Docker Compose:

```bash
docker-compose pull   # Pull latest images
docker-compose up -d  # Start in detached mode
```

---

## Step 5: Access Web Interface

Once running, access Authentik at:

```
http://<your-server-ip>:9000
or
https://<your-server-ip>:9443
```

---

## Step 6: Initial Setup Wizard

I had some trouble getting the initial setup wizard for Authentik to cooperate with me. The wizard would not let me setup the default `akdmin` account on a http connection. To resolve this issue do the following:

Be sure that the docker container for authentik-server is listening on port 9443:

```bash
sudo ss -tulpn | grep LISTEN
```

Access the initial setup wizard using the link below:

```
https://<your server's IP or hostname>:9443/if/flow/initial-setup/
```

---
## Related Posts

[Provisioning Samba Active Directory Domain Controller and Windows Domain Integration](https://blog.tillynet.com/my-home-lab-journey/provisioning-samba-active-directory-domain-controller-and-windows-domain-integration/)
[Integrating Samba 4 Active Directory with Authentik via LDAPS](https://blog.tillynet.com/my-home-lab-journey/integrating-samba-4-active-directory-with-authentik-via-ldaps/)