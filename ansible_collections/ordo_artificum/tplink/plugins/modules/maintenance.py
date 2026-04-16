#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: maintenance
short_description: Perform maintenance operations on a TP-Link managed switch
description:
  - Reboot, factory-reset, backup/restore configuration, run cable
    diagnostics, or change the admin password on a TP-Link managed switch.
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
  action:
    description: Maintenance action to perform.
    required: true
    type: str
    choices:
      - reboot
      - factory_reset
      - backup_config
      - restore_config
      - cable_diag
  dest:
    description: >
      Local filesystem path to save the configuration backup.
      Required when C(action=backup_config).
    type: path
  src:
    description: >
      Local filesystem path of a configuration file to restore.
      Required when C(action=restore_config).
    type: path
  ports:
    description: >
      Port numbers to run cable diagnostics on (1-based).
      If omitted all ports are tested.  Used with C(action=cable_diag).
    type: list
    elements: int
  force:
    description: >
      Required to be C(true) for C(action=factory_reset) as a safety guard.
      A factory reset erases all configuration and resets the switch IP to
      192.168.0.1.
    type: bool
    default: false
notes:
  - Runs on the Ansible controller; use C(connection: local).
  - C(backup_config) and C(restore_config) read/write files on the controller.
  - C(reboot) and C(restore_config) make the switch temporarily unreachable;
    add appropriate waits in your playbook.
  - C(factory_reset) resets the management IP to 192.168.0.1; subsequent
    tasks must target that address.
  - C(cable_diag) is a read-only diagnostic and always returns C(changed=false).
  - Check mode is supported for all actions except C(cable_diag) (which is
    always safe to run) and C(backup_config) (the backup file is always written).
'''

EXAMPLES = r'''
- name: Reboot switch
  ordo_artificum.tplink.maintenance:
    host: 192.168.0.1
    password: admin
    action: reboot
  connection: local

- name: Back up configuration
  ordo_artificum.tplink.maintenance:
    host: 192.168.0.1
    password: admin
    action: backup_config
    dest: /tmp/switch-backup.bin
  connection: local

- name: Restore configuration
  ordo_artificum.tplink.maintenance:
    host: 192.168.0.1
    password: admin
    action: restore_config
    src: /tmp/switch-backup.bin
  connection: local

- name: Run cable diagnostics on all ports
  ordo_artificum.tplink.maintenance:
    host: 192.168.0.1
    password: admin
    action: cable_diag
  connection: local
  register: diag

- name: Show cable diagnostic results
  ansible.builtin.debug:
    msg: "Port {{ item.port }}: {{ item.status }} ({{ item.length_m }} m)"
  loop: "{{ diag.cable_diag }}"

- name: Factory reset (DESTRUCTIVE)
  ordo_artificum.tplink.maintenance:
    host: 192.168.0.1
    password: admin
    action: factory_reset
    force: true
  connection: local
'''

RETURN = r'''
changed:
  description: Whether the switch state was changed.
  returned: always
  type: bool
cable_diag:
  description: Cable diagnostic results (action=cable_diag only).
  returned: when action is cable_diag
  type: list
  elements: dict
  contains:
    port:
      description: Port number.
      type: int
    status:
      description: Cable status (NoCable, Normal, Open, Short, OpenShort, CrossCable, NotTested).
      type: str
    length_m:
      description: Cable length in metres (-1 if not available).
      type: int
backup_size:
  description: Size in bytes of the configuration backup (action=backup_config only).
  returned: when action is backup_config
  type: int
'''

import os
from ansible.module_utils.basic import AnsibleModule

try:
    from ansible_collections.ordo_artificum.tplink.plugins.module_utils.common import (
        CONNECTION_ARGS, make_switch, HAS_SDK, SDK_ERROR, serialize_cable_diag,
    )
except ImportError:
    pass


def run_module():
    argument_spec = dict(
        **CONNECTION_ARGS,
        action=dict(
            type='str', required=True,
            choices=['reboot', 'factory_reset', 'backup_config',
                     'restore_config', 'cable_diag'],
        ),
        dest=dict(type='path'),
        src=dict(type='path'),
        ports=dict(type='list', elements='int'),
        force=dict(type='bool', default=False),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_if=[
            ['action', 'backup_config', ['dest']],
            ['action', 'restore_config', ['src']],
        ],
    )

    if not HAS_SDK:
        module.fail_json(msg='tplink_switch SDK not available: %s' % SDK_ERROR)

    p = module.params
    action = p['action']

    # Safety guard for factory_reset
    if action == 'factory_reset' and not p['force']:
        module.fail_json(
            msg='action=factory_reset requires force=true.  '
                'This will erase all configuration and reset the IP to 192.168.0.1.'
        )

    # Validate file paths before touching the switch
    if action == 'restore_config':
        if not os.path.isfile(p['src']):
            module.fail_json(msg='src file not found: %s' % p['src'])

    try:
        with make_switch(p) as sw:

            if action == 'reboot':
                if not module.check_mode:
                    sw.reboot()
                module.exit_json(changed=True)

            elif action == 'factory_reset':
                if not module.check_mode:
                    sw.factory_reset()
                module.exit_json(changed=True)

            elif action == 'backup_config':
                # Backup is always performed regardless of check_mode —
                # it reads from the switch and writes a local file, which
                # is inherently non-destructive.
                data = sw.backup_config()
                with open(p['dest'], 'wb') as fh:
                    fh.write(data)
                module.exit_json(changed=True, backup_size=len(data))

            elif action == 'restore_config':
                if not module.check_mode:
                    with open(p['src'], 'rb') as fh:
                        data = fh.read()
                    sw.restore_config(data)
                module.exit_json(changed=True)

            elif action == 'cable_diag':
                # Cable diagnostics are always safe to run, even in check mode.
                results = sw.run_cable_diagnostic(ports=p['ports'])
                module.exit_json(
                    changed=False,
                    cable_diag=[serialize_cable_diag(r) for r in results],
                )

    except Exception as e:
        module.fail_json(msg='Switch operation failed: %s' % str(e))


def main():
    run_module()


if __name__ == '__main__':
    main()
