---
title: "Resolving Internet Connectivity Issues for Proxmox VMs on a Routed Subnet"
date: 2025-04-24
tags: ["Proxmox", "Debian", "Wi-Fi", "Linux Bridge", "Home Lab", "Networking", "pfSense", "Static Route", "NAT", "Troubleshooting"]
categories: ["My Home Lab Journey"]
draft: false
---

## Background

This post documents the troubleshooting process I followed to resolve an internet connectivity issue affecting virtual machines (VMs) hosted on a Proxmox VE node running on a Wi-Fi-only Dell XPS 15. The VMs were deployed on a routed internal subnet (`172.30.30.0/24`) with static routes configured through a pfSense firewall. While the VMs could communicate with internal hosts—including DNS and gateway IPs—they were unable to reach external internet addresses such as `8.8.8.8`.

The setup avoided NAT by design to maintain full route visibility, relying instead on static routing and properly scoped firewall rules.

## Environment Overview

- **Proxmox Host:** Dell XPS 15 running Proxmox VE 8.4.1 on top of Debian 12
    
- **Proxmox VM Subnet:** `172.30.30.0/24`
    
- **Host Wi-Fi IP:** Routed via `172.21.21.15` on VLAN 21
    
- **Gateway (pfSense):** `172.21.21.1` with a static route pointing to `172.30.30.0/24`
    
- **Firewall Role:** pfSense acts as central gateway and inter-VLAN router
    

## Issue Summary

Despite a correct static IP configuration on the Arch Linux VM, and successful ping tests to internal IPs (e.g., DNS on `172.21.21.21` and pfSense gateway at `172.21.21.1`), the VM could not reach external addresses.

## Troubleshooting Steps

### 1. **Validated VM IP Configuration**

Set a static IP on the VM from the live Arch Linux installer:

```
ip addr add 172.30.30.10/24 dev enp0s18
ip link set enp0s18 up
ip route add default via 172.30.30.1
echo "nameserver <172.21.21.21>" > /etc/resolv.conf
```

Ping to internal IPs succeeded, confirming basic layer 3 connectivity.

### 2. **Captured Outbound Packets**

Ran `tcpdump` on the Proxmox host Wi-Fi interface:

```
sudo tcpdump -i wlp0s20f3 host 8.8.8.8
```

Confirmed that ICMP packets were leaving the host to the internet.

### 3. **Monitored pfSense Interfaces**

Used pfSense’s built-in packet capture utility to validate:

- Outbound ICMP requests were reaching the WAN interface
    
- No ICMP replies were returning
    
- ARP traffic on the WAN was unrelated to the issue
    

### 4. **Created an Outbound NAT Rule**

Realized that pfSense was not NAT'ing the routed subnet. Added a rule under: `Firewall > NAT > Outbound`:

- **Source:** `172.30.30.0/24`
    
- **Interface:** WAN
    
- **Translation:** Interface Address
    
- **Mode:** Hybrid Outbound NAT
    

### 5. **Re-tested with Packet Capture**

Still no success—packets left, but replies were dropped.

### 6. **Reviewed Firewall Rules**

Found a restrictive rule on the VLAN 21 interface that only allowed `172.30.30.0/24` to access _hosts within VLAN 21_. This prevented pfSense from responding to traffic that was destined for external addresses.

### 7. **Corrected Firewall Rule**

Modified the rule to allow outbound traffic from `172.30.30.0/24` to **any** destination. Immediately after saving:

- VM was able to ping `8.8.8.8`
    
- `curl ifconfig.me` returned the public IP, confirming full internet access
    

## Outcome

The VM now has stable internet access with proper routing and NAT handling, while retaining the benefits of internal subnet isolation and firewall control. The root issue stemmed from a well-intended but overly strict firewall rule that blocked replies from beyond the VLAN scope.

## Next Steps

- Refactor firewall rules for tighter security once validation is complete
    
- Consider isolating NAT-enabled vs. routed-only subnets
    
- Explore using `systemd-networkd` for persistent network configs in Arch VMs