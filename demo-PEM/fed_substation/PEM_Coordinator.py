# Copyright (C) 2017-2019 Battelle Memorial Institute
# file: hvac.py
"""Class that controls the responsive thermostat for one house.

Implements the ramp bidding method, with HVAC power as the
bid quantity, and thermostat setting changes as the response
mechanism.
"""
import math
import my_tesp_support_api.helpers as helpers
import math
import random
import helics
from collections import deque


class PEM_Coordinator:
    def __init__(self, name, enable = True):

        self.name = name
        self.enable = enable

        self.num_loads = 0

        self.vpp_load = 0 # kVA
        self.balance_signal = 200 # kVA

        self.request_list = []
        self.response_list = []
        self.request_ratio  = 0
        self.accepted_ratio  = 0

        self.subs = {}
        self.pubs = {}


    def receive_request(self, request):
        # request is a list [name, load type, power, length]
        if len(request) > 0:
            self.request_list.append(request)

    def aggregate_requests(self):

        self.get_vpp_load()
        num_requests = len(self.request_list)
        num_accepted = 0
        self.request_ratio = num_requests/self.num_loads
        self.response_list.clear()
        self.response_list = self.request_list.copy() # copy messages


        if len(self.response_list) > 0:
            if not self.enable: # if VPP coordinator is not enable, all requests will be accepted
                for i in range(len(self.response_list)):
                    self.response_list[i]['response'] = 'YES'
                    num_accepted += 1
            else:
                arrive_idx_list = list(range(len(self.response_list)))
                random.shuffle(arrive_idx_list) # randomize the arrive time
                load_est = self.vpp_load

                for idx in arrive_idx_list:
                    response = self.response_list[idx]
                    key = response['name']
                    load = response['power']
                    length = response['packet-length']
                    hvac_on = response['on']
                    hvac_kw = response['hvac_kw']
                    if hvac_kw < 0.1:     #actually, it should be "if not hvac_on"
                        load_est += load
                    if (self.balance_signal - load_est) >= 0:
                        self.response_list[idx]['response'] = 'YES'
                        num_accepted += 1
                    else:
                        self.response_list[idx]['response'] = 'NO'
                        load_est -= load

        if num_requests>0:
            self.accepted_ratio = num_accepted/num_requests
        else:
            self.accepted_ratio = 1

        self.request_list.clear()


    def get_vpp_load(self):

        cval = helics.helicsInputGetComplex(self.subs['vppPower'])
        self.vpp_load = cval[0] * 0.001

        # self.vpp_load = 0.001 * helics.helicsInputGetDouble (self.subs['subFeeder']) # it is supposed to be complex, but double is also ok (unit: kVA)


    def update_balance_signal(self, lmp):
        pass

    def get_helics_subspubs(self,input):
        self.subs = input[0]
        self.pubs = input[1]
