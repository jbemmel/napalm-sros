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

import logging, sys, os, json

if __name__ == "__main__":
  LOG_FORMAT = '%(asctime)s %(levelname)s %(filename)s:%(lineno)d %(message)s'
  logging.basicConfig(stream=sys.stdout, level=logging.INFO, format=LOG_FORMAT)

  from ncclient import manager
  from get_bgp_neighbors import get_bgp_neighbors

  with manager.connect(host="192.168.121.102", port=830,
        username='admin', password='admin',
        device_params={'name': 'sros'},
        hostkey_verify=False) as m:
    result = get_bgp_neighbors(m)
    logging.info(result)
    print( json.dumps(result,indent=2) )
    assert( 'global' in result )
