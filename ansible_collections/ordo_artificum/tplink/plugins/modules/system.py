#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: system
short_description: Manage system settings on a TP-Link managed switch
description:
  - Configure system description, IP settings, LED state, and admin
    password on a TP-Link managed switch.
  - Any parameter left unset is left unchanged on the switch.
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
    description: Login password (current password).
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
  description:
    description: Device description string (up to 32 chars).
    type: str
  ip:
    description: Static IP address.
    type: str
  netmask:
    description: Subnet mask.
    type: str
  gateway:
    description: Default gateway.
    type: str
  dhcp:
    description: Enable DHCP.  When true, C(ip)/C(netmask)/C(gateway) are ignored.
    type: bool
  led:
    description: Enable port LEDs.
    type: bool
  new_password:
    description: New admin password.  C(password) is used as the old password.
    type: str
notes:
  - Runs on the Ansible controller; use C(connection: local).
  - Changing C(ip) or enabling C(dhcp) will change the switch's management
    address; subsequent tasks must target the new address.
  - Password changes cannot be verified without attempting them, so C(changed)
    will be true whenever C(new_password) is provided, even in check mode.
'''

EXAMPLES = r'''
- name: Set description and static IP
  ordo_artificum.tplink.system:
    host: 192.168.0.1
    password: admin
    description: core-switch
    ip: 10.1.1.1
    netmask: 255.255.255.0
    gateway: 10.1.1.254
    dhcp: false
  connection: local

- name: Turn off LEDs
  ordo_artificum.tplink.system:
    host: 192.168.0.1
    password: admin
    led: false
  connection: local

- name: Change admin password
  ordo_artificum.tplink.system:
    host: 192.168.0.1
    password: "{{ current_password }}"
    new_password: "{{ new_password }}"
  connection: local
'''

RETURN = r'''
system:
  description: System info after any changes.
  returned: always
  type: dict
ip_settings:
  description: IP configuration after any changes.
  returned: always
  type: dict
led:
  description: LED state after any changes.
  returned: always
  type: bool
changed:
  description: Whether any changes were made to the switch.
  returned: always
  type: bool
'''

from ansible.module_utils.basic import AnsibleModule

try:
    from ansible_collections.ordo_artificum.tplink.plugins.module_utils.common import (
        CONNECTION_ARGS, make_switch, HAS_SDK, SDK_ERROR,
        serialize_system_info, serialize_ip_settings,
    )
except ImportError:
    pass


def run_module():
    argument_spec = dict(
        **CONNECTION_ARGS,
        description=dict(type='str'),
        ip=dict(type='str'),
        netmask=dict(type='str'),
        gateway=dict(type='str'),
        dhcp=dict(type='bool'),
        led=dict(type='bool'),
        new_password=dict(type='str', no_log=True),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    if not HAS_SDK:
        module.fail_json(msg='tplink_switch SDK not available: %s' % SDK_ERROR)

    p = module.params
    changed = False

    try:
        with make_switch(p) as sw:
            current_info = sw.get_system_info()
            current_ip = sw.get_ip_settings()
            current_led = sw.get_led()

            # -- description --
            if p['description'] is not None and p['description'] != current_info.description:
                changed = True
                if not module.check_mode:
                    sw.set_device_description(p['description'])

            # -- IP settings --
            ip_needs_change = (
                (p['dhcp'] is not None and p['dhcp'] != current_ip.dhcp) or
                (p['ip'] is not None and p['ip'] != current_ip.ip) or
                (p['netmask'] is not None and p['netmask'] != current_ip.netmask) or
                (p['gateway'] is not None and p['gateway'] != current_ip.gateway)
            )
            if ip_needs_change:
                changed = True
                if not module.check_mode:
                    sw.set_ip_settings(
                        ip=p['ip'],
                        netmask=p['netmask'],
                        gateway=p['gateway'],
                        dhcp=p['dhcp'],
                    )

            # -- LED --
            if p['led'] is not None and p['led'] != current_led:
                changed = True
                if not module.check_mode:
                    sw.set_led(p['led'])

            # -- password --
            # Cannot verify without trying; always treat as changed.
            if p['new_password'] is not None:
                changed = True
                if not module.check_mode:
                    sw.change_password(
                        old_password=p['password'],
                        new_password=p['new_password'],
                    )

            # Re-read final state (skip on check mode or if nothing changed)
            if changed and not module.check_mode:
                sw.save_config()
                final_info = sw.get_system_info()
                final_ip = sw.get_ip_settings()
                final_led = sw.get_led()
            else:
                final_info = current_info
                final_ip = current_ip
                final_led = current_led

    except Exception as e:
        module.fail_json(msg='Switch operation failed: %s' % str(e))

    module.exit_json(
        changed=changed,
        system=serialize_system_info(final_info),
        ip_settings=serialize_ip_settings(final_ip),
        led=final_led,
    )


def main():
    run_module()


if __name__ == '__main__':
    main()
