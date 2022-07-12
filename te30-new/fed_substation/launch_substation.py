# file: launch substation.py
"""
Function:
        start running substation federate
last update time: 2021-11-11
modified by Yuanliang Li

"""

import sys
sys.path.append('..')
# this is necessary since running this file is actually opening a new process
# where my_tesp_support_api package is not inside the path list
try:
  import helics
except:
  pass
from datetime import datetime
from datetime import timedelta
import json
from my_auction import my_auction  # import user-defined my_auction class for market
from my_hvac import my_hvac        # import user-defined my_hvac class for hvac controllers
import my_tesp_support_api.helpers as helpers
if sys.platform != 'win32':
  import resource



def my_substation_loop(configfile, metrics_root, helicsConfig, hour_stop=48, flag='WithMarket'):
  print ('starting HELICS substation loop', configfile, metrics_root, hour_stop, flag, flush=True)
  print ('##,tnow,tclear,ClearType,ClearQ,ClearP,BuyCount,BuyUnresp,BuyResp,SellCount,SellUnresp,SellResp,MargQ,MargFrac,LMP,RefLoad,ConSurplus,AveConSurplus,SupplierSurplus,UnrespSupplierSurplus', flush=True)
  bWantMarket = True
  if flag == 'NoMarket':
    bWantMarket = False
    print ('Disabled the market', flush=True)
  time_stop = int (hour_stop * 3600) # simulation time in seconds
  StartTime = '2013-07-01 00:00:00 -0800'
  time_fmt = '%Y-%m-%d %H:%M:%S %z'
  dt_now = datetime.strptime (StartTime, time_fmt)


  # ====== load the JSON dictionary (definiting the agents in substation); create the corresponding objects =========
  lp = open (configfile).read()
  dict = json.loads(lp)

  market_key = list(dict['markets'].keys())[0]  # only using the first market
  market_row = dict['markets'][market_key]
  unit = market_row['unit']

  auction_meta = {'clearing_price':{'units':'USD','index':0},'clearing_type':{'units':'[0..5]=[Null,Fail,Price,Exact,Seller,Buyer]','index':1},'consumer_surplus':{'units':'USD','index':2},'average_consumer_surplus':{'units':'USD','index':3},'supplier_surplus':{'units':'USD','index':4}}
  controller_meta = {'bid_price':{'units':'USD','index':0},'bid_quantity':{'units':unit,'index':1}}
  auction_metrics = {'Metadata':auction_meta,'StartTime':StartTime}
  controller_metrics = {'Metadata':controller_meta,'StartTime':StartTime}

  # initialize a user-defined auction object
  aucObj = my_auction (market_row, market_key)

  # get deta time and period
  dt = float(dict['dt']) # 15 seconds
  period = aucObj.period # 300 seconds

  # Initialize the helics federate according to helicsConfig
  hFed = helics.helicsCreateValueFederateFromConfig(helicsConfig) # the helics period is 15 seconds
  pubCount = helics.helicsFederateGetPublicationCount(hFed)
  subCount = helics.helicsFederateGetInputCount(hFed)
  gldName = dict['GridLABD']
  fedName = helics.helicsFederateGetName(hFed)
  bulkName = 'pypower'

  # initialize objects for subscriptions and the publications, and save these objects in dictionary
  subTemp = {}
  subVolt = {}
  subState = {}
  subHVAC = {}
  pubMtrMode = {}
  pubMtrPrice = {}
  pubMtrMonthly = {}
  pubHeating = {}
  pubCooling = {}
  pubDeadband = {}

  subFeeder = helics.helicsFederateGetSubscription (hFed, gldName + '/distribution_load')
  subLMP = helics.helicsFederateGetSubscription (hFed, bulkName + '/LMP_B7')
  pubC1 = helics.helicsFederateGetPublication (hFed, fedName + '/responsive_c1')
  pubC2 = helics.helicsFederateGetPublication (hFed, fedName + '/responsive_c2')
  pubDeg = helics.helicsFederateGetPublication (hFed, fedName + '/responsive_deg')
  pubMax = helics.helicsFederateGetPublication (hFed, fedName + '/responsive_max_mw')
  pubUnresp = helics.helicsFederateGetPublication (hFed, fedName + '/unresponsive_mw')
  pubAucPrice = helics.helicsFederateGetPublication (hFed, fedName + '/clear_price')

  hvacObjs = {}
  hvac_keys = list(dict['controllers'].keys())
  for key in hvac_keys:
    row = dict['controllers'][key]
    hvacObjs[key] = my_hvac (row, key, aucObj)
    ctl = hvacObjs[key]
    hseSubTopic = gldName + '/' + ctl.houseName
    mtrSubTopic = gldName + '/' + ctl.meterName
    mtrPubTopic = fedName + '/' + ctl.meterName
    ctlPubTopic = fedName + '/' + ctl.name
#    print ('{:s} hseSub={:s} mtrSub={:s}  mtrSub={:s}  ctlPub={:s}'.format (key, hseSubTopic, mtrSubTopic, mtrPubTopic, ctlPubTopic))
    subTemp[ctl] = helics.helicsFederateGetSubscription (hFed, hseSubTopic + '#air_temperature')
    subVolt[ctl] = helics.helicsFederateGetSubscription (hFed, mtrSubTopic + '#measured_voltage_1')
    subState[ctl] = helics.helicsFederateGetSubscription (hFed, hseSubTopic + '#power_state')
    subHVAC[ctl] = helics.helicsFederateGetSubscription (hFed, hseSubTopic + '#hvac_load')
    pubMtrMode[ctl] = helics.helicsFederateGetPublication (hFed, mtrPubTopic + '/bill_mode')
    pubMtrPrice[ctl] = helics.helicsFederateGetPublication (hFed, mtrPubTopic + '/price')
    pubMtrMonthly[ctl] = helics.helicsFederateGetPublication (hFed, mtrPubTopic + '/monthly_fee')
    pubHeating[ctl] = helics.helicsFederateGetPublication (hFed, ctlPubTopic + '/heating_setpoint')
    pubCooling[ctl] = helics.helicsFederateGetPublication (hFed, ctlPubTopic + '/cooling_setpoint')
    pubDeadband[ctl] = helics.helicsFederateGetPublication (hFed, ctlPubTopic + '/thermostat_deadband')

  # execute the substation federate
  helics.helicsFederateEnterExecutingMode(hFed)

  aucObj.initAuction()
  LMP = aucObj.mean # local marginal price
  refload = 0.0
  bSetDefaults = True

  # initialize something related to time step
  tnext_bid = period - 2 * dt  #3 * dt  # controllers calculate their final bids
  tnext_agg = period - 2 * dt  # auction calculates and publishes aggregate bid
  tnext_opf = period - 1 * dt  # PYPOWER executes OPF and publishes LMP (no action here)
  tnext_clear = period         # clear the market with LMP
  tnext_adjust = period        # + dt   # controllers adjust setpoints based on their bid and clearing

  time_granted = 0
  time_last = 0

  # simulation loop
  while (time_granted < time_stop):

    """ 1. step the simulation time """
    nextHELICSTime = int(min ([tnext_bid, tnext_agg, tnext_clear, tnext_adjust, time_stop]))
#    fncs.update_time_delta (nextFNCSTime-time_granted)
    time_granted = int (helics.helicsFederateRequestTime(hFed, nextHELICSTime))
    time_delta = time_granted - time_last
    time_last = time_granted
    hour_of_day = 24.0 * ((float(time_granted) / 86400.0) % 1.0)
#    print (dt_now, time_delta, timedelta (seconds=time_delta))
    dt_now = dt_now + timedelta (seconds=time_delta) # this is the actual time
    day_of_week = dt_now.weekday() # get the day of week
    hour_of_day = dt_now.hour # get the hour of the day
#    print ('STEP', time_last, time_granted, time_stop, time_delta, hour_of_day, day_of_week, tnext_bid, tnext_agg, tnext_opf, tnext_clear, tnext_adjust, flush=True)

    """ 2. update the state of controllers, substation LMP,  substation load, from HELICS"""
    LMP = helics.helicsInputGetDouble (subLMP) # get LMP from pypower
    aucObj.set_lmp (LMP)
    refload = 0.001 * helics.helicsInputGetDouble (subFeeder)  # supposed to be kW?
    aucObj.set_refload (refload)
    for key, obj in hvacObjs.items():
      obj.set_air_temp_from_helics (helics.helicsInputGetDouble (subTemp[obj]))
      cval = helics.helicsInputGetComplex(subVolt[obj])  # TODO: pyhelics needs to return complex instead of tuple
      obj.set_voltage_from_helics (complex (cval[0], cval[1]))
      obj.set_hvac_load_from_helics (helics.helicsInputGetDouble (subHVAC[obj]))
      obj.set_hvac_state_from_helics (helics.helicsInputGetString (subState[obj]))

    """3. update the time-of-day schedule (setpoints) for HVAC controllers,
    the thermostat setting will follow the  schedule
    """
    for key, obj in hvacObjs.items():
      if obj.change_basepoint (hour_of_day, day_of_week):
        helics.helicsPublicationPublishDouble (pubCooling[obj], obj.basepoint)
    if bSetDefaults:
      for key, obj in hvacObjs.items():
        helics.helicsPublicationPublishString (pubMtrMode[obj], 'HOURLY')
        helics.helicsPublicationPublishDouble (pubMtrMonthly[obj], 0.0)
        helics.helicsPublicationPublishDouble (pubDeadband[obj], obj.deadband)
        helics.helicsPublicationPublishDouble (pubHeating[obj], 60.0)
      bSetDefaults = False
#      print ('  SET DEFAULTS', flush=True)

    """4. controllers calculate their final bids"""
    if time_granted >= tnext_bid:
      aucObj.clear_bids() # auction remove all previous records, re-initialize
      time_key = str (int (tnext_clear))
      controller_metrics [time_key] = {}
      for key, obj in hvacObjs.items():
        bid = obj.formulate_bid () # bid is [price, quantity, on_state]
        if bid is not None:
          if bWantMarket:
            aucObj.collect_bid (bid)
          controller_metrics[time_key][obj.name] = [bid[0], bid[1]]
      tnext_bid += period # update the time for next bid
#      print ('  COLLECT BIDS', flush=True)

    """5. auction calculates and publishes aggregate bid"""
    if time_granted >= tnext_agg:
      aucObj.aggregate_bids()
      helics.helicsPublicationPublishDouble (pubUnresp, aucObj.agg_unresp)
      helics.helicsPublicationPublishDouble (pubMax, aucObj.agg_resp_max)
      helics.helicsPublicationPublishDouble (pubC2, aucObj.agg_c2)
      helics.helicsPublicationPublishDouble (pubC1, aucObj.agg_c1)
      helics.helicsPublicationPublishInteger (pubDeg, aucObj.agg_deg)
      tnext_agg += period
#      print ('  AGGREGATE BIDS', flush=True)


    """6. auction clears the market with LMP"""
    if time_granted >= tnext_clear:
      if bWantMarket:
        aucObj.clear_market(tnext_clear, time_granted)
        aucObj.surplusCalculation(tnext_clear, time_granted)
        helics.helicsPublicationPublishDouble (pubAucPrice, aucObj.clearing_price)
        for key, obj in hvacObjs.items():
          obj.inform_bid (aucObj.clearing_price)
      time_key = str (int (tnext_clear))
      auction_metrics [time_key] = {aucObj.name:[aucObj.clearing_price, aucObj.clearing_type, aucObj.consumerSurplus, aucObj.averageConsumerSurplus, aucObj.supplierSurplus]}
      tnext_clear += period

    """7. controllers adjust setpoints based on their bid and clearing"""
    if time_granted >= tnext_adjust:
      if bWantMarket:
        for key, obj in hvacObjs.items():
          helics.helicsPublicationPublishDouble (pubMtrPrice[obj], aucObj.clearing_price)
          if obj.bid_accepted ():
            helics.helicsPublicationPublishDouble (pubCooling[obj], obj.setpoint)
      tnext_adjust += period
#      print ('  ADJUSTED', flush=True)

  # ==================== Finalize the metrics output ===========================
  print ('writing metrics', flush=True)
  auction_op = open ('auction_' + metrics_root + '_metrics.json', 'w')
  controller_op = open ('controller_' + metrics_root + '_metrics.json', 'w')
  print (json.dumps(auction_metrics), file=auction_op)
  print (json.dumps(controller_metrics), file=controller_op)
  auction_op.close()
  controller_op.close()
  helpers.stop_helics_federate (hFed)


def show_resource_consumption ():
  if sys.platform != 'win32':
    usage = resource.getrusage(resource.RUSAGE_SELF)
    RESOURCES = [
        ('ru_utime', 'User time'),
        ('ru_stime', 'System time'),
        ('ru_maxrss', 'Max. Resident Set Size'),
        ('ru_ixrss', 'Shared Memory Size'),
        ('ru_idrss', 'Unshared Memory Size'),
        ('ru_isrss', 'Stack Size'),
        ('ru_inblock', 'Block inputs'),
        ('ru_oublock', 'Block outputs')]
    print('Resource usage:')
    for name, desc in RESOURCES:
      print('  {:<25} ({:<10}) = {}'.format(desc, name, getattr(usage, name)))





"""===============================main===================================="""

my_substation_loop('TE_Challenge_agent_dict.json','TE_ChallengeH',helicsConfig='TE_Challenge_HELICS_substation.json')
show_resource_consumption() # after simulation, print the resource consumption
