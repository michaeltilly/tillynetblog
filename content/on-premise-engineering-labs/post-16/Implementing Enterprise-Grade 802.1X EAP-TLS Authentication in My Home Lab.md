---
title: "Implementing Enterprise-Grade 802.1X EAP-TLS Authentication in My Home Lab"
date: 2025-06-17
tags: ["dot1x", "Microsoft Active Directory", "Samba4 AD", "Samba", "Active Directory", "Internal CA", "Chain of Trust", "PKI", "LDAPS", "FreeRADIUS", "RADIUS", "Network Security", "GPO", "EAP-TLS", "Cisco", "AAA", "pfSense"]
categories: ["On-Premise Engineering Labs"]
draft: false
---
# Implementing Enterprise-Grade 802.1X EAP-TLS Authentication in My Home Lab

## Introduction

Network Access Control (NAC) has become a cornerstone of enterprise security, ensuring that only authorized devices can connect to corporate networks. While technologies like 802.1X are commonplace in enterprise environments, implementing them in a home lab presents unique challenges and learning opportunities. In this article, I'll walk through my complete implementation of 802.1X EAP-TLS authentication using FreeRADIUS, Samba4 Active Directory, and Cisco Catalyst switches.

This implementation goes beyond simple password-based authentication by leveraging X.509 certificates for device authentication, providing the same level of security found in enterprise environments while serving as an excellent learning platform for understanding enterprise network security architectures.

## Architecture Overview

My home lab environment consists of several key components that work together to provide enterprise-grade network access control:

**Network Infrastructure:**

- Management VLAN: `172.16.99.0/24`
- Domain: `tillynet.lan`
- Samba4 Active Directory Domain Controller: `172.30.30.30`
- pfSense Firewall with FreeRADIUS: `172.16.99.1`
- Cisco Catalyst 2960 Switch serving as the Network Access Server (NAS)
- Windows 10/11 domain-joined workstation: `TILLYPC`

**Security Infrastructure:**

- Two-tier PKI with offline Root CA
- Samba4-hosted Intermediate Certificate Authority
- EAP-TLS authentication protocol
- Certificate-based device authentication

The architecture follows enterprise best practices by separating the authentication server (FreeRADIUS), directory services (Samba4 AD), and network enforcement (Cisco switch) into distinct components that communicate via standardized protocols.

## Certificate Infrastructure Design

The foundation of any EAP-TLS implementation is a robust Public Key Infrastructure. I designed a two-tier PKI that mirrors enterprise deployments:

### Root Certificate Authority

The Root CA operates offline for maximum security, issuing only intermediate certificates. This design ensures that the root private key remains protected while allowing operational flexibility through the intermediate CA.

### Intermediate Certificate Authority

I integrated the Intermediate CA directly into my Samba4 Active Directory environment. This approach provides several advantages:

- Centralized certificate management
- Integration with AD security groups
- Simplified certificate lifecycle management
- Realistic enterprise-like setup

### Server Certificate Generation

For the FreeRADIUS server certificate, I developed a shell script that automates the certificate generation process while ensuring proper extensions and Subject Alternative Names (SANs):

```bash
#!/bin/bash
SERVICE_FQDN=$1
BASE_DIR="/usr/local/samba/private/tls"
KEY_SIZE=2048
DAYS_VALID=825

INTERMEDIATE_KEY="${BASE_DIR}/intermediate.key"
INTERMEDIATE_CRT="${BASE_DIR}/intermediate.crt"
CA_CHAIN="${BASE_DIR}/ca-chain.crt"

if [[ -z "$SERVICE_FQDN" ]]; then
  echo "Usage: $0 <service.fqdn>"
  exit 1
fi

OUTPUT_DIR="${BASE_DIR}/${SERVICE_FQDN}"
mkdir -p "${OUTPUT_DIR}"

# Generate private key and certificate signing request
openssl req -new -newkey rsa:${KEY_SIZE} -nodes \
  -keyout "${OUTPUT_DIR}/${SERVICE_FQDN}.key" \
  -out "${OUTPUT_DIR}/${SERVICE_FQDN}.csr" \
  -subj "/CN=${SERVICE_FQDN}" \
  -addext "subjectAltName = DNS:${SERVICE_FQDN}"

# Create certificate extensions
EXT_FILE="${OUTPUT_DIR}/v3_ext.cnf"
cat > "${EXT_FILE}" <<EOF
[ v3_req ]
basicConstraints = CA:FALSE
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[ alt_names ]
DNS.1 = ${SERVICE_FQDN}
EOF

# Sign certificate with intermediate CA
openssl x509 -req \
  -in "${OUTPUT_DIR}/${SERVICE_FQDN}.csr" \
  -CA "${INTERMEDIATE_CRT}" \
  -CAkey "${INTERMEDIATE_KEY}" \
  -CAcreateserial \
  -out "${OUTPUT_DIR}/${SERVICE_FQDN}.crt" \
  -days ${DAYS_VALID} -sha256 \
  -extfile "${EXT_FILE}" \
  -extensions v3_req

# Build complete certificate chain
cat "${OUTPUT_DIR}/${SERVICE_FQDN}.crt" "${CA_CHAIN}" > "${OUTPUT_DIR}/${SERVICE_FQDN}-fullchain.crt"

rm -f "${EXT_FILE}"
```

This script ensures that the server certificate includes the proper Extended Key Usage (EKU) for server authentication and maintains the complete certificate chain required for client validation.

### Client Certificate Generation

Client certificates require different extensions, specifically the Client Authentication EKU. I created a separate script for generating client certificates:

```bash
#!/bin/bash
FQDN="$1"
CERT_DIR="/usr/local/samba/private/tls/$FQDN"
mkdir -p "$CERT_DIR"

# Generate client certificate with appropriate extensions
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
extendedKeyUsage = clientAuth
subjectAltName = @alt_names

[ alt_names ]
DNS.1 = $FQDN
EOF
)

# Sign with intermediate CA
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
extendedKeyUsage = clientAuth
subjectAltName = @alt_names

[ alt_names ]
DNS.1 = $FQDN
EOF
)

cat "$CERT_DIR/$FQDN.crt" /usr/local/samba/private/tls/ca-chain.crt > "$CERT_DIR/$FQDN-fullchain.crt"
```

### PKCS#12 Export for Windows

Windows workstations require certificates in PKCS#12 format. I automated this conversion process:

```bash
#!/bin/bash
FQDN="$1"
PFX_PASSWORD="${2:-""}"
CERT_BASE_DIR="/usr/local/samba/private/tls"
CERT_DIR="$CERT_BASE_DIR/$FQDN"

KEY_FILE="$CERT_DIR/$FQDN.key"
CERT_FILE="$CERT_DIR/$FQDN.crt"
CHAIN_FILE="$CERT_BASE_DIR/ca-chain.crt"
PFX_OUTPUT="$CERT_DIR/$FQDN.pfx"

# Validate all required files exist
for file in "$KEY_FILE" "$CERT_FILE" "$CHAIN_FILE"; do
  if [[ ! -f "$file" ]]; then
    echo "Error: Required file not found: $file"
    exit 1
  fi
done

# Generate PKCS#12 bundle
openssl pkcs12 -export \
  -inkey "$KEY_FILE" \
  -in "$CERT_FILE" \
  -certfile "$CHAIN_FILE" \
  -out "$PFX_OUTPUT" \
  -passout pass:"$PFX_PASSWORD"
```

This approach ensures that Windows clients receive certificates with the complete certificate chain, enabling proper validation against the root CA.

## FreeRADIUS Configuration Deep Dive

Configuring FreeRADIUS for EAP-TLS with Active Directory integration required careful attention to several components. The pfSense FreeRADIUS package provides a web interface, but understanding the underlying configuration is crucial for troubleshooting.

### RADIUS Client Configuration

I configured the Cisco switch as a RADIUS client (NAS) with these parameters:

- **Client Name**: TL-ASW1-2960C
- **Client IP Address**: The management IP of the switch
- **Shared Secret**: A complex pre-shared key matching the switch's AAA configuration
- **NAS Type**: Cisco

The shared secret must be identical on both the switch and FreeRADIUS server. I used a 32-character randomly generated string to ensure security.

### LDAP Integration Challenges and Solutions

The most complex aspect of this implementation was configuring FreeRADIUS to authenticate Windows computer accounts against Active Directory. This presented several challenges that required deep understanding of both LDAP and Windows authentication mechanisms.

**Initial LDAP Configuration Attempts:**

My first attempt used user-focused LDAP settings:

- Base DN: `DC=tillynet,DC=lan`
- Filter: `(sAMAccountName=%{Stripped-User-Name:-%{User-Name}})`
- Base Filter: `(objectClass=person)`

This configuration failed because Windows computer authentication works differently from user authentication. Computer accounts authenticate using the format `host/computername.domain`, and they are stored in the `CN=Computers` container by default.

**Corrected LDAP Configuration:**

After extensive troubleshooting, I implemented these settings:

- **Base DN**: `CN=Computers,DC=tillynet,DC=lan`
- **Filter**: `(&(objectClass=computer)(|(sAMAccountName=%{mschap:User-Name}$)(servicePrincipalName=%{User-Name})))`
- **Base Filter**: `(objectClass=computer)`
- **LDAP Authentication**: Enabled
- **LDAP Authorization**: Enabled (critical for proper operation)

The filter deserves special explanation:

- `objectClass=computer` ensures we only match computer accounts
- `sAMAccountName=%{mschap:User-Name}$` handles the computer account name with the required dollar sign suffix
- `servicePrincipalName=%{User-Name}` handles the `host/computername.domain` format used during authentication

### EAP-TLS Configuration

The EAP configuration required specific settings for proper TLS tunnel operation:

**Critical EAP Settings:**

- **Default EAP Type**: TLS
- **TLS Configuration**:
    - Server Certificate: `radius.tillynet.lan`
    - Private Key: Corresponding private key
    - Certificate Chain: Complete CA chain
- **PEAP Configuration**:
    - Default EAP Type: MSCHAPV2 (for inner tunnel, though not used in pure EAP-TLS)
    - Copy Request to Tunnel: **Yes**
    - Use Tunneled Reply: **Yes**

The "Copy Request to Tunnel" and "Use Tunneled Reply" settings are crucial for passing authentication attributes between the outer and inner authentication contexts.

### Interface Binding

I configured FreeRADIUS to bind specifically to the management interface (`172.16.99.1`) rather than all interfaces. This approach provides better security and clearer troubleshooting by ensuring RADIUS traffic flows through the intended interface.

## Group Policy Configuration for 802.1X

Deploying 802.1X authentication to Windows workstations requires careful Group Policy configuration. I created a comprehensive GPO that handles both certificate deployment and network authentication settings.

### Certificate Deployment Strategy

While I could have used automatic certificate enrollment, I chose manual certificate deployment for this lab to better understand the process. In production environments, I would recommend:

1. Certificate Templates configured for auto-enrollment
2. Group Policy-based certificate deployment
3. Certificate lifecycle management through AD Certificate Services

### Wired Network Policy Configuration

I created a new GPO with the following configuration path: **Computer Configuration → Policies → Windows Settings → Security Settings → Wired Network (IEEE 802.3) Policies**

**Policy Settings:**

- **Policy Name**: "Enterprise 802.1X EAP-TLS Authentication"
- **Use Windows Wired Auto Config**: Enabled
- **Network Authentication Method**: Smart Card or other Certificate (EAP-TLS)
- **Authentication Mode**: Computer authentication
- **Validate server certificate**: Enabled
- **Connect to these servers**: `radius.tillynet.lan`
- **Trusted Root Certification Authorities**: My root CA
- **Use simple certificate selection**: Enabled

### GPO Deployment and Verification

I linked the GPO to the Workstations OU where my test computer resides. To verify proper application, I used:

```cmd
gpresult /r /scope computer
gpupdate /force
```

The `gpresult` command confirmed that the wired network policy was being applied correctly to the computer.

## Cisco Catalyst 2960 Configuration

The network switch serves as the 802.1X authenticator, enforcing authentication before allowing network access. My configuration implements industry-standard practices for enterprise environments.

### Global AAA Configuration

```cisco
# Enable new AAA model
aaa new-model

# Configure RADIUS server
radius-server host 172.16.99.1 auth-port 1812 acct-port 1813 key YourSharedSecret
radius-server timeout 10
radius-server retransmit 3

# Configure 802.1X authentication
aaa authentication dot1x default group radius
```

The timeout and retransmit values balance responsiveness with reliability. A 10-second timeout allows for network latency while preventing excessive delays during authentication failures.

### 802.1X Global Configuration

```cisco
# Enable 802.1X system-wide
dot1x system-auth-control
```

This command enables 802.1X globally on the switch. Individual ports must still be configured for 802.1X authentication.

### Port-Level Configuration

I configured a test port (FastEthernet0/2) for 802.1X authentication:

```cisco
interface FastEthernet0/2
 switchport mode access
 authentication port-control auto
 dot1x pae authenticator
 spanning-tree portfast
```

**Configuration Explanation:**

- `switchport mode access`: Configures the port as an access port
- `authentication port-control auto`: Enables 802.1X authentication (port blocked until successful authentication)
- `dot1x pae authenticator`: Sets the port as an 802.1X authenticator
- `spanning-tree portfast`: Reduces convergence time for end-device connections

## Comprehensive Troubleshooting Journey

The implementation process involved extensive troubleshooting that provided valuable insights into 802.1X authentication mechanisms. I'll detail the major issues encountered and their resolutions.

### Issue 1: RADIUS Port Configuration Mismatch

**Symptoms:** Initial authentication attempts showed no communication between the switch and FreeRADIUS server.

**Investigation Process:** I enabled debugging on the Cisco switch:

```cisco
terminal monitor
debug radius
debug dot1x all
```

The debug output revealed:

```
*Feb 10 23:25:41.810: RADIUS(00000000): Send Access-Request to 172.16.99.1:1645
```

**Root Cause:** The switch was using legacy RADIUS ports (1645/1646) instead of the standard ports (1812/1813).

**Resolution:** I updated the switch configuration to explicitly specify the correct ports:

```cisco
radius-server host 172.16.99.1 auth-port 1812 acct-port 1813 key YourSharedSecret
```

**Verification:** After the configuration change, the debug output showed:

```
*Feb 10 23:39:15.446: RADIUS: Received from id 1645/36 172.16.99.1:1812, Access-Reject, len 44
```

This confirmed that RADIUS communication was working, though authentication was still failing.

### Issue 2: FreeRADIUS LDAP Filter Configuration

**Symptoms:** RADIUS packets were reaching the server, but authentication consistently failed with "Access-Reject" responses.

**Investigation Process:** I examined the FreeRADIUS logs at `/var/log/radius.log` and found:

```
[ldap] ERROR: Unable to create filter
[ldap] ERROR: Failed to create LDAP filter
```

**Root Cause Analysis:** The LDAP filter was configured for user authentication rather than computer authentication. Windows computer accounts have distinct characteristics:

1. They authenticate using the `host/computername.domain` format
2. Computer accounts are stored in `CN=Computers` by default
3. Computer account sAMAccountName includes a trailing dollar sign

**Resolution:** I reconfigured the LDAP settings:

- **Base DN**: Changed from `DC=tillynet,DC=lan` to `CN=Computers,DC=tillynet,DC=lan`
- **Filter**: Updated to `(&(objectClass=computer)(|(sAMAccountName=%{mschap:User-Name}$)(servicePrincipalName=%{User-Name})))`
- **Base Filter**: Changed from `(objectClass=person)` to `(objectClass=computer)`

**Additional Configuration:** I also enabled LDAP Authorization, which is required for FreeRADIUS to properly process LDAP responses and make authorization decisions.

### Issue 3: EAP-TLS Tunnel Configuration

**Symptoms:** Even after resolving the LDAP issues, authentication was intermittently failing with TLS-related errors.

**Investigation Process:** Using `radiusd -X` in debug mode, I observed that the EAP-TLS handshake was completing, but the inner authentication was failing.

**Root Cause:** The EAP tunnel configuration was not properly copying authentication attributes between the outer and inner authentication contexts.

**Resolution:** I updated the EAP-PEAP configuration:

- **Copy Request to Tunnel**: Changed from "No" to "Yes"
- **Use Tunneled Reply**: Changed from "No" to "Yes"

These settings ensure that authentication attributes are properly passed through the TLS tunnel, allowing the inner authentication mechanism to access the necessary user/computer information.

### Issue 4: Certificate Validation Problems

**Symptoms:** Some authentication attempts failed with certificate validation errors on the client side.

**Investigation Process:** I used Windows Event Viewer to examine the System log and found certificate chain validation errors.

**Root Cause:** The Windows client was not properly validating the FreeRADIUS server certificate because:

1. The certificate chain was incomplete
2. The server certificate's Common Name didn't match the configured server name

**Resolution:**

1. **Complete Certificate Chain**: I ensured that the FreeRADIUS server was configured with the complete certificate chain (server cert + intermediate CA + root CA)
2. **Certificate Subject Verification**: I verified that the server certificate's CN matched the FQDN configured in the client's 802.1X profile
3. **Root CA Installation**: I confirmed that the root CA certificate was properly installed in the Windows client's Trusted Root Certification Authorities store

### Issue 5: Network Timeout and Performance Optimization

**Symptoms:** Authentication was working but taking an excessive amount of time, sometimes causing timeouts.

**Investigation Process:** I analyzed the authentication flow timing and identified several bottlenecks:

1. LDAP query timeouts
2. Certificate validation delays
3. Network latency between components

**Resolution:** I optimized several timeout values:

- **RADIUS Server Timeout**: Adjusted to 10 seconds on the switch
- **LDAP Connection Pooling**: Enabled persistent LDAP connections
- **Certificate Caching**: Configured client-side certificate caching

## Advanced Troubleshooting Techniques

Throughout this implementation, I developed several troubleshooting methodologies that proved invaluable:

### Packet Capture Analysis

I used tcpdump on the pfSense firewall to capture and analyze RADIUS traffic:

```bash
tcpdump -i em0 -s0 -w radius_capture.pcap udp port 1812
```

This approach allowed me to verify that RADIUS packets were reaching the server and to analyze the timing of authentication flows.

### LDAP Testing

To validate LDAP connectivity and search filters, I used ldapsearch directly from the FreeRADIUS host:

```bash
ldapsearch -x -H ldaps://172.30.30.30:636 \
  -D "CN=ldapbind,CN=Users,DC=tillynet,DC=lan" \
  -W -b "CN=Computers,DC=tillynet,DC=lan" \
  "(&(objectClass=computer)(sAMAccountName=TILLYPC$))"
```

This command helped verify that the LDAP filter was correctly matching computer accounts.

### Certificate Validation Testing

I used OpenSSL to test certificate chain validation:

```bash
openssl verify -CAfile ca-chain.crt radius.tillynet.lan.crt
```

This command confirmed that the certificate chain was properly constructed and that all certificates were valid.

### Windows Event Log Analysis

On the Windows client, I monitored several event logs:

- **System Log**: For 802.1X authentication events
- **Security Log**: For authentication and authorization events
- **Applications and Services Logs → Microsoft → Windows → Wired-AutoConfig**: For detailed 802.1X debugging

## Performance Optimization and Best Practices

Based on my implementation experience, I identified several optimization opportunities:

### Connection Pooling

I configured FreeRADIUS to maintain persistent connections to the LDAP server, reducing authentication latency and improving reliability.

### Certificate Caching

I enabled certificate caching on both the server and client sides to reduce certificate validation overhead during subsequent authentications.

### Monitoring and Alerting

I implemented monitoring for:

- RADIUS authentication success/failure rates
- LDAP server connectivity
- Certificate expiration dates
- Switch port authentication status

### Security Hardening

I applied several security hardening measures:

- Restricted RADIUS communication to specific VLANs
- Implemented certificate revocation checking
- Configured detailed audit logging
- Applied the principle of least privilege to service accounts

## Lessons Learned and Best Practices

This implementation provided several key insights that would be valuable for enterprise deployments:

### Certificate Management

1. **Automate Certificate Lifecycle**: In production environments, implement automated certificate enrollment and renewal
2. **Certificate Templates**: Use properly configured certificate templates that include the necessary EKUs and SANs
3. **Certificate Monitoring**: Implement proactive monitoring for certificate expiration

### LDAP Integration

1. **Service Account Security**: Use dedicated service accounts with minimal required permissions for LDAP binds
2. **Connection Security**: Always use LDAPS (LDAP over TLS) for authentication traffic
3. **Search Optimization**: Design LDAP searches to be as specific as possible to reduce directory server load

### Network Design

1. **VLAN Segmentation**: Implement proper VLAN segmentation to isolate authentication traffic
2. **Redundancy**: Deploy multiple RADIUS servers for high availability
3. **Monitoring**: Implement comprehensive monitoring of the authentication infrastructure

### Troubleshooting Methodology

1. **Layered Approach**: Troubleshoot authentication issues by examining each layer (network, RADIUS, LDAP, certificates)
2. **Comprehensive Logging**: Enable detailed logging at all layers during initial deployment
3. **Test Automation**: Develop automated tests to validate authentication functionality

## Future Enhancements

This implementation serves as a foundation for several potential enhancements:

### Dynamic VLAN Assignment

I plan to implement dynamic VLAN assignment based on computer group membership, allowing for automatic network segmentation based on device classification.

### Certificate Lifecycle Management

I'm working on implementing automated certificate enrollment and renewal using AD Certificate Services templates and Group Policy.

### Monitoring and Analytics

I'm developing a comprehensive monitoring solution that will track authentication patterns, identify potential security issues, and provide detailed reporting on network access.

### Integration with Network Access Control

I'm exploring integration with additional NAC solutions to provide more granular access control based on device health, compliance status, and user context.

## Conclusion

Implementing 802.1X EAP-TLS authentication in my home lab provided invaluable hands-on experience with enterprise network security technologies. The process involved overcoming numerous technical challenges, from certificate infrastructure design to complex LDAP integration issues.

The key takeaways from this implementation include:

1. **Certificate Infrastructure is Critical**: A well-designed PKI is essential for EAP-TLS success. Proper certificate templates, chain validation, and lifecycle management are crucial.
    
2. **LDAP Integration Complexity**: Integrating FreeRADIUS with Active Directory for computer authentication requires deep understanding of Windows authentication mechanisms and LDAP schema.
    
3. **Troubleshooting Methodology**: Systematic troubleshooting using debug logs, packet captures, and component testing is essential for identifying and resolving authentication issues.
    
4. **Security and Performance Balance**: Implementing strong security while maintaining good performance requires careful optimization of timeouts, connection pooling, and caching mechanisms.
    

This implementation now serves as a robust foundation for exploring advanced network access control concepts and provides a realistic environment for testing enterprise security scenarios. The experience gained from building this system from the ground up has significantly enhanced my understanding of enterprise network security architecture and the complex interactions between its various components.
