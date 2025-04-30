---
title: "Provisioning Samba Active Directory Domain Controller and Windows Domain Integration"
date: 2025-04-26
tags: ["Samba", "Active Directory", "Domain Controller", "Windows Domain", "Home Lab", "Networking", "LDAP Server"]
categories: ["My Home Lab Journey"]
draft: false
---

## 1. Server Preparation

- **OS:** Ubuntu Server 24.04.2 LTS
    
- **Initial Setup:**
    
    - Static IP address manually configured
        
        - IP: `172.30.30.30/24`
            
        - Gateway: `172.30.30.1`
            
        - DNS (initially): `172.21.21.21` (Pi-hole)
            
    - Installed basic utilities (OpenSSH, networking tools)
        

## 2. Samba Installation and Configuration

- **Installation Commands:**
    
    ```bash
    sudo apt update
    sudo apt full-upgrade
    sudo apt install samba krb5-config krb5-user winbind smbclient
    ```
    
- **Service Management:**
    
    - Disabled default Samba services to prepare for AD DC mode:
        
        ```bash
        sudo systemctl disable smbd nmbd winbind
        sudo systemctl stop smbd nmbd winbind
        ```
        
- **Provision Domain Controller:**
    
    ```bash
    sudo samba-tool domain provision --use-rfc2307 --interactive
    ```
    
    - **Realm:** TILLYNET.LAN
        
    - **Domain:** TILLYNET
        
    - **Server Role:** Domain Controller (DC)
        
    - **DNS Backend:** SAMBA_INTERNAL
        
    - **DNS Forwarder:** Initially pointed to Pi-hole (172.21.21.21)
        
- **Post-Provision:**
    
    - Samba auto-generated clean `/etc/samba/smb.conf`.
        

## 3. Troubleshooting During Provisioning

- **Provisioning Error: Existing smb.conf:**
    
    - Deleted pre-existing `/etc/samba/smb.conf` before reprovisioning.
        
- **DNS Conflict with systemd-resolved:**
    
    - Overwrote `/etc/resolv.conf` to manually point to `127.0.0.1`.
        
- **Kerberos KDC Lookup Failure:**
    
    - Encountered "Cannot find KDC" errors until DNS pointed correctly.
        
- **DNS Port 53 Not Listening Initially:**
    
    - Restarted `samba-ad-dc` to bind correctly.
        
- **Benign DNS Update Errors (Exit Code 29):**
    
    - Ignored initial race conditions during service startup.
        
- **SRV Record Lookup Failure:**
    
    - SRV records appeared correctly after service stabilization.
        
- **No** `**dns forwarder**` **Command:**
    
    - Confirmed that DNS forwarder must be set during domain provision.
        

## 4. Kerberos Configuration

- **Kerberos File Setup:** `/etc/krb5.conf` overwritten with minimal:
    
    ```bash
    [libdefaults]
        default_realm = TILLYNET.LAN
        dns_lookup_realm = false
        dns_lookup_kdc = true
    ```
    

## 5. DNS Forwarding and Testing

- **DNS Forwarding:**
    
    - Set during provisioning; no samba-tool command available post-provision.
        
- **DNS Functionality Testing:**
    
    ```bash
    dig @127.0.0.1 google.com
    host -t SRV _kerberos._udp.tillynet.lan
    samba-tool dns query 127.0.0.1 tillynet.lan @ ALL
    ```
    
- Confirmed correct A records and SRV records.
    

## 6. Windows Client Domain Join

- **Windows Version:** Windows 11 Pro
    
- **Actions:**
    
    - Configured PC to use Samba server as DNS.
        
    - Joined to domain `TILLYNET.LAN` via System Properties.
        
    - Created new domain administrative account `tillyadmin`.
        

## 7. Profile Migration

- **Tool Used:** ForensIT User Profile Wizard (Community Edition)
    
- **Action:** Migrated old local user profile to domain user (`tillyadmin`).
    
- **Outcome:**
    
    - Files migrated
        
    - Some environmental conflicts detected (e.g., SSH agent issues, mismatched user folders)
        

## 8. Git and SSH Environment

- **Setup Challenges:**
    
    - SSH agent issues (`error connecting to agent: No such file or directory`).
        
    - Incorrect user profile folder (`C:\Users\micha` used instead of `C:\Users\tillyadmin`).
        
- **Diagnosis:**
    
    - Domain login identity correct (`tillynet\tillyadmin`).
        
    - Filesystem path inherited from old local user.
        
- **Plan for Correction:**
    
    - Fully remove the broken tillyadmin profile.
        
    - Reprovision fresh tillyadmin domain account.
        
    - Create clean `C:\Users\tillyadmin` profile.
        
    - Reconfigure SSH keys and Git environment under clean domain context.
        


---

## Related Posts

[Provisioning Authentik for SSO on a Self-Hosted Ubuntu Server (Docker-Based)](https://blog.tillynet.com/my-home-lab-journey/provisioning-authentik-for-sso-on-a-self-hosted-ubuntu-server-docker-based/)  
[Provisioning Authentik for SSO on a Self-Hosted Ubuntu Server (Docker-Based)](https://blog.tillynet.com/my-home-lab-journey/provisioning-authentik-for-sso-on-a-self-hosted-ubuntu-server-docker-based/)

