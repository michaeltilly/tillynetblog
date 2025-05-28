---
title: "Building a Proper PKI Chain of Trust in a Samba AD Lab"
date: 2025-05-20
tags: ["Traefik", "Reverse Proxy", "Authentik", "Samba", "Active Directory", "Internal CA", "Chain of Trust", "PKI", "LDAPS", "OIDC", "HTTPS", "Network Security", "Docker", "Docker Compose", "Home Lab"]
categories: ["On-Premise Engineering Labs"]
draft: false
---

## Overview

This post documents how I implemented a production-style Public Key Infrastructure (PKI) inside my Samba 4 Active Directory (AD) lab. The project simulates how enterprise environments separate certificate authority responsibilities to promote security and manageability. I built a trust chain starting with an offline Root CA, promoted my Samba DC as an Intermediate CA, and automated service certificate signing for applications like Traefik and Authentik.

---

## Why a PKI Chain of Trust?

In enterprise networks, it's a best practice to:

- Keep the **Root Certificate Authority (CA)** offline to minimize risk
    
- Delegate signing authority to an **Intermediate CA**
    
- Sign service certificates (LDAPS, HTTPS, etc.) from the Intermediate
    

Initially, my Samba AD DC handled both Root CA and service cert issuance, which is not secure long-term. This project restructures that into a hardened, tiered architecture.

---

## PKI Topology

```
Root CA (Offline)
 └── Intermediate CA (Samba DC)
     ├── samba-ldaps.crt
     ├── authentik.tld
     └── traefik.tld
```

---

## Phase 1: Offline Root CA

This was done on a separate offline VM or system.

```bash
mkdir -p ~/rootCA/{certs,crl,newcerts,private,csr}
touch ~/rootCA/index.txt
echo 1000 > ~/rootCA/serial
chmod 700 ~/rootCA/private
```

Generate the Root CA key and certificate:

```bash
openssl genrsa -aes256 -out ~/rootCA/private/rootCA.key.pem 4096
openssl req -x509 -new -key ~/rootCA/private/rootCA.key.pem \
  -sha256 -days 3650 -out ~/rootCA/certs/rootCA.cert.pem \
  -subj "/C=US/ST=State/O=Lab/OU=PKI/CN=Root CA"
```

---

## Phase 2: Intermediate CA (Samba DC)

On the Samba DC, generate the Intermediate CA private key and CSR:

```bash
mkdir -p /usr/local/samba/private/pki/intermediate
cd /usr/local/samba/private/pki/intermediate
openssl genrsa -out intermediate.key.pem 4096
openssl req -new -key intermediate.key.pem \
  -out intermediate.csr.pem \
  -subj "/C=US/ST=State/O=Lab/OU=CA/CN=Intermediate CA"
```

Transfer the CSR to the offline Root CA host, then:

```bash
openssl ca -config openssl_root.cnf \
  -extensions v3_intermediate_ca \
  -days 1825 -notext -md sha256 \
  -in csr/intermediate.csr.pem \
  -out certs/intermediate.cert.pem
```

Create the chain:

```bash
cat certs/intermediate.cert.pem certs/rootCA.cert.pem > certs/ca-chain.cert.pem
```

Transfer intermediate.cert.pem and ca-chain.cert.pem back to the Samba server.

---

## Samba TLS Configuration

Save the following files:

```
/usr/local/samba/private/tls/
├── intermediate.key
├── intermediate.crt
├── ca-chain.crt
```

Edit `smb.conf`:

```
[global]
tls enabled  = yes
tls keyfile  = /usr/local/samba/private/tls/intermediate.key
tls certfile = /usr/local/samba/private/tls/intermediate.crt
tls cafile   = /usr/local/samba/private/tls/ca-chain.crt
```

Restart the Samba service:

```bash
systemctl restart samba-ad-dc
```

Test it:

```bash
openssl s_client -connect samba.domain.lan:636 -showcerts
```

---

## Service Certificate Automation

To issue certs for services like Traefik and Authentik, I wrote a bash script:

```
/usr/local/samba/private/tls/sign_service_cert.sh
```

### Script Highlights

```bash
#!/bin/bash
FQDN="$1"
CERT_DIR="/usr/local/samba/private/tls/$FQDN"
mkdir -p "$CERT_DIR"

openssl req -new -nodes -newkey rsa:2048 \
  -keyout "$CERT_DIR/$FQDN.key" \
  -out "$CERT_DIR/$FQDN.csr" \
  -subj "/CN=$FQDN" \
  -config <(cat <<EOF
[ req ]
default_bits       = 2048
prompt             = no
default_md         = sha256
req_extensions     = v3_req
distinguished_name = dn

[ dn ]
CN = $FQDN

[ v3_req ]
basicConstraints = CA:FALSE
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[ alt_names ]
DNS.1 = $FQDN
EOF
)

openssl x509 -req \
  -in "$CERT_DIR/$FQDN.csr" \
  -CA /usr/local/samba/private/tls/intermediate.crt \
  -CAkey /usr/local/samba/private/tls/intermediate.key \
  -CAcreateserial \
  -out "$CERT_DIR/$FQDN.crt" \
  -days 825 -sha256 \
  -extfile <(cat <<EOF
[ v3_req ]
basicConstraints = CA:FALSE
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[ alt_names ]
DNS.1 = $FQDN
EOF
)

cat "$CERT_DIR/$FQDN.crt" /usr/local/samba/private/tls/ca-chain.crt > "$CERT_DIR/$FQDN-fullchain.crt"
```

Usage:

```
./sign_service_cert.sh authentik.domain.lan
```

---

## Traefik + Authentik Certificate Integration

### Problem

The authentik outpost container failed to connect due to:

```
tls: failed to verify certificate: x509: certificate signed by unknown authority
```

### Solution: Dockerfile CA Injection

Create a Dockerfile to embed the Root CA into the outpost container:

```
FROM ghcr.io/goauthentik/proxy:latest

USER root
COPY ./certs/rootCA.crt /usr/local/share/ca-certificates/rootCA.crt
RUN apt update && apt install -y ca-certificates && update-ca-certificates
USER 1000
```

Build the container:

```bash
docker compose build --no-cache authentik-outpost
```

Verify it inside the running container:

```bash
docker exec -it traefik-authentik-outpost bash
openssl s_client -connect authentik.domain.lan:443 -CAfile /etc/ssl/certs/ca-certificates.crt
```

You should see:

```
Verify return code: 0 (ok)
```

---

## Active Directory GPO

To deploy trust across my Windows clients, I used Group Policy to distribute the **Root CA certificate only**, not the entire chain. This prevents clients from implicitly trusting intermediate certificates not issued by the Root.

To deploy:

- Open **Group Policy Management Console**
    
- Create or edit a GPO
    
- Navigate to: `Computer Configuration > Policies > Windows Settings > Security Settings > Public Key Policies > Trusted Root Certification Authorities`
    
- Import `rootCA.cert.pem`
    

After syncing (`gpupdate /force`), all domain-joined clients should trust the Root.

---

## Summary

This project resulted in a secure, enterprise-style certificate infrastructure for my home lab:

- Hardened Root CA hosted offline
    
- Samba promoted to Intermediate CA
    
- Signed certificates for LDAP, Traefik, and Authentik
    
- Trusted CA rolled out via AD GPO
    
- Docker containers extended to trust my internal CA
    

This foundation supports advanced secure services like LDAPS, OIDC, and internal HTTPS endpoints with verified trust.