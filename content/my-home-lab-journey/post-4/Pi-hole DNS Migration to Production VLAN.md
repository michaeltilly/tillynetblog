---
title: "Pi-hole DNS Migration to Production VLAN"
date: 2025-04-20
tags: ["tillynet", "homelab", "pihole", "vlan", "dns", "network_isolation"]
categories: ["My Home Lab Journey"]
draft: false
---

# Pi-hole DNS Migration to Production VLAN

## Overview

This phase of the HomeLab project documents the successful migration of the internal Pi-hole DNS server from the flat LAN network to a newly created and isolated **Production VLAN**. This change enhances security, improves segmentation, and prepares the environment for scalable DNS resolution across all other VLANs.

---

## Objectives

- Create and configure a dedicated Production VLAN on pfSense  
- Migrate the Pi-hole LXC container to the new VLAN  
- Ensure inter-VLAN DNS resolution using Pi-hole  
- Apply proper firewall rules to restrict unnecessary access  
- Update DHCP DNS settings across all VLANs  

---

## Network Summary

| Component         | Before Migration        | After Migration               |
|------------------|--------------------------|-------------------------------|
| Pi-hole Location | LAN network (untagged)   | Production VLAN (tagged)     |
| VLAN ID          | -                        | Production VLAN ID           |
| Subnet           | LAN Subnet               | Production Subnet            |
| Pi-hole IP       | LAN Assigned IP          | VLAN-assigned static IP      |
| Access           | Open to LAN              | Inter-VLAN DNS only (port 53)|

---

## Steps Performed

### 1. Created Production VLAN in pfSense

- Navigated to **Interfaces > Assignments > VLANs**
- Assigned a unique VLAN tag and set the parent interface (LAN)
- Created new interface, enabled it, and assigned a static IPv4 gateway

### 2. Updated Pi-hole LXC Container Configuration

- Edited the container via Proxmox:
  
```bash
pct set <CTID> -net0 name=eth0,bridge=vmbr0,tag=<VLAN_ID>,ip=<Pi-hole_IP>/24,gw=<VLAN_Gateway>
