#!/usr/bin/env python

# -*- coding: utf-8 -*-
# © 2022 Nokia
# Licensed under the Apache License 2.0 License
# SPDX-License-Identifier: Apache-2.0

#
# The contents of this file are licensed under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with the
# License. You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations under
# the License.

import logging

from ncclient.xml_ import to_xml, to_ele
from napalm.base.helpers import convert
from .util import _find_txt, NSMAP
from .bgp_neighbor import BGPNeighbor

#
# Netconf filters to retrieve only required attributes
#
GLOBAL_CONF_ITEMS = """
<local-as>
 <as-number/>
 <prepend-global-as/>
</local-as>
<multihop/>
<asn-4-byte/>
<keepalive/>
<remove-private>
 <limited/>
</remove-private>
<import/>
<export/>
<hold-time>
 <seconds/>
 <minimum-hold-time/>
</hold-time>
"""

GROUP_CONF_ITEMS = """
""" + GLOBAL_CONF_ITEMS + """
<peer-as/>
<local-address/>
"""

NEIGHBOR_CONF = """
<autonomous-system/>
<bgp>
    """+GLOBAL_CONF_ITEMS+"""
    <multipath>
     <ibgp/>
     <ebgp/>
    </multipath>
    <group>
     <dynamic-neighbor/>
     """+GROUP_CONF_ITEMS+"""
    </group>
    <neighbor>
        <ip-address>{neighbor_address}</ip-address>
        <group/>
        <description/>
    """+GROUP_CONF_ITEMS+"""
    </neighbor>
</bgp>
"""

NEIGHBOR_STATS = """
<bgp>
<neighbor>
<ip-address>{neighbor_address}</ip-address>
<statistics>
    <session-state/>
    <local-port/>
    <peer-identifier/>
    <peer-port/>
    <peer-as/>
    <operational-local-address/>
    <operational-remote-address/>
    <last-state/>
    <last-event/>
    <keep-alive-interval/>
    <hold-time-interval/>
    <number-of-update-flaps/>
    <received>
        <messages/>
        <updates/>
    </received>
    <sent>
        <messages/>
        <updates/>
        <queues/>
    </sent>
    <dynamically-configured/>
    <family-prefix>
        <ipv4>
            <active/>
            <received/>
            <suppressed/>
            <rejected/>
            <sent/>
        </ipv4>
        <ipv6>
            <active/>
            <received/>
            <suppressed/>
            <rejected/>
            <sent/>
        </ipv6>
    </family-prefix>
</statistics>
</neighbor>
</bgp>
"""

GET_BGP_NEIGHBORS_DETAILS = """
    <filter>
        <configure xmlns="urn:nokia.com:sros:ns:yang:sr:conf">
            <router>
             <router-name/>
          """+NEIGHBOR_CONF+"""
            </router>
            <service>
                <vprn>
                 <service-name/>
              """+NEIGHBOR_CONF+"""
                </vprn>
            </service>
        </configure>
        <state xmlns="urn:nokia.com:sros:ns:yang:sr:state">
            <router>
            """+NEIGHBOR_STATS+"""
            </router>
            <service>
                <vprn>
                """+NEIGHBOR_STATS+"""
                </vprn>
            </service>
        </state>
    </filter>
"""

log = logging.getLogger(__file__)

def get_bgp_neighbors_detail(conn,neighbor_address=""):
  data = to_ele(
      conn.get(
          filter=GET_BGP_NEIGHBORS_DETAILS.format(
              neighbor_address=neighbor_address
          ),
          with_defaults="report-all",
      ).data_xml
  )
  if log.isEnabledFor(logging.DEBUG):
    log.debug(to_xml(data, pretty_print=True))

  result = {}
  for nb in BGPNeighbor.list(data):

    session_state = nb.state_str('session-state')
    count = nb.counters( attrs=['active','suppressed','rejected','sent','received'], total=True )
    _local_as = nb.local_as()
    _remote_as = nb.state_int('peer-as') or nb.remote_as()
    _xbgp = "ibgp" if _local_as==_remote_as else "ebgp"
    _multipath = nb.conf_int(f'multipath/configure_ns:{_xbgp}') # Note: global only
    peer = {
      'up': session_state.lower()=="established",
      'local_as': _local_as,
      'remote_as': _remote_as,
      'router_id': nb.state_str('peer-identifier'),
      'local_address': nb.state_str('operational-local-address'),
      'routing_table': nb.vrf,
      'local_address_configured': nb.conf_str('local-address',include_global=False) != "",
      'local_port': nb.state_int('local-port'),
      'remote_address': nb.ip_address,
      'remote_port': nb.state_int('peer-port'),
      'multihop': nb.conf_int('multihop',include_global=True) > 0,
      'multipath': _multipath > 1,
      'remove_private_as': nb.conf_bool('remove-private/configure_ns:limited'),
      'import_policy': nb.conf_policies('import/configure_ns:policy'),
      'export_policy': nb.conf_policies('export/configure_ns:policy'),
      'input_messages': nb.state_int('received/state_ns:messages'),
      'output_messages': nb.state_int('sent/state_ns:messages'),
      'input_updates': nb.state_int('received/state_ns:updates'),
      'output_updates': nb.state_int('sent/state_ns:updates'),
      'messages_queued_out': nb.state_int('sent/state_ns:queues'),
      'connection_state': session_state,
      'previous_connection_state': nb.state_str('last-state'),
      'last_event': nb.state_str('last-event'),
      'suppress_4byte_as': nb.conf_str('asn-4-byte') == 'false',
      'local_as_prepend': nb.conf_bool('local-as/configure_ns:prepend-global-as'),
      'holdtime': nb.state_int('hold-time-interval'),
      'configured_holdtime': nb.conf_int('hold-time/configure_ns:seconds'),
      'keepalive': nb.state_int('keep-alive-interval'),
      'configured_keepalive': nb.conf_int('keepalive'),
      'active_prefix_count': count['active']['total'],
      'received_prefix_count': count['received']['total'],
      'accepted_prefix_count': count['received']['total'] - count['rejected']['total'],
      'suppressed_prefix_count': count['suppressed']['total'],
      'advertised_prefix_count': count['sent']['total'],
      'flap_count': nb.state_int('number-of-update-flaps')
    }

    if nb.vrf not in result:
      result[nb.vrf] = {}
    if peer['remote_as'] not in result[nb.vrf]:
      result[nb.vrf][ peer['remote_as'] ] = []
    result[nb.vrf][ peer['remote_as'] ].append(peer)

  return result
