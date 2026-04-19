#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: qos
short_description: Manage QoS settings on a TP-Link managed switch
description:
  - Configure the global QoS scheduling mode and per-port priority on a
    TP-Link managed switch.
  - C(mode) and C(port)/C(priority) may be set independently in the same task.
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
  mode:
    description: QoS scheduling mode.
    type: str
    choices: [PORT_BASED, DOT1P, DSCP]
  port:
    description: >
      Port number(s) to set priority on (1-based).
      Required when C(priority) is specified.
    type: list
    elements: int
  priority:
    description: >
      Port priority level.  1=Lowest, 2=Normal, 3=Medium, 4=Highest.
      Only applies in C(PORT_BASED) QoS mode.
      Required when C(port) is specified.
    type: int
    choices: [1, 2, 3, 4]
notes:
  - Runs on the Ansible controller; use C(connection: local).
  - At least one of C(mode) or C(port)/C(priority) must be specified.
  - Some firmware versions restart the switch's web server after changing QoS
    mode; the SDK handles re-authentication transparently.
'''

EXAMPLES = r'''
- name: Set QoS to port-based and prioritise port 1
  ordo_artificum.tplink.qos:
    host: 192.168.0.1
    password: admin
    mode: PORT_BASED
    port: [1]
    priority: 4
  connection: local

- name: Switch to DSCP-based QoS
  ordo_artificum.tplink.qos:
    host: 192.168.0.1
    password: admin
    mode: DSCP
  connection: local
'''

RETURN = r'''
mode:
  description: Current QoS mode after any changes.
  returned: always
  type: str
ports:
  description: Current per-port priority settings.
  returned: always
  type: list
changed:
  description: Whether any QoS settings were changed.
  returned: always
  type: bool
'''

from ansible.module_utils.basic import AnsibleModule

try:
    from ansible_collections.ordo_artificum.tplink.plugins.module_utils.common import (
        CONNECTION_ARGS, make_switch, HAS_SDK, SDK_ERROR,
        serialize_qos_port, QoSMode,
    )
    if HAS_SDK and QoSMode is not None:
        _MODE_MAP = {m.name: m for m in QoSMode}
    else:
        _MODE_MAP = {}
except ImportError:
    _MODE_MAP = {}
    pass


def run_module():
    argument_spec = dict(
        **CONNECTION_ARGS,
        mode=dict(type='str', choices=['PORT_BASED', 'DOT1P', 'DSCP']),
        port=dict(type='list', elements='int'),
        priority=dict(type='int', choices=[1, 2, 3, 4]),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_one_of=[['mode', 'port']],
        required_together=[['port', 'priority']],
    )

    if not HAS_SDK:
        module.fail_json(msg='tplink_switch SDK not available: %s' % SDK_ERROR)

    p = module.params
    changed = False

    try:
        with make_switch(p) as sw:
            current_mode, current_ports = sw.get_qos_settings()
            port_map = {qp.port: qp for qp in current_ports}

            # -- mode --
            if p['mode'] is not None:
                desired_mode = _MODE_MAP[p['mode']]
                if desired_mode != current_mode:
                    changed = True
                    if not module.check_mode:
                        sw.set_qos_mode(desired_mode)

            # -- port priority --
            if p['port'] is not None:
                target_ports = p['port']
                desired_prio = p['priority']
                needs_prio_change = any(
                    port_map.get(n) and port_map[n].priority != desired_prio
                    for n in target_ports
                )
                if needs_prio_change:
                    changed = True
                    if not module.check_mode:
                        sw.set_port_priority(target_ports, desired_prio)

            if changed and not module.check_mode:
                sw.save_config()
                current_mode, current_ports = sw.get_qos_settings()

    except Exception as e:
        module.fail_json(msg='Switch operation failed: %s' % str(e))

    module.exit_json(
        changed=changed,
        mode=current_mode.name,
        ports=[serialize_qos_port(qp) for qp in current_ports],
    )


def main():
    run_module()


if __name__ == '__main__':
    main()
