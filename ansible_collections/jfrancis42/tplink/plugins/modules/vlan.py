#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: vlan
short_description: Manage VLANs on a TP-Link managed switch
description:
  - Create, update, or delete VLANs on a TP-Link managed switch.
  - Supports 802.1Q VLANs, port-based VLANs, and MTU VLAN mode.
  - The switch supports only one VLAN mode at a time (dot1q, port_based,
    or mtu).  Switching modes is destructive and requires
    C(allow_mode_change=true).
options:
  host:
    description: Switch management IP or hostname.
    required: true
    type: str
  username:
    description: Login username.
    type: str
    default: admin
  password:
    description: Login password.
    required: true
    type: str
  timeout:
    description: HTTP request timeout in seconds.
    type: float
    default: 10.0
  model:
    description: >
      Override model autodetection. Accepts a hardware model prefix
      (e.g. C(TL-SG108E), C(TL-SG1016DE)) or a class name (C(Switch),
      C(SwitchDE)). Only needed if autodetection fails.
    type: str
    required: false
  vlan_mode:
    description: VLAN mode to ensure is active on the switch.
    required: true
    type: str
    choices: [dot1q, port_based, mtu, none]
  vlan_id:
    description: >
      VLAN ID to operate on.  Required for C(dot1q) and C(port_based) modes
      when C(state) is C(present) or C(absent).
    type: int
  name:
    description: VLAN name (802.1Q only).
    type: str
  tagged_ports:
    description: Tagged member ports (802.1Q only).
    type: list
    elements: int
  untagged_ports:
    description: Untagged member ports (802.1Q only).
    type: list
    elements: int
  pvid:
    description: >
      PVID to assign to C(untagged_ports) (802.1Q only).  If omitted,
      PVIDs are left unchanged.
    type: int
  member_ports:
    description: Member ports (port-based VLAN only).
    type: list
    elements: int
  uplink_port:
    description: >
      Uplink port for MTU VLAN mode.  All other ports can reach the
      uplink but not each other.
    type: int
  state:
    description: >
      C(present) ensures the VLAN or mode exists with the given parameters.
      C(absent) removes the VLAN (or disables the VLAN mode when no
      C(vlan_id) is specified).
    type: str
    choices: [present, absent]
    default: present
  allow_mode_change:
    description: >
      Allow switching the VLAN mode.  Mode changes are destructive — they
      erase all existing VLAN configuration.  Must be set to C(true) to
      permit a mode switch; the task will fail otherwise.
    type: bool
    default: false
notes:
  - Runs on the Ansible controller; use C(connection: local).
  - MTU VLAN is independent of dot1q/port_based mode.  Setting
    C(vlan_mode=mtu) does not affect dot1q or port_based VLAN configuration.
  - When creating a new 802.1Q VLAN, any port not in C(tagged_ports) or
    C(untagged_ports) becomes a non-member.
  - When updating an existing 802.1Q VLAN, only the parameters that are
    explicitly provided are changed; unspecified memberships are preserved.
'''

EXAMPLES = r'''
# Enable 802.1Q mode and create VLAN 10 with port 8 as trunk, port 1 as access
- name: Create VLAN 10
  jfrancis42.tplink.vlan:
    host: 192.168.0.1
    password: admin
    vlan_mode: dot1q
    vlan_id: 10
    name: servers
    tagged_ports: [8]
    untagged_ports: [1]
    pvid: 10
    state: present
  connection: local

# Delete VLAN 10
- name: Remove VLAN 10
  jfrancis42.tplink.vlan:
    host: 192.168.0.1
    password: admin
    vlan_mode: dot1q
    vlan_id: 10
    state: absent
  connection: local

# Port-based VLAN
- name: Create port-based VLAN 2
  jfrancis42.tplink.vlan:
    host: 192.168.0.1
    password: admin
    vlan_mode: port_based
    vlan_id: 2
    member_ports: [1, 2, 3]
    state: present
  connection: local

# MTU VLAN — port 8 is the uplink, all other ports are isolated
- name: Enable MTU VLAN
  jfrancis42.tplink.vlan:
    host: 192.168.0.1
    password: admin
    vlan_mode: mtu
    uplink_port: 8
    state: present
  connection: local

# Disable MTU VLAN
- name: Disable MTU VLAN
  jfrancis42.tplink.vlan:
    host: 192.168.0.1
    password: admin
    vlan_mode: mtu
    state: absent
  connection: local
'''

RETURN = r'''
vlan:
  description: Current VLAN configuration after any changes.
  returned: always
  type: dict
changed:
  description: Whether any VLAN settings were changed.
  returned: always
  type: bool
'''

from ansible.module_utils.basic import AnsibleModule

try:
    from ansible_collections.jfrancis42.tplink.plugins.module_utils.common import (
        CONNECTION_ARGS, make_switch, HAS_SDK, SDK_ERROR,
        serialize_dot1q_vlan_entry, serialize_port_vlan_entry,
        serialize_mtu_vlan, _bits_to_ports, _ports_to_bits,
    )
except ImportError:
    pass


def _get_current_mode(sw):
    """Return ('dot1q'|'port_based'|'none', d1q_enabled, pv_enabled)."""
    pv_enabled, _ = sw.get_port_vlan()
    d1q_enabled, _ = sw.get_dot1q_vlans()
    if d1q_enabled:
        return 'dot1q', True, False
    if pv_enabled:
        return 'port_based', False, True
    return 'none', False, False


def _switch_mode(sw, from_mode, to_mode, module):
    """Switch VLAN mode, raising fail_json if allow_mode_change is False."""
    if from_mode == to_mode:
        return
    if not module.params['allow_mode_change']:
        module.fail_json(
            msg=(
                'Switching from %s to %s VLAN mode would destroy all existing '
                'VLAN configuration.  Set allow_mode_change=true to permit this.'
            ) % (from_mode, to_mode)
        )
    if module.check_mode:
        return
    # Disable current mode
    if from_mode == 'dot1q':
        sw.set_dot1q_enabled(False)
    elif from_mode == 'port_based':
        sw.set_port_vlan_enabled(False)
    # Enable desired mode
    if to_mode == 'dot1q':
        sw.set_dot1q_enabled(True)
    elif to_mode == 'port_based':
        sw.set_port_vlan_enabled(True)
    # 'none' means disable everything — already done above


def run_module():
    argument_spec = dict(
        **CONNECTION_ARGS,
        vlan_mode=dict(type='str', required=True, choices=['dot1q', 'port_based', 'mtu', 'none']),
        vlan_id=dict(type='int'),
        name=dict(type='str'),
        tagged_ports=dict(type='list', elements='int'),
        untagged_ports=dict(type='list', elements='int'),
        pvid=dict(type='int'),
        member_ports=dict(type='list', elements='int'),
        uplink_port=dict(type='int'),
        state=dict(type='str', default='present', choices=['present', 'absent']),
        allow_mode_change=dict(type='bool', default=False),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    if not HAS_SDK:
        module.fail_json(msg='tplink_switch SDK not available: %s' % SDK_ERROR)

    p = module.params
    vlan_mode = p['vlan_mode']
    state = p['state']
    changed = False

    try:
        with make_switch(p) as sw:

            # ----------------------------------------------------------------
            # MTU VLAN — independent of dot1q/port_based
            # ----------------------------------------------------------------
            if vlan_mode == 'mtu':
                mv = sw.get_mtu_vlan()
                if state == 'present':
                    uplink = p['uplink_port'] or mv.uplink_port
                    if not mv.enabled or mv.uplink_port != uplink:
                        changed = True
                        if not module.check_mode:
                            sw.set_mtu_vlan(enabled=True, uplink_port=uplink)
                else:  # absent
                    if mv.enabled:
                        changed = True
                        if not module.check_mode:
                            sw.set_mtu_vlan(enabled=False)

                if changed and not module.check_mode:
                    sw.save_config()
                    mv = sw.get_mtu_vlan()

                module.exit_json(changed=changed, vlan=serialize_mtu_vlan(mv))
                return

            # ----------------------------------------------------------------
            # none — disable whichever mode is active
            # ----------------------------------------------------------------
            if vlan_mode == 'none':
                current_mode, d1q_on, pv_on = _get_current_mode(sw)
                if current_mode != 'none':
                    if not module.params['allow_mode_change']:
                        module.fail_json(
                            msg=(
                                'Disabling VLAN mode (%s) would destroy all existing '
                                'VLAN configuration.  Set allow_mode_change=true to permit this.'
                            ) % current_mode
                        )
                    changed = True
                    if not module.check_mode:
                        if d1q_on:
                            sw.set_dot1q_enabled(False)
                        if pv_on:
                            sw.set_port_vlan_enabled(False)
                        sw.save_config()

                module.exit_json(changed=changed, vlan=dict(mode='none', vlans=[]))
                return

            # ----------------------------------------------------------------
            # dot1q and port_based
            # ----------------------------------------------------------------
            current_mode, d1q_on, pv_on = _get_current_mode(sw)

            # Ensure the right mode is active
            if current_mode != vlan_mode:
                changed = True
                _switch_mode(sw, current_mode, vlan_mode, module)

            # If no vlan_id is given, mode change was the whole job
            if p['vlan_id'] is None:
                if changed and not module.check_mode:
                    sw.save_config()
                vlan_info = _build_vlan_return(sw, vlan_mode, module.check_mode)
                module.exit_json(changed=changed, vlan=vlan_info)
                return

            vid = p['vlan_id']

            # ----------------------------------------------------------------
            # 802.1Q VLAN CRUD
            # ----------------------------------------------------------------
            if vlan_mode == 'dot1q':
                _, existing_vlans = sw.get_dot1q_vlans()
                existing = next((v for v in existing_vlans if v.vid == vid), None)

                if state == 'present':
                    if existing is None:
                        # New VLAN
                        changed = True
                        if not module.check_mode:
                            sw.add_dot1q_vlan(
                                vid=vid,
                                name=p['name'] or '',
                                tagged_ports=p['tagged_ports'] or [],
                                untagged_ports=p['untagged_ports'] or [],
                            )
                            _apply_pvids(sw, p)
                    else:
                        # Compare with existing
                        desired_tagged = (
                            _ports_to_bits(p['tagged_ports'])
                            if p['tagged_ports'] is not None
                            else existing.tagged_members
                        )
                        desired_untagged = (
                            _ports_to_bits(p['untagged_ports'])
                            if p['untagged_ports'] is not None
                            else existing.untagged_members
                        )
                        desired_name = p['name'] if p['name'] is not None else existing.name

                        vlan_needs_change = (
                            desired_tagged != existing.tagged_members or
                            desired_untagged != existing.untagged_members or
                            desired_name != existing.name
                        )

                        pvid_needs_change = _pvid_needs_change(sw, p)

                        if vlan_needs_change or pvid_needs_change:
                            changed = True
                            if not module.check_mode:
                                if vlan_needs_change:
                                    sw.add_dot1q_vlan(
                                        vid=vid,
                                        name=desired_name,
                                        tagged_ports=_bits_to_ports(desired_tagged),
                                        untagged_ports=_bits_to_ports(desired_untagged),
                                    )
                                if pvid_needs_change:
                                    _apply_pvids(sw, p)

                else:  # absent
                    if existing is not None:
                        changed = True
                        if not module.check_mode:
                            sw.delete_dot1q_vlan(vid)

            # ----------------------------------------------------------------
            # Port-based VLAN CRUD
            # ----------------------------------------------------------------
            elif vlan_mode == 'port_based':
                _, existing_vlans = sw.get_port_vlan()
                existing = next((v for v in existing_vlans if v.vid == vid), None)

                if state == 'present':
                    desired_members = _ports_to_bits(p['member_ports'] or [])
                    if existing is None or existing.members != desired_members:
                        changed = True
                        if not module.check_mode:
                            sw.add_port_vlan(vid, p['member_ports'] or [])
                else:  # absent
                    if existing is not None:
                        changed = True
                        if not module.check_mode:
                            sw.delete_port_vlan(vid)

            # Build return value
            if changed and not module.check_mode:
                sw.save_config()
            vlan_info = _build_vlan_return(sw, vlan_mode, module.check_mode)

    except Exception as e:
        module.fail_json(msg='Switch operation failed: %s' % str(e))

    module.exit_json(changed=changed, vlan=vlan_info)


def _pvid_needs_change(sw, p):
    """Return True if any untagged port's PVID differs from the desired pvid."""
    if p['pvid'] is None or not p['untagged_ports']:
        return False
    current_pvids = sw.get_pvids()
    for port_num in p['untagged_ports']:
        idx = port_num - 1
        if idx < len(current_pvids) and current_pvids[idx] != p['pvid']:
            return True
    return False


def _apply_pvids(sw, p):
    """Set PVID on untagged_ports if pvid is specified."""
    if p['pvid'] is not None and p['untagged_ports']:
        current_pvids = sw.get_pvids()
        ports_needing_pvid = [
            port_num for port_num in p['untagged_ports']
            if (port_num - 1) < len(current_pvids) and
               current_pvids[port_num - 1] != p['pvid']
        ]
        if ports_needing_pvid:
            sw.set_pvid(ports_needing_pvid, p['pvid'])


def _build_vlan_return(sw, vlan_mode, check_mode):
    """Build the vlan dict to return, accounting for check mode."""
    if check_mode:
        return dict(mode=vlan_mode, vlans=[])
    try:
        if vlan_mode == 'dot1q':
            enabled, entries = sw.get_dot1q_vlans()
            pvids = sw.get_pvids()
            return dict(
                mode='dot1q' if enabled else 'none',
                vlans=[serialize_dot1q_vlan_entry(v) for v in entries],
                pvids=pvids,
            )
        elif vlan_mode == 'port_based':
            enabled, entries = sw.get_port_vlan()
            return dict(
                mode='port_based' if enabled else 'none',
                vlans=[serialize_port_vlan_entry(v) for v in entries],
            )
    except Exception:
        pass
    return dict(mode=vlan_mode, vlans=[])


def main():
    run_module()


if __name__ == '__main__':
    main()
