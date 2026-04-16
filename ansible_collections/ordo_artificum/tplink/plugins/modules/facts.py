#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: facts
short_description: Gather facts from a TP-Link managed switch
description:
  - Reads all available state from a TP-Link managed switch and registers
    it as Ansible facts under the C(tplink) key.
  - If an individual subsystem read fails, its key will contain
    C({'error': '<message>'}) rather than failing the whole task.
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
    no_log: true
  timeout:
    description: HTTP request timeout in seconds.
    type: float
    default: 10.0
notes:
  - Runs on the Ansible controller; use C(connection: local).
'''

EXAMPLES = r'''
- name: Gather switch facts
  ordo_artificum.tplink.facts:
    host: "{{ ansible_host }}"
    password: "{{ tplink_password }}"
  connection: local

- name: Show firmware version
  ansible.builtin.debug:
    msg: "{{ tplink.system.firmware }}"

- name: Show all port states
  ansible.builtin.debug:
    msg: "Port {{ item.port }}: {{ 'up' if item.enabled else 'down' }}"
  loop: "{{ tplink.ports }}"
'''

RETURN = r'''
ansible_facts:
  description: Facts registered under the C(tplink) key.
  returned: always
  type: dict
  contains:
    tplink:
      description: All switch state.
      type: dict
      contains:
        system:
          description: System info (firmware, MAC, IP, etc).
          type: dict
        ip_settings:
          description: IP configuration.
          type: dict
        led:
          description: LED on/off state.
          type: bool
        ports:
          description: Per-port settings.
          type: list
        port_statistics:
          description: Per-port TX/RX packet counters.
          type: list
        mirror:
          description: Port mirroring configuration.
          type: dict
        trunk:
          description: LAG group configuration.
          type: dict
        igmp_snooping:
          description: IGMP snooping configuration.
          type: dict
        loop_prevention:
          description: Loop prevention enabled state.
          type: bool
        mtu_vlan:
          description: MTU VLAN configuration.
          type: dict
        vlan:
          description: VLAN configuration including active mode and VLAN list.
          type: dict
        qos:
          description: QoS mode and per-port priorities.
          type: dict
        bandwidth:
          description: Per-port bandwidth limits.
          type: list
        storm_control:
          description: Per-port storm control configuration.
          type: list
'''

from ansible.module_utils.basic import AnsibleModule

try:
    from ansible_collections.ordo_artificum.tplink.plugins.module_utils.common import (
        CONNECTION_ARGS, make_switch, HAS_SDK, SDK_ERROR,
        serialize_system_info, serialize_ip_settings, serialize_port_info,
        serialize_port_stats, serialize_mirror, serialize_trunk,
        serialize_igmp, serialize_mtu_vlan, serialize_port_vlan_entry,
        serialize_dot1q_vlan_entry, serialize_qos_port, serialize_bandwidth,
        serialize_storm,
    )
except ImportError:
    pass


def _safe(fn, *args, **kwargs):
    """Call fn(*args); on exception return {'_error': message}."""
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        return {'_error': str(e)}


def _err(result):
    return isinstance(result, dict) and '_error' in result


def run_module():
    module = AnsibleModule(
        argument_spec=dict(**CONNECTION_ARGS),
        supports_check_mode=True,
    )

    if not HAS_SDK:
        module.fail_json(msg='tplink_switch SDK not available: %s' % SDK_ERROR)

    facts = {}

    try:
        with make_switch(module.params) as sw:

            # -- System --
            r = _safe(sw.get_system_info)
            facts['system'] = {'_error': r['_error']} if _err(r) else serialize_system_info(r)

            r = _safe(sw.get_ip_settings)
            facts['ip_settings'] = {'_error': r['_error']} if _err(r) else serialize_ip_settings(r)

            r = _safe(sw.get_led)
            facts['led'] = r  # bool or error dict

            # -- Ports --
            r = _safe(sw.get_port_settings)
            facts['ports'] = (
                {'_error': r['_error']} if _err(r)
                else [serialize_port_info(p) for p in r]
            )

            r = _safe(sw.get_port_statistics)
            facts['port_statistics'] = (
                {'_error': r['_error']} if _err(r)
                else [serialize_port_stats(s) for s in r]
            )

            # -- Topology --
            r = _safe(sw.get_port_mirror)
            facts['mirror'] = {'_error': r['_error']} if _err(r) else serialize_mirror(r)

            r = _safe(sw.get_port_trunk)
            facts['trunk'] = {'_error': r['_error']} if _err(r) else serialize_trunk(r)

            # -- Layer 2 features --
            r = _safe(sw.get_igmp_snooping)
            facts['igmp_snooping'] = {'_error': r['_error']} if _err(r) else serialize_igmp(r)

            r = _safe(sw.get_loop_prevention)
            facts['loop_prevention'] = r  # bool or error dict

            # -- VLAN --
            r = _safe(sw.get_mtu_vlan)
            facts['mtu_vlan'] = {'_error': r['_error']} if _err(r) else serialize_mtu_vlan(r)

            pv = _safe(sw.get_port_vlan)
            d1q = _safe(sw.get_dot1q_vlans)

            vlan_facts = {}
            pv_enabled = (not _err(pv)) and pv[0]
            d1q_enabled = (not _err(d1q)) and d1q[0]

            if pv_enabled:
                vlan_facts['mode'] = 'port_based'
                vlan_facts['vlans'] = [serialize_port_vlan_entry(v) for v in pv[1]]
            elif d1q_enabled:
                vlan_facts['mode'] = 'dot1q'
                vlan_facts['vlans'] = [serialize_dot1q_vlan_entry(v) for v in d1q[1]]
                r = _safe(sw.get_pvids)
                vlan_facts['pvids'] = r if isinstance(r, list) else []
            else:
                vlan_facts['mode'] = 'none'
                vlan_facts['vlans'] = []

            if _err(pv) or _err(d1q):
                vlan_facts['_error'] = (
                    pv.get('_error') or d1q.get('_error')
                )

            facts['vlan'] = vlan_facts

            # -- QoS --
            r = _safe(sw.get_qos_settings)
            if _err(r):
                facts['qos'] = {'_error': r['_error']}
            else:
                qos_mode, qos_ports = r
                facts['qos'] = dict(
                    mode=qos_mode.name,
                    ports=[serialize_qos_port(p) for p in qos_ports],
                )

            r = _safe(sw.get_bandwidth_control)
            facts['bandwidth'] = (
                {'_error': r['_error']} if _err(r)
                else [serialize_bandwidth(b) for b in r]
            )

            r = _safe(sw.get_storm_control)
            facts['storm_control'] = (
                {'_error': r['_error']} if _err(r)
                else [serialize_storm(s) for s in r]
            )

    except Exception as e:
        module.fail_json(msg='Failed to connect to switch: %s' % str(e))

    module.exit_json(changed=False, ansible_facts={'tplink': facts})


def main():
    run_module()


if __name__ == '__main__':
    main()
