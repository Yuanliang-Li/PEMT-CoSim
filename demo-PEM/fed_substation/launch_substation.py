# file: launch substation.py
"""
Function:
        start running substation federate (main federate) as well as other federates
last update time: 2021-12-11
modified by Yuanliang Li
"""

import sys
sys.path.append('..')
# this is necessary since running this file is actually opening a new process
# where my_tesp_support_api package is not inside the path list
import time
import os
import json
import helics
import random
import psutil
import subprocess
from PEM_Controller import PEM_Controller      # import user-defined my_hvac class for hvac controllers
from PEM_Coordinator import PEM_Coordinator
from datetime import datetime
from datetime import timedelta
from my_auction import AUCTION  # import user-defined my_auction class for market
import matplotlib.pyplot as plt
import my_tesp_support_api.helpers as helpers
from federate_helper import FEDERATE_HELPER, CURVES_TO_PLOT



"""================================Declare something====================================="""
data_path = './data/exp(test)/'
if not os.path.exists(data_path):
    os.makedirs(data_path)
configfile = 'TE_Challenge_agent_dict.json'
helicsConfig = 'TE_Challenge_HELICS_substation.json'
metrics_root = 'TE_ChallengeH'
hour_stop = 24
hasMarket = False # have market or not
vppEnable = True # have Vpp coordinator or not
drawFigure = True # draw figures during the simulation
fh = FEDERATE_HELPER(configfile, helicsConfig, metrics_root, hour_stop) # initialize the federate helper


"""=============================Start The Co-simulation==================================="""
fh.cosimulation_start() # launch the broker; launch other federates; the substation federate enters executing mode


"""============================Substation Initialization=================================="""
# initialize a user-defined PEM coordinator object (VPP object)
vpp_name = fh.vpp_name_list[0] # select the first VPP, it is possible to initialize multiple VPP
vpp = PEM_Coordinator(vpp_name,vppEnable)
vpp.get_helics_subspubs(fh.get_agent_pubssubs(vpp.name, 'VPP'))

# initialize a user-defined auction object
auction = AUCTION (fh.market_row, fh.market_key)
auction.get_helics_subspubs(fh.get_agent_pubssubs(auction.name, 'auction'))
auction.initAuction()


# initialize PEM controller objects (House objects)
houses = {}
for meter, info in fh.houseMeters_dict.items():
  key = info['house'] # house name
  hvac_name = info['HVAC']
  houses[key] = PEM_Controller(info, fh.agents_dict, auction) # initialize a house object
  houses[key].get_helics_subspubs(fh.get_agent_pubssubs(meter, 'meter')) # get subscriptions and publications for house meters
  houses[key].set_meter_mode() # set meter mode
  houses[key].get_cleared_price(auction.clearing_price)
  houses[key].hvac.get_helics_subspubs(fh.get_agent_pubssubs(hvac_name, 'HVAC'))
  houses[key].hvac.turn_OFF()  # at the beginning of the simulation, turn off all HVACs
last_house_name = key
vpp.num_loads = len(houses)


# initialize HVAC controller objects
# hvacObjs = {}
# hvac_keys = list(fh.agents_dict['hvacs'].keys())
# for key in hvac_keys:
#   row = fh.agents_dict['hvacs'][key]
#   hvacObjs[key] = HVAC(key, row, aucObj)
#   hvacObjs[key].get_helics_subspubs(fh.get_agent_pubssubs(key, 'HVAC'))
#   hvacObjs[key].set_meter_mode()
#   hvacObjs[key].turn_OFF()       # at the beginning of the simulation, turn off all HVACs
#   hvacObjs[key].get_cleared_price(aucObj.clearing_price) # get the initial cleared price from the market
# last_hvac_name = key # record the name of the last have object to get some time parameters


# initialize DATA_TO_PLOT class to visualize data in the simulation
curves = CURVES_TO_PLOT()
if drawFigure:
  fig, (ax1, ax2, ax3, ax4, ax5) = plt.subplots(5)



# initialize time parameters
StopTime= int(hour_stop * 3600) # co-simulation stop time in seconds
StartTime = '2013-07-01 00:00:00 -0800' # co-simulation start time
dt_now = datetime.strptime (StartTime, '%Y-%m-%d %H:%M:%S %z')

dt = fh.dt # HELCIS period (1 seconds)
update_period = houses[last_house_name].hvac.update_period # state update period (15 seconds)
request_period = houses[last_house_name].hvac.request_period   # local controller samples energy packet request period
market_period = auction.period # market period (300 seconds)
adjust_period = market_period # demand response period (300 seconds)
fig_update_period = 60 # figure update time period
tnext_update = dt             # the next time to update the state
tnext_request = dt            # the next time to request
tnext_lmp = market_period - 2 * dt  # the next time PYPOWER executes OPF and publishes LMP (no action here)
tnext_bid = market_period - 2 * dt  # the next time controllers calculate their final bids
tnext_agg = market_period - 2 * dt  # the next time auction calculates and publishes aggregate bid
tnext_clear = market_period         # the next time clear the market
tnext_adjust = market_period        # the next time controllers adjust control parameters/setpoints based on their bid and clearing price
tnext_fig_update = fig_update_period    # the next time to update figures

time_granted = 0
time_last = 0

"""============================Substation Loop=================================="""
print("Co-Simulation Start!")

while (time_granted < StopTime):

  """ 1. step the co-simulation time """
  nextHELICSTime = int(min ([tnext_update,tnext_request,tnext_lmp, tnext_bid, tnext_agg, tnext_clear, tnext_adjust, StopTime]))
  time_granted = int (helics.helicsFederateRequestTime(fh.hFed, nextHELICSTime))
  time_delta = time_granted - time_last
  time_last = time_granted
  hour_of_day = 24.0 * ((float(time_granted) / 86400.0) % 1.0)
  dt_now = dt_now + timedelta(seconds=time_delta) # this is the actual time
  day_of_week = dt_now.weekday() # get the day of week
  hour_of_day = dt_now.hour # get the hour of the day



  """ 2. PEM controllers update schedule, state, monitor energy packet length"""
  if time_granted >= tnext_update:
    for key, house in houses.items():
      house.update_state()
      house.hvac.change_basepoint (hour_of_day, day_of_week) # update schedule
      house.hvac.monitor_packet_length() # if the power delivery is on going, update the length of the packet
    tnext_update += update_period



  """ 3. houses generate/send request, VPP receives requests and dispatch YES/NO """
  if time_granted >= tnext_request:
    vpp.update_balance_signal(auction.lmp)
    for key, house in houses.items():
      request = house.hvac.send_request() # load generate/send its request
      vpp.receive_request(request) # vpp receives this request
    vpp.aggregate_requests()    # vpp aggregate requests and generate responses
    for response in vpp.response_list:
      houses[response['house-name']].hvac.receive_response(response['response'])
    curves.record_data(time_granted, houses, auction, vpp)
    tnext_request += request_period


  """ 4. market gets the local marginal price (LMP) from the bulk power grid"""
  if time_granted >= tnext_lmp:
    auction.get_lmp () # get local marginal price (LMP) from the bulk power grid
    auction.get_refload() # get distribution load from gridlabd
    tnext_lmp += market_period



  """ 5. prosumer demand response (adjust control parameters/setpoints) """
  if time_granted >= tnext_adjust:
    for key, house in houses.items():
      house.demand_response(auction.lmp)
    tnext_adjust += market_period


  """ 9. visualize some results during the simulation"""
  if drawFigure and time_granted >= tnext_fig_update:
    curves.update_curves(time_granted, houses, auction, vpp)
    ax1.cla()
    ax1.set_ylabel("VPP Load (kW/kVar)")
    ax1.plot(curves.curve_time_hour, curves.curve_vpp_load_p)
    ax1.plot(curves.curve_time_hour, curves.curve_balancing_signal)
    ax1.legend(['active', 'balancing_signal'])

    ax2.cla()
    ax2.set_ylabel("House Load (kW)")
    ax2.plot(curves.curve_time_hour, curves.curve_house_load_max)
    ax2.plot(curves.curve_time_hour, curves.curve_house_load_mean)
    ax2.plot(curves.curve_time_hour, curves.curve_house_load_min)
    ax2.legend(['max', 'mean', 'min'])

    ax3.cla()
    ax3.set_ylabel("Temperature (degF)")
    ax3.plot(curves.curve_time_hour, curves.curve_temp_max)
    ax3.plot(curves.curve_time_hour, curves.curve_temp_mean)
    ax3.plot(curves.curve_time_hour, curves.curve_temp_min)
    ax3.plot(curves.curve_time_hour, curves.curve_temp_basepoint_mean)
    ax3.legend(['max', 'mean', 'min', 'schedule'])

    ax4.cla()
    ax4.set_ylabel("LMP ($)")
    ax4.plot(curves.curve_time_hour, curves.curve_lmp)

    ax5.cla()
    ax5.set_xlabel("Time (h)")
    ax5.set_ylabel("Percentage")
    ax5.plot(curves.curve_time_hour, curves.curve_on_ratio)
    ax5.plot(curves.curve_time_hour, curves.curve_probability_mean)
    ax5.plot(curves.curve_time_hour, curves.curve_request_ratio)
    ax5.plot(curves.curve_time_hour, curves.curve_accepted_ratio)
    ax5.legend(['on-ratio','probability', 'request', 'accepted'])


    plt.pause(0.01)
    print("Time = ", time_granted, ', Accepted ratio: ', curves.curve_request_ratio[-1])

    tnext_fig_update += fig_update_period


"""============================ Finalize the metrics output ============================"""
curves.save_statistics(data_path)
print ('writing metrics', flush=True)
auction_op = open (data_path + 'auction_' + metrics_root + '_metrics.json', 'w')
house_op = open (data_path + 'house_' + metrics_root + '_metrics.json', 'w')
print (json.dumps(fh.auction_metrics), file=auction_op)
print (json.dumps(fh.prosumer_metrics), file=house_op)
auction_op.close()
house_op.close()
fh.destroy_federate()  # destroy the federate
fh.show_resource_consumption() # after simulation, print the resource consumption
plt.show()
# fh.kill_processes(True) # it is not suggested here because some other federates may not end their simulations, it will affect their output metrics


