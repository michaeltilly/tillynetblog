---
title: "Provisioning Authentik Middleware with Traefik Reverse Proxy Using Internal Samba AD CA"
date: 2025-05-13
tags: ["Traefik", "Reverse Proxy", "Authentik", "Authentik Outposts", "Middleware", "Samba", "Active Directory", "Internal CA","Network Security", "Docker", "Docker Compose", "Home Lab"]
categories: ["My Home Lab Journey"]
draft: false
---

## Introduction

This guide details how I provisioned **Authentik** as a middleware authentication provider integrated with **Traefik** reverse proxy, using TLS certificates issued by my internal **Samba Active Directory Certificate Authority (CA)**. The result is a secure, SSO-enabled reverse proxy setup that leverages **LDAPS** to enforce access control for authorized users in my Active Directory.

This solution enables:

- Trusted HTTPS access to services proxied through Traefik.
    
- SSO enforcement using Authentik via the forwardAuth middleware.
    
- Certificate-based trust rooted in my Samba 4 AD CA.
    
- Authentik outpost (proxy) deployment as a sidecar container to manage authentication flows.

## Prerequisites

- Working Traefik reverse proxy deployed via Docker Compose
    
- Authentik server accessible at `https://authentik.example.lan`
    
- Valid internal CA-signed certificates for both Traefik and Authentik
    
- Samba 4 running as internal CA with LDAPS enabled
    
- Docker and Docker Compose installed
    
- DNS records pointing to correct internal service IPs (e.g., `traefik.example.lan`)

---

## Authentik Setup Notes

- Authentik was configured to use **LDAPS** for user directory integration against Samba AD.
    
- Users from a specific group (e.g., `AuthorizedSSOUsers`) were assigned access to the Traefik application.
    
- An embedded outpost was initially tested, but the dedicated container provided cleaner integration.

---

## Directory Layout

```bash
📁 Directory Layout
/home/username/traefik-authentik/  
├── docker-compose.yml # Main Docker Compose file  
├── Dockerfile # Custom Dockerfile for the Authentik outpost  
├── .env # (Optional) Environment variables file  
├── certs/ # Internal CA and TLS certs  
│ ├── ca.crt # Internal Samba AD CA certificate (PEM format)  
│ ├── authentik.example.lan.crt # Authentik SSL certificate  
│ ├── authentik.example.lan.key # Authentik SSL key  
│ ├── traefik.example.lan.crt # Traefik dashboard SSL certificate  
│ └── traefik.example.lan.key # Traefik dashboard SSL key  
├── traefik/  
│ ├── traefik.yml # Static Traefik configuration  
│ ├── middleware.yml # Middleware definition for Authentik SSO  
│ └── tls.yml # TLS options and certificate stores  
```

### Notes:
- The `certs/` folder is mounted into containers to provide all necessary trusted CA and TLS materials.
- All certificates must be in PEM format.
- The `Dockerfile` should use a multi-stage approach or add the CA and call `update-ca-certificates` as `root`.
- The `traefik/` folder holds Traefik's dynamic configuration files.
- You can substitute `/home/username/traefik-authentik/` with any appropriate directory, but all relative volume mounts in `docker-compose.yml` should align.

---

## 1. Traefik Configuration Overview
### `traefik.yml`

```yaml
global:
  checkNewVersion: false
  sendAnonymousUsage: false
accessLog: {}
log:
  level: TRACE
api:
  dashboard: true
  insecure: false
  debug: false
entryPoints:
  web:
    address: :80
    http:
      redirections:
        entryPoint:
          to: websecure
          scheme: https
  websecure:
    address: :443
serversTransport:
  insecureSkipVerify: true # Useful during internal CA testing phase
providers:
  docker:
    exposedByDefault: false
    endpoint: 'unix:///var/run/docker.sock'
    watch: true
  file:
    directory: /etc/traefik/conf/
    watch: true
```

This file defines:

- The two Traefik entrypoints (HTTP and HTTPS)
    
- Enabling the dashboard
    
- Providers (Docker and external files)
    
- Disabling strict TLS validation for initial setup

### `conf/middleware.yml`

```yaml
http:
  middlewares:
    authentik:
      forwardAuth:
        address: http://NAME-OF-AUTHENTIK-OUTPOST:9000/outpost.goauthentik.io/auth/traefik
        trustForwardHeader: true
        authResponseHeaders:
          - X-authentik-username
          - X-authentik-groups
          - X-authentik-entitlements
          - X-authentik-email
          - X-authentik-name
          - X-authentik-uid
          - X-authentik-jwt
          - X-authentik-meta-jwks
          - X-authentik-meta-outpost
          - X-authentik-meta-provider
          - X-authentik-meta-app
          - X-authentik-meta-version
```

This `middleware.yml` file configures Traefik to forward requests to the Authentik outpost container to enforce authentication and pass key user identity headers.

### `conf/tls.yml`

```yaml
tls:
  certificates
    - certFile: /var/traefik/certs/traefik.example.lan.crt
      keyFile: /var/traefik/certs/traefik.example.lan.key
    - certFile: /var/traefik/certs/authentik.example.lan.crt
      keyFile: /var/traefik/certs/authentik.example.lan.key
  stores:
    default:
      defaultCertificate:
        certFile: /var/traefik/certs/traefik.example.lan.crt
        keyFile: /var/traefik/certs/traefik.example.lan.key
  options:
    default:
      minVersion: VersionTLS12
      sniStrict: true
      curvePreferences:
        - CurveP256
        - CurveP384
        - CurveP521
      cipherSuites:
        - TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256
        - TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384
        - TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305_SHA256
        - TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384
        - TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256
        - TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305
```

The `tls.yml` file Specifies TLS certificate and key files signed by the internal Samba CA.

---
## 2. Docker Compose Configuration

### `docker-compose.yml`

Create a unified `docker-compose.yml` that includes both `traefik` and the `authentik-outpost`:

```yaml
services:
  traefik:
    container_name: traefik
    image: traefik:latest
    ports:
      - 80:80
      - 443:443
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - filepathto/traefik.yml:/etc/traefik/traefik.yml:ro
      - filepathto/traefik/config/:/etc/traefik/conf:ro
      - filepathto/traefik/certs/:/var/traefik/certs/:rw
    networks:
      - frontend
      - backend
    labels:
      - traefik.enable=true
      - traefik.http.routers.traefik.rule=Host(`traefik.example.lan`)
      - traefik.http.routers.traefik.entrypoints=websecure
      - traefik.http.routers.traefik.tls=true
      - traefik.http.routers.traefik.middlewares=authentik@file
      - traefik.http.routers.traefik.service=api@internal
    restart: unless-stopped
  authentik-outpost:
    container_name: traefik-authentik-outpost
    image: custom-authentik-outpost #use custom image to load trusted internal CA cert into container
    volumes:
      - filepathto/certs:/certs:ro
    restart: unless-stopped
    networks:
      - frontend
      - backend
    environment:
      - AUTHENTIK_HOST=https://authentik.example.lan
      - AUTHENTIK_INSECURE=false
      - REQUESTS_CA_BUNDLE=/certs/ca.crt
      - LOG_LEVEL=debug
      - AUTHENTIK_HOST_BROWSER=https://authentik.example.lan
      - AUTHENTIK_TOKEN=xxxxxxxxxxxxxxx   # Replace with Authentik outpost token

networks:
  frontend:
    external: true
  backend:
    external: true
```

**Highlights:**

- Traefik loads configuration from mounted YAML files.
    
- Authentik outpost uses the internal CA to validate Authentik's certificate.
    
- If `AUTHENTIK_INSECURE=false` fails due to CA trust, temporarily flip it to `true`.
    
- Note: Replace `custom-authentik-outpost` with the name of the custom image (see next step).

---

## 3. Custom Dockerfile for Outpost (Trust Internal CA)

To resolve certificate validation issues, a custom image was created by appending your Samba AD CA to the container's trust store:

### `Dockerfile` for Custom Outpost Image

To trust my internal Samba CA, I built a custom image for the Authentik proxy outpost:

`Dockerfile` -- name the file exactly like this
```
FROM ghcr.io/goauthentik/proxy:latest
COPY ./certs/ca.crt /usr/local/share/ca-certificates/ca.crt
RUN update-ca-certificates
```

Then build the file with:

```bash
sudo docker build -t custom-authentik-outpost .
```

This step ensured the Authentik outpost container would trust my internal certificate hierarchy.

---

## 4. Authentik Configuration

In the Authentik dashboard:

### Application

- Name: traefik-dashboard
    
- Slug: `traefik-dashboard`
    
- Launch URL: `https://traefik.example.lan/dashboard/`
    
- Provider: The created proxy provider (in my case traefik-forward-auth)
     
- Policy engine mode: any

### Provider (Proxy)

- Type: Proxy
    
- Name: traefik-forward-auth
    
- Authorization flow: default-provider-authorization-explicit-consent (Authorize Application)
    
- Use forward auth (single application)
	- the external host address should be the FQDN that you'll want to access the application at
	- in my case that is: https://traefik.tillynet.lan since I want to protect my Traefik dashboard with Authentik
- Token Validity: hours=24
    

### Outpost

Create a new Authentik Outpost to deploy in the same docker compose config file as traefik (see the traefik `docker-compose.yml` above for deploying the outpost as a docker container)

- Name: traefik-authentik-outpost
    
- Type: Proxy
    
- Integration: Local Docker connection
    
- Applications: Link your `traefik-dashboard` application
    
- Token: After outpost copy your Authentik token and paste it in `docker-compose.yml`
    
- Healthy check: Ensure Authentik sees outpost as healthy after the docker container for the outpost has been deployed
    

---

## 6. Start the Stack

```bash
docker compose up -d
```

You should now be able to access:

- `https://traefik.example.lan/dashboard/` — protected by Authentik SSO
    

---

## 6. Troubleshooting Tips

- Ensure your internal CA is correctly mounted and trusted in the custom container.
    
- If you see `x509: certificate signed by unknown authority`, the CA is likely missing.
    
- Use `docker logs` for both Traefik and Outpost to trace errors.
    
- Check firewall/NAT between 172.x Docker bridge and your internal CA if `connection reset by peer` occurs. MAKE SURE YOU ARE NOT USING THE DEFAULT DOCKER NETWORK.
    

---

## 7. ## Final Outcome

You should now be able to:

- Visit `https://traefik.example.lan/dashboard/`
    
- Be redirected to Authentik SSO
    
- Log in via your authorized AD credentials using LDAPS
    
- Gain access to the secured dashboard with a valid TLS certificate
    

---

This project brought together reverse proxying, identity management, and internal PKI in a way that’s reproducible and production-ready for any homelab setup.