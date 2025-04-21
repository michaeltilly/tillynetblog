---
title: "The Big Bang (How it All Began)"
date: 2025-04-10
tags: ["tillynet", "homelab", "setup"]
categories: ["My Home Lab Journey"]
draft: false
---

# 🏡 HomeLab: Initial Network Setup

This project documents the first working phase of my home network infrastructure built on top of Proxmox, using pfSense as a virtual firewall/router and LXC containers to host internal services. The design lays the foundation for a scalable, secure, and isolated home lab environment.

---

## 🌐 Overview

- **Hypervisor:** Proxmox VE running on Protectli Vault (Intel J6412, 4 NICs)
- **Router/Firewall:** pfSense VM
- **Internal Services:**
  - Pi-hole (LXC) – local DNS + ad-blocking
  - Omada Controller (LXC) – TP-Link AP management
- **LAN Devices:** Proxmox host, personal workstation, AP, switch
- **Guest Devices:** IoT & roommate devices on isolated VLAN 14

---

## 🏗️ Infrastructure at a Glance

| Component        | Description                                         |
|------------------|-----------------------------------------------------|
| **pfSense**      | VM with two PCI-passthrough NICs (WAN + LAN)       |
| **vmbr0**        | Bridge for LAN (Proxmox + LXCs)                     |
| **vmbr1**        | Reserved for future VLAN tagging (e.g., mgmt)      |
| **Pi-hole**      | LXC container for DNS (on LAN)                      |
| **Omada Ctrl**   | LXC container managing TP-Link EAP670 AP           |
| **Cisco Switch** | Access switch trunking VLANs to Proxmox/AP         |
| **Guest VLAN 14**| WiFi-only VLAN for roommate & IoT devices          |

---

## 🚀 Setup Timeline

### ✅ Phase 1 – Core Infrastructure

- Flashed Proxmox onto Protectli Vault
- Created pfSense VM with 2 passthrough NICs:
  - WAN: connected to ISP modem
  - LAN: connected to Cisco switch (trunk-ready)
- Configured `vmbr0` as LAN bridge in Proxmox
- Gave Proxmox host static IP on the LAN network

### ✅ Phase 2 – Internal Services

- Provisioned LXC container for Pi-hole
  - Static IP assigned
  - Configured upstream DNS servers (e.g., Cloudflare)
- Provisioned LXC container for Omada Controller
  - Used to manage TP-Link EAP670 AP
  - Served on LAN via Omada web GUI (port 8043)

### ✅ Phase 3 – Wireless & Guest VLAN

- Set up VLAN 14 in pfSense (Guest Network)
- Trunked VLANs through switch port to Omada AP
- Created isolated wireless SSID mapped to VLAN 14
- Configured firewall rules in pfSense:
  - Guests can access WAN only
  - Blocked access to LAN and Pi-hole
- Verified DHCP lease and internet access for guests
- Observed isolated traffic from personal network

---

## 🔐 Security Practices

- Created distinct VLANs for guest vs personal network
- Isolated Pi-hole to LAN access only
- Disabled inter-VLAN routing from Guest → LAN
- Assigned firewall rules by interface in pfSense
- Reserved management services for trusted VLAN only

---

## 🔍 To-Do / Next Steps

- Create VLAN 99 for network management
- Move Proxmox GUI and Omada Controller to VLAN 99
- Add remote access via OpenVPN (completed later)
- Diagram full topology and backup strategy

---

## 📸 Network Diagram

![Image](/images/TillyNet_OG.drawio.png)

> Will include:  
> Proxmox bridges → pfSense VM → Switch trunk → AP → VLAN segmentation

---

## 🧠 Lessons Learned

- Always reserve a static fallback IP for management
- pfSense is extremely powerful when paired with LXC containers
- VLANs and firewall rules are critical to proper isolation
- Omada Controller offers enterprise-like wireless management

---

## 🧾 Resume Bullet (from this phase)

> - Deployed full virtual home network lab with pfSense firewall, VLAN isolation, and internal services (DNS, WiFi controller) using Proxmox and LXC containers; implemented guest network segregation and trunked VLANs across Cisco infrastructure.
