---
title: "Provisioning Traefik with Docker Compose and TLS Termination via Internal CA"
date: 2025-05-02
tags: ["Traefik", "Reverse Proxy", "Samba", "Internal CA","Network Security", "Home Lab"]
categories: ["My Home Lab Journey"]
draft: false
---

## Overview

This guide documents the process of deploying the Traefik reverse proxy using Docker Compose with TLS termination handled by a self-hosted internal certificate authority (CA). It includes all key configuration decisions, troubleshooting steps, and final validation outcomes.

## Objectives

- Deploy Traefik using Docker Compose
    
- Enable HTTPS via static and dynamic configuration
    
- Load a custom certificate signed by an internal CA
    
- Validate secure access to the Traefik dashboard
    

## Environment

- Operating System: Ubuntu Server
    
- Traefik Version: 2.11
    
- Docker & Docker Compose
    
- Internal PKI: Self-hosted CA issuing trusted certificates
    
- Domain: Custom internal domain (e.g., `*.example.lan`)
    

## Directory Structure

```
~/traefik/
├── traefik.yml               # Static configuration
├── docker-compose.yml        # Docker service definition
├── config/
│   └── dynamic.yml           # Dynamic configuration
└── certs/
    ├── example.lan.crt       # Server certificate
    ├── example.lan.key       # Private key
    └── ca.crt                # Root CA certificate (optional for clients)
```

## Step-by-Step Configuration

### 1. Static Configuration (`traefik.yml`)

```
entryPoints:
  web:
    address: ":80"
  websecure:
    address: ":443"

api:
  dashboard: true

log:
  level: DEBUG

providers:
  file:
    filename: /home/user/traefik/config/dynamic.yml
    watch: true
```

### 2. Dynamic Configuration (`config/dynamic.yml`)

```
tls:
  certificates:
    - certFile: /home/user/traefik/certs/example.lan.crt
      keyFile: /home/user/traefik/certs/example.lan.key

http:
  routers:
    traefik-dashboard:
      rule: "Host(`traefik.example.lan`)"
      entryPoints:
        - websecure
      service: api@internal
      tls: true
```

### 3. Docker Compose File (`docker-compose.yml`)

```
version: "3.8"
services:
  traefik:
    image: traefik:v2.11
    container_name: traefik
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./traefik.yml:/home/user/traefik/traefik.yml
      - ./config/dynamic.yml:/home/user/traefik/config/dynamic.yml
      - ./certs:/home/user/traefik/certs
```

> Note: All file paths are absolute within the container for consistency.

## Troubleshooting Process

### Problem: Curl to HTTPS endpoint failed (Connection Refused)

- **Symptoms:**
    
    - `curl -vk https://traefik.example.lan` returns connection refused.
        
    - Port 443 shown as open via `ss -tuln`, but no container binding occurred.
        
- **Resolutions Attempted:**
    
    - Verified ports 80/443 availability (`netstat`, `lsof`, `ss`)
        
    - Ensured `docker-compose down` fully removed container states
        
    - Restarted Docker service to release potentially held ports
        

### Problem: No Traefik logs visible

- **Symptoms:** `docker logs traefik` showed no output
    
- **Fix:** Added `log.level: DEBUG` to `traefik.yml` and confirmed config was mounted properly
    

### Problem: Dashboard loads with default self-signed certificate

- **Symptoms:** Dashboard displayed a browser warning for `TRAEFIK DEFAULT CERT`
    
- **Fix:**
    
    - Verified dynamic config was correctly referenced and mounted
        
    - Confirmed cert and key filenames were correct
        
    - Restarted Traefik after changing mount paths to match container expectations
        

### Final Fix: Proper Mounting and Configuration Paths

- All paths in the YAML files were made fully absolute and consistently mounted into the container
    
- Docker Compose volumes were validated against container paths
    
- After restarting the container stack, the browser showed the correct certificate issued by the internal CA
    

## Final Validation

- Verified TLS certificate via browser: matched `CN=traefik.example.lan`, signed by internal root CA
    
- Accessed dashboard via `https://traefik.example.lan:443`
    
- No browser warnings when root CA was installed in local trust store
    

## Conclusion

This deployment demonstrates a secure and customizable method to run Traefik with HTTPS backed by an internal certificate authority. The setup supports Docker-based dynamic service exposure and can serve as a foundation for SSO, mTLS, or zero-trust architectures.

Future steps may include:

- Integrating with Authentik for OIDC
    
- Adding automatic TLS renewal via internal CA workflows
    
- Using Traefik middlewares for authentication, rate-limiting, or header injection