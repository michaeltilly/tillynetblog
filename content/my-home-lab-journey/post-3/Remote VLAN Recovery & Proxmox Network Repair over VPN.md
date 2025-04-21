---
title: "Remote VLAN Recovery & Proxmox Network Repair over VPN"
date: 2025-04-18
tags: ["tillynet", "homelab", "remote-recovery", "vpn", "networking"]
categories: ["My Home Lab Journey"]
draft: false
---

# 🛠️ Remote VLAN Recovery & Proxmox Network Repair over VPN

## 📡 Project Title: Remote SDN Recovery & VLAN Isolation via VPN & Shell Access

### Overview

In this project, I successfully re-established full access to my network management stack (Omada Controller, Proxmox GUI, and LXC containers) after losing access due to misconfigured VLAN trunking. The recovery was performed entirely **off-site**, using only a mobile device connected via an **OpenVPN tunnel**.

---

### 🔍 Background

I transitioned my home lab management network to VLAN 99 to achieve full traffic isolation. In the process of re-tagging Proxmox and LXC container traffic and reconfiguring Cisco switch trunk ports, I lost access to the Omada Controller and Proxmox GUI. With no local access to the console, I needed a remote solution.

---

### 🎯 Objective

- Regain access to VLAN 99 (management)
- Restore Omada Controller GUI and Proxmox Web GUI
- Ensure all traffic on management interfaces is VLAN 99 tagged

---

### 🧰 Tools Used

- Proxmox VE 8.3
- pfSense (OpenVPN Server & Firewall)
- TP-Link Omada Controller (LXC)
- SSH (mobile terminal access)
- OpenVPN (Client-to-Site)
- VLAN-aware Linux bridges (`vmbr1`)
- Cisco Catalyst switch (trunk config)

---

### 🔧 Steps Performed

1. **Connected to VPN Tunnel 1 (LAN access)**  
   - Used an existing OpenVPN client-to-site tunnel connected to the LAN network  
   - Leveraged this connection as a starting point

2. **Established VPN Tunnel 2 (MGMT access)**  
   - Configured a new OpenVPN tunnel to reach VLAN 99  
   - Verified routing and DNS from VPN client to MGMT subnet

3. **Accessed Proxmox Shell Remotely**  
   - Used SSH to access the Proxmox server shell

4. **Reviewed & Edited `/etc/network/interfaces`**  
   - Created a Linux Bridge `vmbr1` on `enp1s0`  
   - Configured `vmbr1` as VLAN-aware with a VLAN 99 subinterface

5. **Reconfigured Omada Controller LXC**  
   - Set static IP from VLAN 99  
   - Edited `/etc/pve/lxc/<vmid>.conf` to tag interface correctly

6. **Updated pfSense Firewall Rules**  
   - Allowed VPN access to Proxmox, Omada Controller, and LXCs  
   - Verified GUI access over VPN

7. **Safely Restarted Proxmox Networking Stack**  
   - Reloaded network stack without reboot to preserve SSH session

8. **Verified LXC & Controller Connectivity**  
   - Confirmed restored access to Omada Controller & Proxmox GUI  
   - Checked VLAN 99 trunking on Cisco switch

9. **Secured VLAN 99**  
   - Blocked all external access to VLAN 99  
   - Allowed only OpenVPN tunnel access

10. **Tested Full Remote Management Over VPN**

---

### ✅ Outcome

- Full recovery of Proxmox and Omada Controller  
- Management services isolated to VLAN 99  
- VLAN trunking corrected on switch  
- Secure remote access via OpenVPN tunnel  
- All executed **off-site using a mobile SSH client**

---

### 📸 Screenshots & CLI Snippets _(To be added)_

- Network configuration diagrams  
- VLAN trunking layout  
- `ip a`, `bridge vlan`, `openvpn` status

---

### 🧠 Lessons Learned

- Always test VLAN changes with fallback access
- Proxmox shell is essential for remote recovery
- OpenVPN enables secure remote SDN administration
- Avoid dual gateway configurations on bridges

---

### 🔮 Future Improvements

- Add fallback management IP on separate VLAN
- Setup out-of-band access (serial/IPMI)
- Automate Proxmox network config backups

---

### 🧾 Resume Bullet

> - Performed live remote SDN infrastructure recovery using OpenVPN and SSH from a mobile device; reconfigured VLAN-tagged Proxmox bridges, updated pfSense firewall rules, and restored access to critical network services including Omada Controller and LXC containers on an isolated management VLAN.
