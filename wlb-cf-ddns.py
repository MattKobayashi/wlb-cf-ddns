#!/usr/bin/env python3

import os
import socket
from urllib3.poolmanager import PoolManager
import json

import requests
from requests import adapters
from vyos.configquery import ConfigTreeQuery


class InterfaceAdapter(adapters.HTTPAdapter):
    def __init__(self, **kwargs):
        self.iface = kwargs.pop('iface', None)
        super(InterfaceAdapter, self).__init__(**kwargs)

    def _socket_options(self):
        if self.iface is None:
            return []
        else:
            return [(socket.SOL_SOCKET, socket.SO_BINDTODEVICE, self.iface)]

    def init_poolmanager(self, connections, maxsize, block=False):
        self.poolmanager = PoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            socket_options=self._socket_options()
        )


# Configurables
zone_name = "example.com"
record_name = "wan.example.com"
api_token = "<your Cloudflare API token>"

# Get list of load-balanced WAN interfaces
interfaces_raw = []
conf_query = ConfigTreeQuery()
wlb_rules = conf_query.list_nodes(['load-balancing', 'wan', 'rule'])
for rule in wlb_rules:
    for interface in conf_query.list_nodes(
            ['load-balancing', 'wan', 'rule', rule, 'interface']
            ):
        interfaces_raw.append(interface)
interfaces = list(set(interfaces_raw))
del interfaces_raw
del wlb_rules
del conf_query

# Iterate through list of interfaces
api_auth = {'Authorization': 'Bearer ' + api_token}
for interface in interfaces:

    # Match interface name and state to env vars from wan_lb
    if interface == os.environ.get(
            'WLB_INTERFACE_NAME'
            ) and os.environ.get(
                'WLB_INTERFACE_STATE'
                ) == 'ACTIVE':
        print(
            'wlb-cf-ddns: Performing dynamic DNS update for interface:',
            os.environ.get('WLB_INTERFACE_NAME')
            )

        # Get external IP address for interface
        try:
            session = requests.Session()
            for prefix in ('http://', 'https://'):
                session.mount(prefix, InterfaceAdapter(
                    iface=str.encode(os.environ.get('WLB_INTERFACE_NAME'))
                    ))
            ip = (session.get("https://api.ipify.org").text)
            print(
                'wlb-cf-ddns: New external IPv4 address:',
                ip
                )
        except OSError:
            print('wlb-cf-ddns: Unable to connect to external IPv4 API!')
            break

        # Get zone ID from Cloudflare
        api_url = "https://api.cloudflare.com/client/v4/zones"
        api_call = requests.get(
            api_url,
            headers=api_auth
            )
        for result in json.loads(api_call.text)["result"]:
            if result["name"] == zone_name:
                zone_id = result["id"]

        # Get record ID from CloudFlare
        api_url = "https://api.cloudflare.com/client/v4/zones/" \
            + zone_id \
            + "/dns_records"
        api_call = requests.get(
            api_url,
            headers=api_auth
            )
        record_id = False
        for result in json.loads(api_call.text)["result"]:
            if result["comment"] == interface:
                record_id = result["id"]

        # Patch existing record
        if record_id is not False:
            print(
                'wlb-cf-ddns: Interface',
                interface,
                'has an existing DNS record, updating it...'
                )
            api_url = "https://api.cloudflare.com/client/v4/zones/" \
                + zone_id \
                + "/dns_records/" \
                + record_id
            params = json.loads('{"content": "'
                                + ip
                                + '", "name": "'
                                + record_name
                                + '", "type": "A", "comment": "'
                                + interface
                                + '"}')
            api_call = requests.patch(
                api_url,
                json=params,
                headers=api_auth
                )
            if api_call.status_code >= 400:
                print(
                    'wlb-cf-ddns: An error occurred',
                    'with the Cloudflare API call!'
                    )
                print('wlb-cf-ddns:', api_call.text)
            else:
                print('wlb-cf-ddns: Dynamic DNS record updated successfully!')

        # If record doesn't exist, create new record
        else:
            print(
                'wlb-cf-ddns: Interface',
                interface,
                'does not have an existing DNS record, creating it...'
                )
            api_url = "https://api.cloudflare.com/client/v4/zones/" \
                + zone_id \
                + "/dns_records/"
            params = json.loads('{"content": "'
                                + ip
                                + '", "name": "'
                                + record_name
                                + '", "type": "A", "comment": "'
                                + interface
                                + '"}')
            api_call = requests.post(
                api_url,
                json=params,
                headers=api_auth
                )
            if api_call.status_code >= 400:
                print(
                    'wlb-cf-ddns: An error occurred',
                    'with the Cloudflare API call!'
                    )
                print('wlb-cf-ddns:', api_call.text)
            else:
                print('wlb-cf-ddns: Dynamic DNS record created successfully!')
    
    # Delete record for failed interface
    elif interface == os.environ.get(
            'WLB_INTERFACE_NAME'
            ) and os.environ.get(
                'WLB_INTERFACE_STATE'
                ) == 'FAILED':
        print(
            'wlb-cf-ddns: Performing dynamic DNS update for interface:',
            os.environ.get('WLB_INTERFACE_NAME')
            )

        # Get zone ID from Cloudflare
        try:
            api_url = "https://api.cloudflare.com/client/v4/zones"
            api_call = requests.get(
                api_url,
                headers=api_auth
                )
            for result in json.loads(api_call.text)["result"]:
                if result["name"] == zone_name:
                    zone_id = result["id"]
        except OSError:
            print('wlb-cf-ddns: Unable to connect to external IPv4 API!')
            break

        # Get record ID from CloudFlare
        api_url = "https://api.cloudflare.com/client/v4/zones/" \
            + zone_id \
            + "/dns_records"
        api_call = requests.get(
            api_url,
            headers=api_auth
            )
        record_id = False
        for result in json.loads(api_call.text)["result"]:
            if result["comment"] == interface:
                record_id = result["id"]

        # Delete record if it exists
        if record_id is not False:
            print(
                'wlb-cf-ddns: Interface',
                interface,
                'has an existing DNS record, deleting it...'
                )
            api_url = "https://api.cloudflare.com/client/v4/zones/" \
                + zone_id \
                + "/dns_records/" \
                + record_id
            api_call = requests.delete(
                api_url,
                headers=api_auth
                )
            if api_call.status_code >= 400:
                print(
                    'wlb-cf-ddns: An error occurred',
                    'with the Cloudflare API call!'
                    )
                print('wlb-cf-ddns:', api_call.text)
            else:
                print('wlb-cf-ddns: Dynamic DNS record deleted successfully!')
        else:
            print(
                'wlb-cf-ddns: Interface', 
                interface,
                'does not have an existing DNS record, skipping...'
                )
    else:
        print('wlb-cf-ddns: No dynamic DNS updates required')
