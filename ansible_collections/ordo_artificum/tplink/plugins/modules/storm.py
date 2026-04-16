#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: storm
short_description: Manage storm control on a TP-Link managed switch
description:
  - Enable or disable storm control on one or more ports of a TP-Link
    managed switch, with configurable rate and traffic type filtering.
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
  port:
    description: Port number(s) to configure (1-based).
    required: true
    type: list
    elements: int
  enabled:
    description: Enable storm control on the port(s).
    type: bool
    default: true
  rate_index:
    description: >
      Rate limit index (1–12).  Required when C(enabled=true).
      Corresponding kbps values: 1=64, 2=128, 3=256, 4=512, 5=1024,
      6=2048, 7=4096, 8=8192, 9=16384, 10=32768, 11=65536, 12=131072.
    type: int
  storm_types:
    description: >
      Traffic types to limit.  Defaults to all three types when
      C(enabled=true).
    type: list
    elements: str
    choices: [UNKNOWN_UNICAST, MULTICAST, BROADCAST]
notes:
  - Runs on the Ansible controller; use C(connection: local).
  - Some firmware versions drop the TCP connection after applying storm
    control changes; the SDK handles reconnection transparently.
'''

EXAMPLES = r'''
- name: Limit broadcast and multicast on ports 1-4 to 1024 kbps
  ordo_artificum.tplink.storm:
    host: 192.168.0.1
    password: admin
    port: [1, 2, 3, 4]
    enabled: true
    rate_index: 5
    storm_types: [BROADCAST, MULTICAST]
  connection: local

- name: Disable storm control on port 1
  ordo_artificum.tplink.storm:
    host: 192.168.0.1
    password: admin
    port: [1]
    enabled: false
  connection: local
'''

RETURN = r'''
storm_control:
  description: Current storm control settings for the configured ports.
  returned: always
  type: list
changed:
  description: Whether any storm control settings were changed.
  returned: always
  type: bool
'''

from ansible.module_utils.basic import AnsibleModule

try:
    from ansible_collections.ordo_artificum.tplink.plugins.module_utils.common import (
        CONNECTION_ARGS, make_switch, HAS_SDK, SDK_ERROR,
        serialize_storm, StormType,
    )
    if HAS_SDK and StormType is not None:
        _TYPE_MAP = {t.name: t for t in StormType}
    else:
        _TYPE_MAP = {}
except ImportError:
    _TYPE_MAP = {}
    pass


def _types_to_mask(type_names):
    """Convert a list of storm type name strings to an integer bitmask."""
    mask = 0
    for name in (type_names or []):
        t = _TYPE_MAP.get(name)
        if t is not None:
            mask |= int(t)
    return mask


def run_module():
    argument_spec = dict(
        **CONNECTION_ARGS,
        port=dict(type='list', elements='int', required=True),
        enabled=dict(type='bool', default=True),
        rate_index=dict(type='int'),
        storm_types=dict(
            type='list', elements='str',
            choices=['UNKNOWN_UNICAST', 'MULTICAST', 'BROADCAST'],
        ),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_if=[['enabled', True, ['rate_index']]],
    )

    if not HAS_SDK:
        module.fail_json(msg='tplink_switch SDK not available: %s' % SDK_ERROR)

    p = module.params
    target_ports = p['port']
    desired_enabled = p['enabled']

    # Resolve desired storm types
    if desired_enabled:
        if p['storm_types']:
            desired_type_names = p['storm_types']
        else:
            desired_type_names = ['UNKNOWN_UNICAST', 'MULTICAST', 'BROADCAST']
        desired_mask = _types_to_mask(desired_type_names)
        desired_rate = p['rate_index']
    else:
        desired_mask = 0
        desired_rate = 0

    changed = False

    try:
        with make_switch(p) as sw:
            all_sc = sw.get_storm_control()
            sc_map = {s.port: s for s in all_sc}

            needs_change = False
            for port_num in target_ports:
                s = sc_map.get(port_num)
                if s is None:
                    continue
                if desired_enabled != s.enabled:
                    needs_change = True
                    break
                if desired_enabled and (
                    s.rate_index != desired_rate or
                    s.storm_types != desired_mask
                ):
                    needs_change = True
                    break

            if needs_change:
                changed = True
                if not module.check_mode:
                    if desired_enabled:
                        type_enums = [_TYPE_MAP[n] for n in desired_type_names if n in _TYPE_MAP]
                        sw.set_storm_control(
                            target_ports,
                            rate_index=desired_rate,
                            storm_types=type_enums,
                            enabled=True,
                        )
                    else:
                        sw.set_storm_control(target_ports, enabled=False)
                    all_sc = sw.get_storm_control()
                    sc_map = {s.port: s for s in all_sc}

            result = [serialize_storm(sc_map[n]) for n in target_ports if n in sc_map]

    except Exception as e:
        module.fail_json(msg='Switch operation failed: %s' % str(e))

    module.exit_json(changed=changed, storm_control=result)


def main():
    run_module()


if __name__ == '__main__':
    main()
