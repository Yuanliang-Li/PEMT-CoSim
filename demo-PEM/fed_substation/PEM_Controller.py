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

class HVAC:
    """This agent manages thermostat

    Args:
        dict (dict): dictionary row for this agent from the JSON configuration file
        key (str): name of this agent, also key for its dictionary row
        aucObj (simple_auction): the auction this agent bids into

    Attributes:
        name (str): name of this agent
        control_mode (str): control mode from dict (CN_RAMP or CN_NONE, which still implements the setpoint schedule)
        houseName (str): name of the corresponding house in GridLAB-D, from dict
        meterName (str): name of the corresponding triplex_meter in GridLAB-D, from dict
        period (float): market clearing period, in seconds, from dict
        wakeup_start (float): hour of the day (0..24) for scheduled weekday wakeup period thermostat setpoint, from dict
        daylight_start (float): hour of the day (0..24) for scheduled weekday daytime period thermostat setpoint, from dict
        evening_start (float): hour of the day (0..24) for scheduled weekday evening (return home) period thermostat setpoint, from dict
        night_start (float): hour of the day (0..24) for scheduled weekday nighttime period thermostat setpoint, from dict
        wakeup_set (float): preferred thermostat setpoint for the weekday wakeup period, in deg F, from dict
        daylight_set (float): preferred thermostat setpoint for the weekday daytime period, in deg F, from dict
        evening_set (float): preferred thermostat setpoint for the weekday evening (return home) period, in deg F, from dict
        night_set (float): preferred thermostat setpoint for the weekday nighttime period, in deg F, from dict
        weekend_day_start (float): hour of the day (0..24) for scheduled weekend daytime period thermostat setpoint, from dict
        weekend_day_set (float): preferred thermostat setpoint for the weekend daytime period, in deg F, from dict
        weekend_night_start (float): hour of the day (0..24) for scheduled weekend nighttime period thermostat setpoint, from dict
        weekend_night_set (float): preferred thermostat setpoint for the weekend nighttime period, in deg F, from dict
        deadband (float): thermostat deadband in deg F, invariant, from dict
        offset_limit (float): maximum allowed change from the time-scheduled setpoint, in deg F, from dict
        ramp (float): bidding ramp denominator in multiples of the price standard deviation, from dict
        price_cap (float): the highest allowed bid price in $/kwh, from dict
        bid_delay (float): from dict, not implemented
        use_predictive_bidding (float): from dict, not implemented
        std_dev (float): standard deviation of expected price, determines the bidding ramp slope, initialized from aucObj
        mean (float): mean of the expected price, determines the bidding ramp origin, initialized from aucObj
        Trange (float): the allowed range of setpoint variation, bracketing the preferred time-scheduled setpoint
        air_temp (float): current air temperature of the house in deg F
        hvac_kw (float): most recent non-zero HVAC power in kW, this will be the bid quantity
        mtr_v (float): current line-neutral voltage at the triplex meter
        hvac_on (Boolean): True if the house HVAC is currently running
        basepoint (float): the preferred time-scheduled thermostat setpoint in deg F
        setpoint (float): the thermostat setpoint, including price response, in deg F
        bid_price (float): the current bid price in $/kwh
        cleared_price (float): the cleared market price in $/kwh
    """
    def __init__(self,name,dict,aucObj):
        """Initializes the class
        """
        self.name = name
        self.loadType = 'hvac'
        self.control_mode = dict['control_mode']
        self.houseName = dict['houseName']
        self.meterName = dict['meterName']
        self.period = float(dict['period'])
        self.wakeup_start = float(dict['wakeup_start'])
        self.daylight_start = float(dict['daylight_start'])
        self.evening_start = float(dict['evening_start'])
        self.night_start = float(dict['night_start'])
        self.wakeup_set = float(dict['wakeup_set'])
        self.daylight_set = float(dict['daylight_set'])
        self.evening_set = float(dict['evening_set'])
        self.night_set = float(dict['night_set'])
        self.weekend_day_start = float(dict['weekend_day_start'])
        self.weekend_day_set = float(dict['weekend_day_set'])
        self.weekend_night_start = float(dict['weekend_night_start'])
        self.weekend_night_set = float(dict['weekend_night_set'])
        self.deadband = float(dict['deadband'])
        self.offset_limit = float(dict['offset_limit'])
        self.ramp = float(dict['ramp'])
        self.price_cap = float(dict['price_cap'])
        self.bid_delay = float(dict['bid_delay'])
        self.use_predictive_bidding = float(dict['use_predictive_bidding'])

        # price related
        self.std_dev = aucObj.std_dev
        self.mean = aucObj.clearing_price
        # self.cleared_price = aucObj.clearing_price
        # self.cleared_price_window = deque(maxlen = 36) # this window saves history cleared price with a window size
        # self.bid_price = 0.0

        # state
        self.air_temp = 78.0
        self.hvac_kw = 3.0
        self.hvac_kw_last = self.hvac_kw # save the last power measurement that > 0
        self.hvac_on = False

        # setpoint related
        self.basepoint = 82
        self.fix_basepoint = False # if ture, the base point will not be changed all the time
        self.setpoint = 0.0
        self.offset = 0
        self.Trange = abs (2.0 * self.offset_limit)

        # PEM related
        self.update_period = 1 # the time interval that the energy meter measures its load, update state
        self.market_period = aucObj.period
        self.energyMarket = 0    # energy consumed within market period
        self.energy_cumulated = 0           # energy consumed in the co-simulation
        self.energyMarket_window = deque(maxlen = 3) # this windows saves latest n energy consumptions during the market period
        self.request_period = 2 # the time interval that a load generate its request according to its probability based on its internal state
        self.energy_packet_length = 1*30   # the energy packet total length when the request is accepted
        self.energy_packet_length_now = 0  # current energy packet length (unit: s)
        self.has_exit_mode = True
        self.exit_mode = True # if has exit-mode
        self.MTTR_base = 30   # initial mean time to request (equal to the packet length)
        self.MTTR_now = self.MTTR_base    # dynamic mean time to request
        self.MTTR_lower = self.MTTR_base*1/2  # lower bound for dynamic MTTR
        self.MTTR_upper = self.MTTR_base*10  # upper bound for dynamic MTTR

        self.packet_delivered = True  # True if the latest packer has been delivered, False if the packet is on delivery
        self.probability = 0   # current request probability
        self.response_strategy = "no"  # "setpoint" means price response by adjusting the setpoint according to the cleared price
                                       # "mttr" means price response by adjusting the mean time to request (MTTR)


        # publications and subscriptions
        self.subs = None
        self.pubs = None


    def get_helics_subspubs(self,input):
        self.subs = input[0]
        self.pubs = input[1]


    def update_state(self):

        # get temperate
        self.air_temp = helics.helicsInputGetDouble (self.subs['subTemp'])

        # get hvac load
        self.hvac_kw = max(helics.helicsInputGetDouble (self.subs['subHVACLoad']), 0) # unit kW
        if self.hvac_kw > 0.0:
            self.hvac_kw_last = self.hvac_kw

        # get hvac state (no work here)
        str = helics.helicsInputGetString (self.subs['subState'])

        # update request probability
        self.probability = self.get_request_probability()

        if self.has_exit_mode:
            self.exit_mode_operation()
        else:
            self.exit_mode = False


    def exit_mode_operation(self):
        self.setpoint = self.basepoint + self.offset

        up_bound = self.setpoint + 1/2*self.deadband
        lower_bound = self.setpoint - 1/2*self.deadband

        if self.air_temp > up_bound:
            self.turn_ON()
            self.exit_mode = True
            self.energy_packet_length_now = 0
            self.packet_delivered = True
        if self.air_temp < lower_bound:
            self.turn_OFF()
            self.exit_mode = True
            self.energy_packet_length_now = 0
            self.packet_delivered = True
        if self.exit_mode and self.air_temp < (self.setpoint + 3/8*self.deadband) \
                and self.air_temp > (self.setpoint - 3/8*self.deadband):
            # self.turn_OFF()
            self.exit_mode = False
            self.energy_packet_length_now = 0
            self.packet_delivered = True


    def get_request_probability(self):
        """
        Get current request probability for cooling system
        """
        self.setpoint = self.basepoint + self.offset

        up_bound = self.setpoint + 1/2*self.deadband
        lower_bound = self.setpoint - 1/2*self.deadband

        mr = 1/self.MTTR_now
        if self.air_temp >= up_bound:
            mu = float('inf')
        elif self.air_temp <= lower_bound:
            mu = 0
        else:
            mu = mr * (self.air_temp-lower_bound)/(up_bound-self.air_temp)*(up_bound-self.setpoint)/(self.setpoint-lower_bound)

        self.probability = 1 - math.exp(-mu*self.request_period)

        return self.probability


    def send_request(self):

        request = {}
        if self.packet_delivered and not self.exit_mode:
            if random.random() < self.probability:
                request['name'] = self.name
                request['house-name'] = self.houseName
                request['load-type'] = self.loadType
                request['power'] = self.hvac_kw_last
                request['on'] = self.hvac_on
                request['hvac_kw'] = self.hvac_kw
                request['packet-length'] = self.energy_packet_length
                request['response'] = None
                return request
        return request

    def receive_response(self, response):
        # response: YES or NO
        if response == 'YES':
            self.turn_ON()                   # once the request is accepted, turn on the device
            self.packet_delivered = False
            self.energy_packet_length_now = 0
        else:
            self.turn_OFF()
            self.energy_packet_length_now = 0


    def turn_ON(self):
        helics.helicsPublicationPublishString(self.pubs['pubThermostatState'], "COOL")
        self.hvac_on = True


    def turn_OFF(self):
        helics.helicsPublicationPublishString(self.pubs['pubThermostatState'], "OFF")
        self.hvac_on = False

    def monitor_packet_length(self):
        if not self.packet_delivered and self.hvac_on and not self.exit_mode: # if the last packet has been delivered and the hvac is on
            self.energy_packet_length_now += self.update_period
            if self.energy_packet_length_now >= self.energy_packet_length:
                self.turn_OFF()
                self.packet_delivered = True


    def update_energyMarket(self):
        dEnergy = self.hvac_kw*self.update_period/3600
        self.energyMarket += dEnergy
        self.energy_cumulated += dEnergy

    def predict_energyMarket(self, strategy):
        if strategy == 0:
            pass

        if strategy == 1:
            pass
        pass

    def record_energyMarket(self):
        self.energyMarket_window.append(self.energyMarket)

    def clean_energyMarket(self):
        self.energyMarket = 0


    def price_response(self, price):
        """ Update the thermostat setting if the last bid was accepted

        The last bid is always "accepted". If it wasn't high enough,
        then the thermostat could be turned up.p

        """
        if self.response_strategy == 'setpoint':
            if self.control_mode == 'CN_RAMP' and self.std_dev > 0.0:
                self.offset = (price - self.mean) * self.Trange / self.ramp / self.std_dev
                if self.offset < -self.offset_limit:
                    self.offset = -self.offset_limit
                elif self.offset > self.offset_limit:
                    self.offset = self.offset_limit
        if self.response_strategy == 'mttr':
            price_upper = 0.5
            self.MTTR_now = (price-price_upper)/(self.mean-price_upper)*(self.MTTR_base-self.MTTR_upper)+self.MTTR_upper

            self.MTTR_now = max(self.MTTR_now, self.MTTR_lower)
            self.MTTR_now = min(self.MTTR_now, self.MTTR_upper)


    # def formulate_bid(self):
    #     """ Bid to run the air conditioner through the next period
    #         Bid price is based on mean cleared price instead of the instant cleared price
    #
    #     Returns:
    #         [float, float, Boolean]: bid price in $/kwh, bid quantity in kW and current HVAC on state, or None if not bidding
    #     """
    #
    #     #print (' = formulating bid for {:s} kw={:.2f} on={:d} T={:.2f} Base={:.2f} mu={:.5f} ramp={:.3f} std={:.5f} Trange={:.2f} mode={:s}'.format (self.name,
    #     #  self.hvac_kw, self.hvac_on, self.air_temp, self.basepoint, self.mean, self.ramp, self.std_dev, self.Trange, self.control_mode))
    #
    #     if self.control_mode == 'CN_NONE':
    #         return None
    #
    #     # self.update_cleared_price_mean() # re-evaluate the mean of the cleared price
    #
    #     p = self.mean + (self.air_temp - self.basepoint) * self.ramp * self.std_dev / self.Trange
    #     if p >= self.price_cap:
    #         self.bid_price = self.price_cap
    #     elif p <= 0.0:
    #         self.bid_price = 0.0
    #     else:
    #         self.bid_price = p
    #     return [self.bid_price, self.hvac_kw, self.hvac_on]

    def change_basepoint(self,hod,dow):
        """ Updates the time-scheduled thermostat setting

        Args:
            hod (float): the hour of the day, from 0 to 24
            dow (int): the day of the week, zero being Monday

        Returns:
            Boolean: True if the setting changed, Falso if not
        """
        if not self.fix_basepoint:
            if dow > 4: # a weekend
                val = self.weekend_night_set
                if hod >= self.weekend_day_start and hod < self.weekend_night_start:
                    val = self.weekend_day_set
            else: # a weekday
                val = self.night_set
                if hod >= self.wakeup_start and hod < self.daylight_start:
                    val = self.wakeup_set
                elif hod >= self.daylight_start and hod < self.evening_start:
                    val = self.daylight_set
                elif hod >= self.evening_start and hod < self.night_start:
                    val = self.evening_set
            if abs(self.basepoint - val) > 0.1:
                self.basepoint = val




class PV:
    pass


class Battery:
    pass



class PEM_Controller:
    """ PEM controller, each house has one controller

    """
    def __init__(self,info, agents_dict, aucObj):

        # agent related
        self.name = info['house']
        hvac_name = info['HVAC']
        PV_name = info['PV']
        battery_name = info['battery']
        self.hvac = HVAC(hvac_name, agents_dict['hvacs'][hvac_name], aucObj) # create hvac object
        self.PV = None
        self.battery = None
        self.role = 'buyer' # current role: buyer or seller

        # market price related
        self.std_dev = aucObj.std_dev
        self.mean = aucObj.clearing_price
        self.cleared_price = aucObj.clearing_price
        self.cleared_price_window = deque(maxlen = 36) # this window saves history cleared price with a window size
        self.bid_price = 0.0

        # meter related
        self.mtr_voltage = 120.0
        self.mtr_power = 0
        self.unres_kw = 0


        self.pubs = None
        self.subs = None

    def get_helics_subspubs(self,input):
        self.subs = input[0]
        self.pubs = input[1]

    def set_meter_mode(self):
        helics.helicsPublicationPublishString (self.pubs['pubMtrMode'], 'HOURLY')
        helics.helicsPublicationPublishDouble (self.pubs['pubMtrMonthly'], 0.0)


    def update_state(self):
        # get meter voltage
        cval = helics.helicsInputGetComplex(self.subs['subVolt'])  # TODO: pyhelics needs to return complex instead of tuple
        self.mtr_voltage = abs (complex (cval[0], cval[1]))

        cval = helics.helicsInputGetComplex(self.subs['subMtrPower'])
        self.mtr_power = cval[0]*0.001 # unit. kW

        self.hvac.update_state()

        # get unresponsive load
        self.unres_kw = self.mtr_power - self.hvac.hvac_kw



    def get_cleared_price(self,price):
        """ get the cleared price from the market

        Args:
            price (float): cleared price in $/kwh
        """
        self.cleared_price = price
        self.cleared_price_window.append(self.cleared_price)

    def publish_meter_price(self):
        helics.helicsPublicationPublishDouble (self.pubs['pubMtrPrice'], self.cleared_price)


    def formulate_bid(self):
        """ Bid to run the air conditioner through the next period
            Bid price is based on mean cleared price instead of the instant cleared price

        Returns:
            [float, float, Boolean]: bid price in $/kwh, bid quantity in kW and current HVAC on state, or None if not bidding
        """

        #print (' = formulating bid for {:s} kw={:.2f} on={:d} T={:.2f} Base={:.2f} mu={:.5f} ramp={:.3f} std={:.5f} Trange={:.2f} mode={:s}'.format (self.name,
        #  self.hvac_kw, self.hvac_on, self.air_temp, self.basepoint, self.mean, self.ramp, self.std_dev, self.Trange, self.control_mode))

        if self.mtr_power > 0:
            self.role = 'buyer'
            if self.hvac.control_mode == 'CN_NONE':
                return None
            # self.update_cleared_price_mean() # re-evaluate the mean of the cleared price
            p = self.mean + (self.hvac.air_temp - self.hvac.basepoint) * self.hvac.ramp * self.std_dev / self.hvac.Trange
            if p >= self.hvac.price_cap:
                self.bid_price = self.hvac.price_cap
            elif p <= 0.0:
                self.bid_price = 0.0
            else:
                self.bid_price = p
            return [self.bid_price, self.mtr_power, True , self.role]
        elif self.mtr_power < 0:
            self.role = 'seller'
            self.bid_price = 0.01
            return [self.bid_price, self.mtr_power, True, self.role]
        else:
            return None

    def demand_response(self, price):
        self.hvac.price_response(price)



class VPP:
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
