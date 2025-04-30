---
title: "Integrating Samba 4 Active Directory with Authentik via LDAPS"
date: 2025-04-29
tags: ["Samba", "Active Directory", "Authentik", "LDAP", "Home Lab", "LDAPS", "LDAP Server", "Network Security", "Authentication"]
categories: ["My Home Lab Journey"]
draft: false
---

This guide documents the process of securely binding a Samba 4 Active Directory (AD) server to Authentik using LDAPS. The integration allows Authentik to use the AD as an identity source, enabling centralized authentication across applications via SAML/OIDC while Samba 4 maintains the authoritative user directory.

---

## Overview

- **Samba 4 AD** acts as the LDAP and Kerberos provider.
    
- **Authentik** serves as the Identity Provider (IdP) using the LDAP source for authentication.
    
- **LDAPS** is used to securely transmit credentials between Authentik and Samba.
    

---

## Prerequisites

- A working Samba 4 Active Directory Domain Controller
    
- A running Authentik instance (Docker or native)
    
- DNS resolution and time synchronization between the two systems
    
- Samba server with LDAPS enabled and a trusted certificate
    

---

## Step 1: Enable LDAPS on Samba 4

1. Generate an internal CA and a server certificate for Samba:
    

```bash
# Generate internal CA
openssl genrsa -out ca.key 4096
openssl req -x509 -new -nodes -key ca.key -sha256 -days 3650 -out ca.crt

# Generate Samba key and CSR
openssl genrsa -out samba.key 4096
openssl req -new -key samba.key -out samba.csr

# Sign server certificate
openssl x509 -req -in samba.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out samba.crt -days 825 -sha256
```

2. Update `/etc/samba/smb.conf`:
    

```bash
tls enabled = yes
tls keyfile = /etc/samba/ssl/samba.key
tls certfile = /etc/samba/ssl/samba.crt
tls cafile = /etc/samba/ssl/ca.crt
```

3. Restart Samba:
    

```bash
systemctl restart samba-ad-dc
```

4. Test LDAPS:
    

```bash
openssl s_client -connect <samba_fqdn>:636 -CAfile ca.crt
```

---

## Step 2: Create a Bind User in Samba

Create a service account in AD for Authentik to bind:

```bash
samba-tool user create authentik-bind
```

Assign a strong password and note the DN (e.g., `CN=authentik-bind,CN=Users,DC=example,DC=lan`).

---

## Step 3: Upload CA to Authentik

1. Navigate to **Certificates** in the Authentik admin UI.
    
2. Create a new certificate and upload your `ca.crt`.
    
3. Name it appropriately (e.g., `Internal AD CA`).
    

---

## Step 4: Configure LDAP Source in Authentik

1. Go to **Directory > LDAP Sources > Create**.
    
2. Fill in the fields:
    

- **Server URI**: `ldaps://<samba_fqdn>`
    
- **TLS Verification Certificate**: Select your uploaded CA cert
    
- **Bind CN**: Full DN of the bind user
    
- **Bind Password**: The service account password
    
- **Base DN**: `DC=example,DC=lan`
    
- **User Object Filter**: `(objectClass=person)`
    
- **Group Object Filter**: `(objectClass=group)`
    
- **Group Membership Field**: `member`
    
- **Object Uniqueness Field**: `objectSid`
    

3. Select appropriate user/group property mappings (default Active Directory mappings are recommended).
    
4. Save and test the connection.
    

---

## Step 5: Add LDAP Source to Authentication Flow

1. Go to **Flows > default-authentication-flow > Edit**.
    
2. Add a new **Source (Login)** stage.
    
3. Select your Samba 4 LDAP source.
    
4. Save the flow.
    

---

## Step 6: Sync Users

1. Navigate to **Directory > LDAP Source**.
    
2. Click **Manual Sync** to import users.
    
3. Users should appear under **Users**, with their `DN`, `UPN`, and `objectSid` attributes visible.
    

---

## Notes

- Authentik does **not write back** to Samba AD. Any changes to user details in Authentik are local and will be overwritten on sync.
    
- Always secure LDAPS using a trusted internal CA or public CA to prevent man-in-the-middle attacks.
    
- Syncs can be scheduled or triggered manually depending on your directory update policies.
    

---

## Outcome

With this setup, Authentik now authenticates users against Samba 4 AD using secure LDAPS. Authentik remains the central SSO provider for web applications, while Samba manages users and groups.

---

## Related Posts

[Provisioning Authentik for SSO on a Self-Hosted Ubuntu Server (Docker-Based)](https://blog.tillynet.com/my-home-lab-journey/provisioning-authentik-for-sso-on-a-self-hosted-ubuntu-server-docker-based/)
[Provisioning Samba Active Directory Domain Controller and Windows Domain Integration](https://blog.tillynet.com/my-home-lab-journey/provisioning-samba-active-directory-domain-controller-and-windows-domain-integration/)
