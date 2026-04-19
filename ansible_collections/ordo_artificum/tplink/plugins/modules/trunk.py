#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: trunk
short_description: Manage LAG (Link Aggregation Group) configuration on a TP-Link managed switch
description:
  - Create, update, or delete LAG (trunk) groups on a TP-Link managed switch.
  - The TL-SG108E supports up to two LAG groups.
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
  group_id:
    description: LAG group number (1 or 2).
    required: true
    type: int
    choices: [1, 2]
  ports:
    description: >
      Port numbers to assign to this LAG group (1-based).
      Required when C(state=present).
    type: list
    elements: int
  state:
    description: >
      C(present) ensures the LAG group exists with exactly the specified ports.
      C(absent) removes the LAG group.
    type: str
    choices: [present, absent]
    default: present
notes:
  - Runs on the Ansible controller; use C(connection: local).
'''

EXAMPLES = r'''
- name: Create LAG group 1 with ports 1 and 2
  ordo_artificum.tplink.trunk:
    host: 192.168.0.1
    password: admin
    group_id: 1
    ports: [1, 2]
    state: present
  connection: local

- name: Remove LAG group 1
  ordo_artificum.tplink.trunk:
    host: 192.168.0.1
    password: admin
    group_id: 1
    state: absent
  connection: local
'''

RETURN = r'''
trunk:
  description: Current trunk configuration after any changes.
  returned: always
  type: dict
changed:
  description: Whether the trunk configuration was changed.
  returned: always
  type: bool
'''

from ansible.module_utils.basic import AnsibleModule

try:
    from ansible_collections.ordo_artificum.tplink.plugins.module_utils.common import (
        CONNECTION_ARGS, make_switch, HAS_SDK, SDK_ERROR, serialize_trunk,
    )
except ImportError:
    pass


def run_module():
    argument_spec = dict(
        **CONNECTION_ARGS,
        group_id=dict(type='int', required=True, choices=[1, 2]),
        ports=dict(type='list', elements='int'),
        state=dict(type='str', default='present', choices=['present', 'absent']),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_if=[['state', 'present', ['ports']]],
    )

    if not HAS_SDK:
        module.fail_json(msg='tplink_switch SDK not available: %s' % SDK_ERROR)

    p = module.params
    gid = p['group_id']
    desired_ports = sorted(p['ports'] or [])
    changed = False

    try:
        with make_switch(p) as sw:
            tc = sw.get_port_trunk()
            current_ports = sorted(tc.groups.get(gid, []))

            if p['state'] == 'present':
                if current_ports != desired_ports:
                    changed = True
                    if not module.check_mode:
                        sw.set_port_trunk(gid, desired_ports)

            else:  # absent
                if gid in tc.groups:
                    changed = True
                    if not module.check_mode:
                        sw.set_port_trunk(gid, [])

            if changed and not module.check_mode:
                sw.save_config()
                tc = sw.get_port_trunk()

    except Exception as e:
        module.fail_json(msg='Switch operation failed: %s' % str(e))

    module.exit_json(changed=changed, trunk=serialize_trunk(tc))


def main():
    run_module()


if __name__ == '__main__':
    main()
