# ordo_artificum.tplink — Ansible Collection for TP-Link Managed Switches

Manage TP-Link managed switches entirely from Ansible — no CLI, no SSH,
no REST API required.  The collection reverse-engineers the switch's HTTP
web UI and exposes all configuration as idempotent Ansible modules.

> **Early release — lightly tested.**  This collection is new.  All
> modules have been exercised against a single TL-SG108E (hardware v6.0,
> firmware 1.0.0 Build 20230218 Rel.50633), but coverage on other models
> and firmware versions is unknown.  Please open an issue if something
> doesn't work on your hardware.

Developed and tested against the **TL-SG108E** (hardware v6.0, firmware
1.0.0 Build 20230218 Rel.50633).  Other TP-Link managed switches that
share the same frameset-based HTTP interface are likely compatible.

---

## Contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Quick start](#quick-start)
- [Inventory and connection setup](#inventory-and-connection-setup)
- [Modules](#modules)
  - [facts](#facts)
  - [system](#system)
  - [port](#port)
  - [trunk](#trunk)
  - [mirror](#mirror)
  - [igmp](#igmp)
  - [qos](#qos)
  - [bandwidth](#bandwidth)
  - [storm](#storm)
  - [vlan](#vlan)
  - [maintenance](#maintenance)
- [Common workflows](#common-workflows)
- [Return values and registered variables](#return-values-and-registered-variables)
- [Check mode](#check-mode)
- [License](#license)

---

## Requirements

- Ansible 2.9 or later
- Python `requests` library on the **controller** node

```bash
pip install requests
```

---

## Installation

```bash
ansible-galaxy collection install ordo_artificum.tplink
```

Or pin a specific version:

```bash
ansible-galaxy collection install ordo_artificum.tplink:==0.1.0
```

---

## Quick start

```yaml
- name: Configure TP-Link switch
  hosts: switches
  connection: local          # modules run on the controller, not the switch
  gather_facts: false
  tasks:

    - name: Gather switch facts
      ordo_artificum.tplink.facts:
        host: "{{ ansible_host }}"
        password: "{{ tplink_password }}"

    - name: Show firmware version
      ansible.builtin.debug:
        msg: "Firmware: {{ tplink.system.firmware }}"

    - name: Ensure loop prevention is on
      ordo_artificum.tplink.igmp:
        host: "{{ ansible_host }}"
        password: "{{ tplink_password }}"
        loop_prevention: true
```

---

## Inventory and connection setup

Every module connects directly to the switch over HTTP from the Ansible
controller.  Set `connection: local` either in the play header or per
task, **or** set it globally in `ansible.cfg`:

```ini
# ansible.cfg
[defaults]
collections_path = /path/to/your/collections

[ssh_connection]
# not used — switches connect over HTTP, not SSH
```

A typical inventory for switches:

```ini
# inventory/hosts.ini
[switches]
core-switch  ansible_host=10.1.0.31

[switches:vars]
ansible_connection=local
tplink_password=yourpassword
```

Or in YAML:

```yaml
# inventory/hosts.yml
all:
  children:
    switches:
      vars:
        ansible_connection: local
        tplink_password: yourpassword
      hosts:
        core-switch:
          ansible_host: 10.1.0.31
        access-switch:
          ansible_host: 10.1.0.32
```

Store the password in an Ansible Vault file:

```bash
ansible-vault create group_vars/switches/vault.yml
# Add: tplink_password: yourpassword
```

---

## Modules

All modules share these common connection parameters:

| Parameter  | Required | Default | Description |
|------------|----------|---------|-------------|
| `host`     | yes      |         | Switch IP or hostname |
| `username` | no       | `admin` | Login username |
| `password` | yes      |         | Login password |
| `timeout`  | no       | `10.0`  | HTTP request timeout (seconds) |

---

### facts

Gathers all available switch state and registers it as Ansible facts
under the `tplink` key.  Use this to inspect the current state of the
switch or to make other tasks conditional on switch state.

If an individual subsystem read fails (e.g., the switch doesn't support
a feature), its key contains `{'_error': 'message'}` rather than
failing the entire task.

```yaml
- name: Gather switch facts
  ordo_artificum.tplink.facts:
    host: "{{ ansible_host }}"
    password: "{{ tplink_password }}"
  connection: local

# Facts are now available as tplink.*
- name: Print firmware
  ansible.builtin.debug:
    msg: "{{ tplink.system.firmware }}"

- name: Print all port states
  ansible.builtin.debug:
    msg: "Port {{ item.port }}: {{ item.speed_cfg }}, link {{ item.speed_act | default('down') }}"
  loop: "{{ tplink.ports }}"

- name: Print active VLAN mode
  ansible.builtin.debug:
    msg: "VLAN mode: {{ tplink.vlan.mode }}"

- name: Print storm control on port 1
  ansible.builtin.debug:
    msg: "{{ tplink.storm_control | selectattr('port', 'eq', 1) | first }}"
```

**Fact keys returned under `tplink`:**

| Key | Description |
|-----|-------------|
| `system` | Firmware version, hardware, MAC address, description |
| `ip_settings` | IP address, netmask, gateway, DHCP state |
| `led` | Port LED on/off (`true`/`false`) |
| `ports` | List of per-port settings (enabled, speed_cfg, speed_act, fc_cfg, fc_act) |
| `port_statistics` | List of per-port TX/RX packet counters |
| `mirror` | Port mirroring configuration |
| `trunk` | LAG group configuration |
| `igmp_snooping` | IGMP snooping settings |
| `loop_prevention` | Loop prevention enabled state (`true`/`false`) |
| `mtu_vlan` | MTU VLAN configuration |
| `vlan` | Active VLAN mode (`dot1q`/`port_based`/`none`) and VLAN list |
| `qos` | QoS mode and per-port priority |
| `bandwidth` | Per-port ingress/egress bandwidth limits |
| `storm_control` | Per-port storm control settings |

---

### system

Configure system description, IP settings, LED state, and admin password.
Only parameters you specify are changed; everything else is left as-is.

```yaml
# Set hostname/description
- name: Set switch description
  ordo_artificum.tplink.system:
    host: "{{ ansible_host }}"
    password: "{{ tplink_password }}"
    description: core-switch-01
  connection: local

# Configure a static IP (will change management address — update inventory after)
- name: Set static IP
  ordo_artificum.tplink.system:
    host: "{{ ansible_host }}"
    password: "{{ tplink_password }}"
    ip: 10.1.0.31
    netmask: 255.255.255.0
    gateway: 10.1.0.1
    dhcp: false
  connection: local

# Enable DHCP
- name: Enable DHCP
  ordo_artificum.tplink.system:
    host: "{{ ansible_host }}"
    password: "{{ tplink_password }}"
    dhcp: true
  connection: local

# Turn off port LEDs
- name: Disable LEDs
  ordo_artificum.tplink.system:
    host: "{{ ansible_host }}"
    password: "{{ tplink_password }}"
    led: false
  connection: local

# Change the admin password
- name: Rotate admin password
  ordo_artificum.tplink.system:
    host: "{{ ansible_host }}"
    password: "{{ current_password }}"
    new_password: "{{ new_password }}"
  connection: local
  no_log: true
```

> **Note:** Changing the IP address or enabling DHCP takes the switch off
> the address you connected to.  Subsequent tasks in the same play must
> target the new address.

> **Note:** Password changes always report `changed=true` — there is no
> way to check the current password without attempting to change it.

---

### port

Enable or disable ports and configure speed/duplex and flow control.
All listed ports receive the same settings.  Only parameters you specify
are changed; unspecified parameters are preserved.

Port numbers are 1-based.

**Speed choices:** `AUTO`, `M10H` (10M half), `M10F` (10M full),
`M100H` (100M half), `M100F` (100M full), `M1000F` (1G full).

```yaml
# Ensure ports 1-4 are up at auto speed
- name: Enable access ports
  ordo_artificum.tplink.port:
    host: "{{ ansible_host }}"
    password: "{{ tplink_password }}"
    port: [1, 2, 3, 4]
    enabled: true
    speed: AUTO
  connection: local

# Disable unused ports
- name: Shut down unused ports
  ordo_artificum.tplink.port:
    host: "{{ ansible_host }}"
    password: "{{ tplink_password }}"
    port: [5, 6, 7]
    enabled: false
  connection: local

# Force uplink to 1G full-duplex with flow control
- name: Configure uplink port
  ordo_artificum.tplink.port:
    host: "{{ ansible_host }}"
    password: "{{ tplink_password }}"
    port: [8]
    speed: M1000F
    flow_control: true
  connection: local
```

---

### trunk

Create or remove LAG (Link Aggregation Group) groups.  The TL-SG108E
supports up to two LAG groups.

```yaml
# Bond ports 7 and 8 into LAG group 1
- name: Create uplink LAG
  ordo_artificum.tplink.trunk:
    host: "{{ ansible_host }}"
    password: "{{ tplink_password }}"
    group_id: 1
    ports: [7, 8]
    state: present
  connection: local

# Remove the LAG
- name: Remove LAG group 1
  ordo_artificum.tplink.trunk:
    host: "{{ ansible_host }}"
    password: "{{ tplink_password }}"
    group_id: 1
    state: absent
  connection: local
```

---

### mirror

Enable or disable port mirroring.  Traffic from any combination of
ingress (RX) and egress (TX) ports can be copied to a single destination
port for analysis.

```yaml
# Mirror all traffic on port 1 to port 8 (for a capture device on port 8)
- name: Enable port mirroring
  ordo_artificum.tplink.mirror:
    host: "{{ ansible_host }}"
    password: "{{ tplink_password }}"
    dest_port: 8
    ingress_ports: [1]
    egress_ports: [1]
    state: present
  connection: local

# Mirror ingress from multiple ports
- name: Mirror ingress from ports 1-4
  ordo_artificum.tplink.mirror:
    host: "{{ ansible_host }}"
    password: "{{ tplink_password }}"
    dest_port: 8
    ingress_ports: [1, 2, 3, 4]
    egress_ports: []
    state: present
  connection: local

# Disable mirroring
- name: Disable port mirroring
  ordo_artificum.tplink.mirror:
    host: "{{ ansible_host }}"
    password: "{{ tplink_password }}"
    state: absent
  connection: local
```

---

### igmp

Configure IGMP snooping and loop prevention.  Any parameter left unset
is preserved on the switch.  At least one parameter must be specified.

```yaml
# Enable IGMP snooping with report suppression
- name: Enable IGMP snooping
  ordo_artificum.tplink.igmp:
    host: "{{ ansible_host }}"
    password: "{{ tplink_password }}"
    igmp_enabled: true
    report_suppression: true
  connection: local

# Enable loop prevention
- name: Enable loop prevention
  ordo_artificum.tplink.igmp:
    host: "{{ ansible_host }}"
    password: "{{ tplink_password }}"
    loop_prevention: true
  connection: local

# Enable both at once
- name: Harden L2 settings
  ordo_artificum.tplink.igmp:
    host: "{{ ansible_host }}"
    password: "{{ tplink_password }}"
    igmp_enabled: true
    report_suppression: false
    loop_prevention: true
  connection: local
```

---

### qos

Set the global QoS scheduling mode and per-port priority.

**Mode choices:** `PORT_BASED`, `DOT1P` (802.1p), `DSCP`.

**Priority levels:** 1 (lowest) through 4 (highest).  Port priority only
applies in `PORT_BASED` mode.

```yaml
# Set port-based QoS and raise priority on the uplink
- name: Configure QoS
  ordo_artificum.tplink.qos:
    host: "{{ ansible_host }}"
    password: "{{ tplink_password }}"
    mode: PORT_BASED
    port: [8]
    priority: 4
  connection: local

# Switch to 802.1p (DSCP and 802.1p are common for VoIP/video)
- name: Use 802.1p QoS
  ordo_artificum.tplink.qos:
    host: "{{ ansible_host }}"
    password: "{{ tplink_password }}"
    mode: DOT1P
  connection: local

# Set multiple ports to the same priority (just mode, no ports)
- name: Use port-based QoS mode only
  ordo_artificum.tplink.qos:
    host: "{{ ansible_host }}"
    password: "{{ tplink_password }}"
    mode: PORT_BASED
  connection: local
```

---

### bandwidth

Set ingress and/or egress bandwidth limits on one or more ports.
A value of `0` removes the limit.

**Valid non-zero values (kbps):** 512, 1024, 2048, 4096, 8192, 16384,
32768, 65536, 131072, 262144, 524288, 1000000.

```yaml
# Limit a guest-network port to 10 Mbps in each direction
- name: Rate-limit guest port
  ordo_artificum.tplink.bandwidth:
    host: "{{ ansible_host }}"
    password: "{{ tplink_password }}"
    port: [3]
    ingress_kbps: 8192
    egress_kbps: 8192
  connection: local

# Limit upload to 1 Mbps on ports 1-4 (restrict clients, not the switch uplink)
- name: Restrict client upload
  ordo_artificum.tplink.bandwidth:
    host: "{{ ansible_host }}"
    password: "{{ tplink_password }}"
    port: [1, 2, 3, 4]
    ingress_kbps: 1024
    egress_kbps: 0
  connection: local

# Remove all bandwidth limits
- name: Remove bandwidth limits
  ordo_artificum.tplink.bandwidth:
    host: "{{ ansible_host }}"
    password: "{{ tplink_password }}"
    port: [1, 2, 3, 4, 5, 6, 7, 8]
    ingress_kbps: 0
    egress_kbps: 0
  connection: local
```

---

### storm

Enable or disable storm control (broadcast/multicast/unknown-unicast
rate limiting) on one or more ports.

**Rate index → kbps mapping:**

| Index | kbps |
|-------|------|
| 1 | 64 |
| 2 | 128 |
| 3 | 256 |
| 4 | 512 |
| 5 | 1024 |
| 6 | 2048 |
| 7 | 4096 |
| 8 | 8192 |
| 9 | 16384 |
| 10 | 32768 |
| 11 | 65536 |
| 12 | 131072 |

**Storm type choices:** `BROADCAST`, `MULTICAST`, `UNKNOWN_UNICAST`.
Defaults to all three when `enabled: true` and `storm_types` is omitted.

```yaml
# Enable storm control on all access ports, limit to 1024 kbps
- name: Enable storm control on access ports
  ordo_artificum.tplink.storm:
    host: "{{ ansible_host }}"
    password: "{{ tplink_password }}"
    port: [1, 2, 3, 4, 5, 6, 7]
    enabled: true
    rate_index: 5
  connection: local

# Limit only broadcast and multicast (not unknown unicast) on the uplink
- name: Partial storm control on uplink
  ordo_artificum.tplink.storm:
    host: "{{ ansible_host }}"
    password: "{{ tplink_password }}"
    port: [8]
    enabled: true
    rate_index: 9
    storm_types: [BROADCAST, MULTICAST]
  connection: local

# Disable storm control on port 1
- name: Disable storm control on port 1
  ordo_artificum.tplink.storm:
    host: "{{ ansible_host }}"
    password: "{{ tplink_password }}"
    port: [1]
    enabled: false
  connection: local
```

---

### vlan

Manage VLANs on the switch.  Supports 802.1Q VLANs, port-based VLANs,
and MTU VLAN mode.  **The switch supports only one VLAN mode at a time.**
Switching modes is destructive (erases all VLAN config) and requires
`allow_mode_change: true`.

#### 802.1Q VLANs

Tagged ports carry the VLAN tag in the Ethernet frame (trunk ports).
Untagged ports strip the tag on egress (access ports).  `pvid` sets
the port VLAN ID on untagged ports so incoming untagged frames are
assigned to the right VLAN.

```yaml
# Enable 802.1Q mode and create a management VLAN
- name: Create management VLAN 10
  ordo_artificum.tplink.vlan:
    host: "{{ ansible_host }}"
    password: "{{ tplink_password }}"
    vlan_mode: dot1q
    vlan_id: 10
    name: management
    tagged_ports: [8]        # trunk/uplink carries the tag
    untagged_ports: [1]      # access port strips the tag
    pvid: 10                 # assign PVID 10 to port 1
    state: present
  connection: local

# Create a second VLAN for guest traffic
- name: Create guest VLAN 20
  ordo_artificum.tplink.vlan:
    host: "{{ ansible_host }}"
    password: "{{ tplink_password }}"
    vlan_mode: dot1q
    vlan_id: 20
    name: guest
    tagged_ports: [8]
    untagged_ports: [2, 3]
    pvid: 20
    state: present
  connection: local

# Delete a VLAN
- name: Remove VLAN 20
  ordo_artificum.tplink.vlan:
    host: "{{ ansible_host }}"
    password: "{{ tplink_password }}"
    vlan_mode: dot1q
    vlan_id: 20
    state: absent
  connection: local

# Just ensure 802.1Q mode is on (no VLAN changes)
- name: Enable 802.1Q mode
  ordo_artificum.tplink.vlan:
    host: "{{ ansible_host }}"
    password: "{{ tplink_password }}"
    vlan_mode: dot1q
    allow_mode_change: true
  connection: local
```

#### Port-based VLANs

Simpler isolation: ports in the same group can communicate; ports in
different groups cannot (no tagging, no trunking).

```yaml
# Create two isolated port groups
- name: Create port-based VLAN 1 (ports 1-4)
  ordo_artificum.tplink.vlan:
    host: "{{ ansible_host }}"
    password: "{{ tplink_password }}"
    vlan_mode: port_based
    vlan_id: 1
    member_ports: [1, 2, 3, 4]
    state: present
  connection: local

- name: Create port-based VLAN 2 (ports 5-8)
  ordo_artificum.tplink.vlan:
    host: "{{ ansible_host }}"
    password: "{{ tplink_password }}"
    vlan_mode: port_based
    vlan_id: 2
    member_ports: [5, 6, 7, 8]
    state: present
  connection: local
```

#### MTU VLAN (port isolation with shared uplink)

All ports can reach the uplink port but are isolated from each other.
Useful for separating client devices that all share the same uplink.

```yaml
# Enable MTU VLAN — port 8 is the uplink
- name: Enable MTU VLAN
  ordo_artificum.tplink.vlan:
    host: "{{ ansible_host }}"
    password: "{{ tplink_password }}"
    vlan_mode: mtu
    uplink_port: 8
    state: present
  connection: local

# Disable MTU VLAN
- name: Disable MTU VLAN
  ordo_artificum.tplink.vlan:
    host: "{{ ansible_host }}"
    password: "{{ tplink_password }}"
    vlan_mode: mtu
    state: absent
  connection: local
```

> **Note on mode changes:** switching from `dot1q` to `port_based`
> (or vice versa) erases all VLAN configuration.  The module will fail
> unless `allow_mode_change: true` is set.  MTU VLAN is independent
> and does not interfere with dot1q/port_based config.

---

### maintenance

Perform one-off maintenance operations: reboot, factory reset, config
backup/restore, or cable diagnostics.

```yaml
# Reboot the switch
- name: Reboot switch
  ordo_artificum.tplink.maintenance:
    host: "{{ ansible_host }}"
    password: "{{ tplink_password }}"
    action: reboot
  connection: local

# Wait for it to come back
- name: Wait for switch to return
  ansible.builtin.wait_for:
    host: "{{ ansible_host }}"
    port: 80
    delay: 10
    timeout: 120

# Back up configuration to a local file
- name: Back up switch config
  ordo_artificum.tplink.maintenance:
    host: "{{ ansible_host }}"
    password: "{{ tplink_password }}"
    action: backup_config
    dest: "/backups/{{ inventory_hostname }}-{{ ansible_date_time.date }}.bin"
  connection: local

# Restore a previously saved configuration
- name: Restore switch config
  ordo_artificum.tplink.maintenance:
    host: "{{ ansible_host }}"
    password: "{{ tplink_password }}"
    action: restore_config
    src: /backups/core-switch-2024-01-15.bin
  connection: local

# Run cable diagnostics on all ports
- name: Run cable test
  ordo_artificum.tplink.maintenance:
    host: "{{ ansible_host }}"
    password: "{{ tplink_password }}"
    action: cable_diag
  connection: local
  register: diag

- name: Show cable test results
  ansible.builtin.debug:
    msg: "Port {{ item.port }}: {{ item.status }}{{ ' (' + item.length_m | string + ' m)' if item.length_m >= 0 else '' }}"
  loop: "{{ diag.cable_diag }}"

# Factory reset (DESTRUCTIVE — erases all config, resets IP to 192.168.0.1)
- name: Factory reset
  ordo_artificum.tplink.maintenance:
    host: "{{ ansible_host }}"
    password: "{{ tplink_password }}"
    action: factory_reset
    force: true        # required safety guard
  connection: local
```

**Cable diagnostic status values:** `NoCable`, `Normal`, `Open` (unterminated),
`Short`, `OpenShort`, `CrossCable`, `NotTested`.

> **Note:** `factory_reset` resets the management IP to `192.168.0.1`.
> Subsequent tasks must target that address.

---

## Common workflows

### Initial switch provisioning

```yaml
- name: Provision TP-Link switch from factory defaults
  hosts: new_switches
  connection: local
  gather_facts: false
  vars:
    # Factory default is 192.168.0.1 / admin / admin
    initial_host: 192.168.0.1
    initial_password: admin

  tasks:

    - name: Set permanent IP address
      ordo_artificum.tplink.system:
        host: "{{ initial_host }}"
        password: "{{ initial_password }}"
        ip: "{{ ansible_host }}"
        netmask: "{{ switch_netmask }}"
        gateway: "{{ switch_gateway }}"
        dhcp: false
        description: "{{ inventory_hostname }}"
      connection: local

    - name: Change default password
      ordo_artificum.tplink.system:
        host: "{{ initial_host }}"
        password: "{{ initial_password }}"
        new_password: "{{ tplink_password }}"
      connection: local
      no_log: true

    - name: Wait for switch at new IP
      ansible.builtin.wait_for:
        host: "{{ ansible_host }}"
        port: 80
        timeout: 30

    - name: Harden L2 settings
      ordo_artificum.tplink.igmp:
        host: "{{ ansible_host }}"
        password: "{{ tplink_password }}"
        igmp_enabled: true
        report_suppression: true
        loop_prevention: true
      connection: local
```

### VLAN segmentation (802.1Q)

This example creates three VLANs: management (10), servers (20), and
clients (30), with port 8 as a tagged uplink carrying all three.

```yaml
- name: Configure 802.1Q VLANs
  hosts: core-switch
  connection: local
  gather_facts: false

  tasks:

    - name: Management VLAN 10 — port 1 access, port 8 trunk
      ordo_artificum.tplink.vlan:
        host: "{{ ansible_host }}"
        password: "{{ tplink_password }}"
        vlan_mode: dot1q
        allow_mode_change: true
        vlan_id: 10
        name: management
        tagged_ports: [8]
        untagged_ports: [1]
        pvid: 10
        state: present

    - name: Server VLAN 20 — ports 2-3 access, port 8 trunk
      ordo_artificum.tplink.vlan:
        host: "{{ ansible_host }}"
        password: "{{ tplink_password }}"
        vlan_mode: dot1q
        vlan_id: 20
        name: servers
        tagged_ports: [8]
        untagged_ports: [2, 3]
        pvid: 20
        state: present

    - name: Client VLAN 30 — ports 4-7 access, port 8 trunk
      ordo_artificum.tplink.vlan:
        host: "{{ ansible_host }}"
        password: "{{ tplink_password }}"
        vlan_mode: dot1q
        vlan_id: 30
        name: clients
        tagged_ports: [8]
        untagged_ports: [4, 5, 6, 7]
        pvid: 30
        state: present
```

### Scheduled config backup

```yaml
- name: Back up all switch configurations
  hosts: switches
  connection: local
  gather_facts: false

  tasks:

    - name: Create backup directory
      ansible.builtin.file:
        path: "/backups/switches/{{ ansible_date_time.date }}"
        state: directory
      delegate_to: localhost
      run_once: true

    - name: Back up switch config
      ordo_artificum.tplink.maintenance:
        host: "{{ ansible_host }}"
        password: "{{ tplink_password }}"
        action: backup_config
        dest: "/backups/switches/{{ ansible_date_time.date }}/{{ inventory_hostname }}.bin"
```

### Network security hardening

```yaml
- name: Harden switch network security
  hosts: switches
  connection: local
  gather_facts: false

  tasks:

    - name: Enable loop prevention and IGMP snooping
      ordo_artificum.tplink.igmp:
        host: "{{ ansible_host }}"
        password: "{{ tplink_password }}"
        igmp_enabled: true
        report_suppression: true
        loop_prevention: true

    - name: Enable storm control on all access ports
      ordo_artificum.tplink.storm:
        host: "{{ ansible_host }}"
        password: "{{ tplink_password }}"
        port: [1, 2, 3, 4, 5, 6, 7]
        enabled: true
        rate_index: 5          # 1024 kbps
        storm_types: [BROADCAST, MULTICAST, UNKNOWN_UNICAST]

    - name: Disable unused ports
      ordo_artificum.tplink.port:
        host: "{{ ansible_host }}"
        password: "{{ tplink_password }}"
        port: "{{ unused_ports }}"
        enabled: false
      when: unused_ports is defined and unused_ports | length > 0
```

---

## Return values and registered variables

Every module returns `changed` (bool) and a module-specific key with
the current switch state after the task runs.  Register the result to
use it in subsequent tasks:

```yaml
- name: Gather facts
  ordo_artificum.tplink.facts:
    host: "{{ ansible_host }}"
    password: "{{ tplink_password }}"
  connection: local

- name: Fail if firmware is outdated
  ansible.builtin.fail:
    msg: "Firmware {{ tplink.system.firmware }} is older than expected"
  when: "'20230218' not in tplink.system.firmware"

- name: Run cable diagnostics
  ordo_artificum.tplink.maintenance:
    host: "{{ ansible_host }}"
    password: "{{ tplink_password }}"
    action: cable_diag
  connection: local
  register: cable_result

- name: Flag open/short cables
  ansible.builtin.debug:
    msg: "FAULT on port {{ item.port }}: {{ item.status }}"
  loop: "{{ cable_result.cable_diag }}"
  when: item.status in ['Open', 'Short', 'OpenShort']
```

---

## Check mode

All modules support `--check` mode.  No changes are written to the
switch; the return value shows what would have changed.

```bash
ansible-playbook site.yml --check --diff
```

Two exceptions to the "no writes" rule in check mode:
- `backup_config` always writes the local file (it reads from the switch
  and is non-destructive)
- `cable_diag` always runs the diagnostic (it is read-only)

---

## License

GNU General Public License v3.0.
See [LICENSE](https://www.gnu.org/licenses/gpl-3.0.html) for full text.
