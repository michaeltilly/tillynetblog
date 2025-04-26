---
title: "Deploying a Proxmox Node on a Wi-Fi-Only Dell XPS Laptop"
date: 2025-04-23
tags: ["Proxmox", "Debian", "Wi-Fi", "Linux Bridge", "Home Lab", "Networking", "pfSense", "Static Route"]
categories: ["My Home Lab Journey"]
draft: false
---
## Overview

In this post, I document how I deployed Proxmox VE on a Dell XPS 15 laptop with no physical Ethernet interface. This machine was added to my home lab as a standalone hypervisor, running independently from my main Protectli-based Proxmox node.

Because the XPS lacks wired connectivity, I had to work through some unique networking constraints, including bridging over Wi-Fi and enabling connectivity for guest virtual machines. This write-up covers the initial NAT-based setup and the transition to a cleaner routed network model with static routes via pfSense.


## Environment Summary

- **Hardware**: Dell XPS 15 (no Ethernet NIC)
    
- **Host OS**: Debian 12 (Bookworm) base installation
    
- **Hypervisor**: Proxmox VE 8.4.1 installed manually
    
- **Wireless Interface**: `wlp0s20f3` (connected to VLAN 21 - Production)
    
- **Virtual Bridge**: `vmbr0` (for LXC and VM traffic on isolated subnet)
    

---

## Installing Proxmox VE 8.4.1 on top of Debian 12

### `/etc/network/interfaces`

```bash
iface wlp0s20f3
iface wlp0s20f3 inet static
	address 172.21.21.15/24
	gateway 172.21.21.1
	wpa-ssid xxxxxx
	wpa-psk xxxxxxx
```

### `/etc/hosts`

```bash
127.0.0.1 localhost.localdomain localhost
127.21.21.15 xps15.tillynet.lan xps15
```

### Reset Interface

```bash
ifdown wlp0s20f3
ifup wlp0s20f3
```

### Proxmox apt Repository

```bash

nano /etc/apt/sources.list.d/pve-install-repo.list

deb [arch=amd64] http://download.proxmox.com/debian/pve bookworm pve-no-subscription
```

This adds the Proxmox apt repository in the `sources.list.d` folder.

```bash
wget  http://download.proxmox.com/debian/proxmox-release-bookworm.gpg -O /etc/apt/trusted.gpg.d/proxmox-release-bookworm.gpg
```

This adds the Proxmox gpg key and places it into a specific folder so that `apt` will find it.

```bash
apt update
apt full-upgrade
```

Makes sure that everything is up to date before installing Proxmox. Once done, Proxmox can be installed from apt packages with the command below.

```bash
apt install proxmox-ve postfix open-iscsi
```

```bash
apt remove os-prober
```

## Initial Network Setup with NAT

Due to the Linux kernel’s limitation on bridging wireless interfaces directly, I created a bridge (`vmbr0`) with no attached physical ports. Initially, I used NAT (masquerading) to allow outbound internet access for containers and VMs.

### `/etc/network/interfaces`

```bash
auto vmbr0
iface vmbr0 inet static
    address 172.30.30.1/24
    bridge_ports none
    bridge_stp off
    bridge_fd 0
```

**Do not use** `bridge-ports`, `bridge-stp`, or `bridge-fd` — those will fail validation in Debian/Proxmox deployment.

### Enable IP Forwarding

```bash
nano /etc/sysctl.conf
net.ipv4.ip_forward= 1
```

### NAT Rule (iptables)

```bash
sudo iptables -t nat -A POSTROUTING -s 172.30.30.0/24 -o wlp0s20f3 -j MASQUERADE
```

### Make NAT Rule persistent (install iptables-persistent)

```bash
sudo apt install iptables-persistent
```

This approach allowed outbound traffic but made the Proxmox node act as a NAT gateway. The firewall (pfSense) would only see the host’s IP (`172.21.21.15`) and not the internal clients.

---

## Transition to Routed Networking with Static Route

To enable full visibility and allow routed traffic from other VLANs, I removed the NAT rule and configured pfSense with a static route to the Proxmox-hosted subnet.

### Remove NAT

```bash
sudo iptables -t nat -D POSTROUTING -s 172.30.30.0/24 -o wlp0s20f3 -j MASQUERADE
```

### Save Cleaned-up Rules

```bash
sudo iptables-save > /etc/iptables/rules.v4
```

### pfSense Static Route Configuration

- **Destination Network**: `172.30.30.0/24`
    
- **Gateway**: `172.21.21.15` (Proxmox host IP)
    
- **Interface**: Production VLAN (VLAN 21)
    
- **Firewall Rules**: Allowed inter-VLAN access from trusted zones
    

### LXC/VM Guest Network Settings

- **IP Address**: `172.30.30.x`
    
- **Subnet Mask**: `255.255.255.0`
    
- **Gateway**: `172.30.30.1`
    
- **DNS**: `172.21.21.21` (internal Pi-hole)
    

With this configuration, all traffic is routed properly between pfSense and the isolated Proxmox subnet, and there's no longer a need for NAT.

---

## Outcome

This setup enabled my Wi-Fi-only XPS laptop to function as a fully routed Proxmox hypervisor on a dedicated subnet. By avoiding NAT, I maintained visibility and control over LXC and VM traffic from my central firewall. The solution is scalable and works well within my VLAN-segmented home lab.

---

## Future Plans

- Add lightweight shared storage (e.g., NFS over VLAN 21)
    
- Automate Proxmox LXC deployment and backups via Ansible
    
- Possibly integrate into a Proxmox cluster using a third quorum-only node
    


