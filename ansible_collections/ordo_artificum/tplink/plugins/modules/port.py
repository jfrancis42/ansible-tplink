#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: port
short_description: Configure port settings on a TP-Link managed switch
description:
  - Enable/disable ports and set speed and flow-control on one or more
    ports of a TP-Link managed switch.
  - Only parameters that are explicitly set are changed; unspecified
    parameters are left as-is on the switch.
  - All listed ports receive the same settings in a single request.
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
    description: Enable or disable the port(s).
    type: bool
  speed:
    description: Configured speed/duplex.
    type: str
    choices: [AUTO, M10H, M10F, M100H, M100F, M1000F]
  flow_control:
    description: Enable flow control on the port(s).
    type: bool
notes:
  - Runs on the Ansible controller; use C(connection: local).
  - If ports have different current settings they will all be set to the
    same desired value; this module does not support per-port differing
    targets within a single task.
'''

EXAMPLES = r'''
- name: Enable port 1 at auto speed, no flow control
  ordo_artificum.tplink.port:
    host: 192.168.0.1
    password: admin
    port: [1]
    enabled: true
    speed: AUTO
    flow_control: false
  connection: local

- name: Disable ports 5 through 8
  ordo_artificum.tplink.port:
    host: 192.168.0.1
    password: admin
    port: [5, 6, 7, 8]
    enabled: false
  connection: local

- name: Force port 2 to 100M full-duplex
  ordo_artificum.tplink.port:
    host: 192.168.0.1
    password: admin
    port: [2]
    speed: M100F
  connection: local
'''

RETURN = r'''
ports:
  description: Current settings for the configured ports after any changes.
  returned: always
  type: list
changed:
  description: Whether any port settings were changed.
  returned: always
  type: bool
'''

from ansible.module_utils.basic import AnsibleModule

try:
    from ansible_collections.ordo_artificum.tplink.plugins.module_utils.common import (
        CONNECTION_ARGS, make_switch, HAS_SDK, SDK_ERROR,
        serialize_port_info, PortSpeed,
    )
    if HAS_SDK and PortSpeed is not None:
        _SPEED_MAP = {member.name: member for member in PortSpeed}
    else:
        _SPEED_MAP = {}
except ImportError:
    _SPEED_MAP = {}
    pass


def run_module():
    argument_spec = dict(
        **CONNECTION_ARGS,
        port=dict(type='list', elements='int', required=True),
        enabled=dict(type='bool'),
        speed=dict(type='str', choices=['AUTO', 'M10H', 'M10F', 'M100H', 'M100F', 'M1000F']),
        flow_control=dict(type='bool'),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_one_of=[['enabled', 'speed', 'flow_control']],
    )

    if not HAS_SDK:
        module.fail_json(msg='tplink_switch SDK not available: %s' % SDK_ERROR)

    p = module.params
    target_ports = p['port']
    desired_speed = _SPEED_MAP.get(p['speed']) if p['speed'] else None

    try:
        with make_switch(p) as sw:
            all_ports = sw.get_port_settings()
            port_map = {pi.port: pi for pi in all_ports}

            # Check whether any targeted port differs from the desired settings
            needs_change = False
            for port_num in target_ports:
                pi = port_map.get(port_num)
                if pi is None:
                    module.fail_json(msg='Port %d not found on switch' % port_num)
                if p['enabled'] is not None and pi.enabled != p['enabled']:
                    needs_change = True
                    break
                if desired_speed is not None and pi.speed_cfg != desired_speed:
                    needs_change = True
                    break
                if p['flow_control'] is not None and pi.fc_cfg != p['flow_control']:
                    needs_change = True
                    break

            if needs_change:
                if not module.check_mode:
                    sw.set_ports(
                        target_ports,
                        enabled=p['enabled'],
                        speed=desired_speed,
                        flow_control=p['flow_control'],
                    )
                    all_ports = sw.get_port_settings()
                    port_map = {pi.port: pi for pi in all_ports}

            result_ports = [serialize_port_info(port_map[n]) for n in target_ports if n in port_map]

    except Exception as e:
        module.fail_json(msg='Switch operation failed: %s' % str(e))

    module.exit_json(changed=needs_change, ports=result_ports)


def main():
    run_module()


if __name__ == '__main__':
    main()
