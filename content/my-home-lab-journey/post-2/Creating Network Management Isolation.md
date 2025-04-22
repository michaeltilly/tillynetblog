---
title: "Creating Network Management Isolation"
date: 2025-04-15
tags: ["tillynet", "homelab", "networkisolation"]
categories: ["My Home Lab Journey"]
draft: false
---

# 02 - Migrating to a Dedicated Management VLAN (VLAN 99)

This phase documents the migration of all core management infrastructure to an isolated VLAN (VLAN 99) for improved security, network segmentation, and long-term scalability. This included Proxmox GUI access, Omada Controller LXC, and strict firewall rules enforced via pfSense.

---

## Goals

- Remove critical services from default/native VLAN
- Assign a dedicated, isolated VLAN (VLAN 99) for:
  - Proxmox management GUI
  - Omada Controller (LXC)
- Trunk management VLAN through switch to Proxmox
- Implement firewall rules to allow remote admin access only
- Preserve service availability during transition

---

## Pre-Migration Topology

| Component         | Network | VLAN  | Interface | Description                        |
|------------------|---------|-------|-----------|------------------------------------|
| **Proxmox Host**  | LAN     | VLAN 1| vmbr0     | Static IP via native VLAN          |
| **Omada Controller** | LAN | VLAN 1| vmbr0     | LXC container, web GUI on port 8043|
| **Pi-hole**       | LAN     | VLAN 1| vmbr0     | DNS LXC                            |
| **VPN Tunnel**    | LAN     | VLAN 1| pfSense   | Remote client-to-site access       |

---

## Post-Migration Topology

| Component           | Network        | VLAN   | Interface     | Description                                  |
|--------------------|----------------|--------|---------------|----------------------------------------------|
| **Proxmox Host**    | Management     | VLAN 99| vmbr1.99      | Tagged IP for GUI access via `vmbr1`         |
| **Omada Controller**| Management     | VLAN 99| vmbr1 (tagged)| LXC container with VLAN tag 99               |
| **Pi-hole**         | LAN            | VLAN 1 | vmbr0         | LXC container                                |
| **Trunk Port (Switch)** | Trunked Port | 1,99,14| enp1s0         | Connected to VLAN-aware bridge `vmbr1`       |
| **VPN Tunnel**      | Routed to MGMT | VLAN 99| pfSense       | Allows external admin access to VLAN 99      |

---

## Migration Steps

### 1. Create VLAN 99 in pfSense

- **Interfaces > Assignments > VLANs**
- Created VLAN 99 on the LAN parent interface
- Assigned it as a new interface and renamed it to `MGMT`
- Enabled the interface and set a static IP (management subnet)

### 2. Configure Proxmox Bridge for VLAN Tagging

Created a new VLAN-aware bridge and subinterface in `/etc/network/interfaces`:

```bash
auto vmbr1
iface vmbr1 inet manual
    bridge-ports enp1s0
    bridge-stp off
    bridge-fd 0
    bridge-vlan-aware yes
    bridge-vids 2-4094

auto vmbr1.99
iface vmbr1.99 inet static
    address <management_ip>/24
    gateway <management_gateway>
