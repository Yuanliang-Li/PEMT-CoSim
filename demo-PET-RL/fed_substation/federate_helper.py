import time
import helics
import os
import sys
import json
import pickle
import psutil
from collections import deque
import subprocess
if sys.platform != 'win32':
  import resource



class FEDERATE_HELPER:
    def __init__(self, configfile, helicsConfig, metrics_root, hour_stop):

        self.configfile = configfile
        self.helicsConfig = helicsConfig
        with open(configfile, encoding='utf-8') as f:
            self.agents_dict = json.loads(f.read()) # federate_config is the dict data structure
            f.close()
        with open(helicsConfig, encoding='utf-8') as f:
            self.helics_config = json.loads(f.read()) # federate_config is the dict data structure
            f.close()

        """helics configuration related"""
        # basic information
        self.dt = float(self.helics_config['period'])
        self.duration = int(self.agents_dict['duration'])
        self.gldName = self.agents_dict['GridLABD']
        self.bulkName = 'pypower'
        self.hFed = None # the helics period is 15 seconds
        self.fedName = self.helics_config['name']
        self.is_destroyed = True
        self.pubCount = 0
        self.subCount = 0

        self.vpp_name_list = list(self.agents_dict['VPPs'].keys())
        self.house_name_list = list(self.agents_dict['houses'].keys())
        self.billingmeter_name_list = [self.agents_dict['houses'][house]['billingmeter_id'] for house in self.house_name_list]
        self.hvac_name_list = [houseName + '_hvac' for houseName in self.house_name_list]
        self.inverter_name_list = list(self.agents_dict['inverters'].keys())


        self.housesInfo_dict = {} # where the house name is the key,
        # each item includes 5 key:value for
        # 'meter': name of the triplex meter for the house
        # 'VPP'  : name of the VPP
        # 'HVAC' : name of the HVAC
        # 'PV'   : name of the PV inverter; if no PV, None
        # 'battery': name of battery inverter; if no battery, None
        for i, houseName in enumerate(self.house_name_list):
            self.housesInfo_dict[houseName] = {}
            hvacName = self.hvac_name_list[i]
            meter = self.billingmeter_name_list[i]
            vpp = self.agents_dict['houses'][houseName]['house_class']
            self.housesInfo_dict[houseName]['VPP'] = vpp
            self.housesInfo_dict[houseName]['meter'] = meter
            self.housesInfo_dict[houseName]['HVAC'] = hvacName
            self.housesInfo_dict[houseName]['PV'] = None
            self.housesInfo_dict[houseName]['battery'] = None

        for key, dict in self.agents_dict['inverters'].items():
            billingmeter_id = dict['billingmeter_id']
            if billingmeter_id in self.billingmeter_name_list:
                house_name = self.house_name_list[self.billingmeter_name_list.index(billingmeter_id)]
                resource = dict['resource']
                if resource == 'solar':
                    self.housesInfo_dict[house_name]['PV'] = key
                if resource == 'battery':
                    self.housesInfo_dict[house_name]['battery'] = key

        # initialize objects for subscriptions and the publications, and save these objects in dictionary
        # for House
        self.subsTemp = {} # subscriptions dict for HVAC temperature
        self.subsVolt = {} # subscriptions dict for house meter measured_voltage_1
        self.subsMtrPower = {} # subscriptions dict for house billing meter measured_power
        self.subsMtrDemand = {} # subscriptions dict for house meter measured_demand
        self.subsHousePower = {} # subscriptions dict for house meter measured_power
        self.subsSolarPower = {} # subscriptions dict for solar measured_power
        self.subsSolarVout = {} # subscriptions dict for solar Vout
        self.subsSolarIout = {} # subscriptions dict for solar Iout
        self.subsBattPower = {}  # subscriptions dict for battery measured_power
        self.subsBattSoC = {}  # subscriptions dict for battery SoC
        self.subsState = {} # subscriptions dict for HVAC power state
        self.subsHVACLoad = {}  # subscriptions dict for HVAC load
        self.subsHouseLoad = {}  # subscriptions dict for HVAC load
        self.pubsMtrMode = {}   # publications dict for billing mode
        self.pubsMtrPrice = {}  # publications dict for price
        self.pubsMtrMonthly = {} # publications dict for monthly_fee
        self.pubsHeatingSetpoint = {}  # publications dict for heating setpoint
        self.pubsCoolingSetpoint = {}  # publications dict for cooling setpoint
        self.pubsDeadband = {} # publications dict for cooling Deadband
        self.pubsThermostatState = {} # publications for thermostat state
        self.subsVPPMtrPower = {} # subscription dict for VPP measured power
        self.pubsCharge_on_threshold = {}
        self.pubsCharge_off_threshold = {}
        self.pubsDischarge_on_threshold = {}
        self.pubsDischarge_off_threshold = {}
        self.pubsPVPout = {}
        self.pubsPVQout = {}

        # for grid
        self.subFeeder = None
        self.subLMP = None
        self.pubC1 = None
        self.pubC2 = None
        self.pubDeg = None
        self.pubMax = None
        self.pubUnresp = None
        self.pubAucPrice = None


        """agents related"""
        self.market_key = list(self.agents_dict['markets'].keys())[0]  # only using the first market
        self.market_row = self.agents_dict['markets'][self.market_key]

        """metrics related"""
        unit = self.market_row['unit']
        StartTime = '2013-07-01 00:00:00 -0800'
        self.auction_meta = {'clearing_price':{'units':'USD','index':0},'clearing_type':{'units':'[0..5]=[Null,Fail,Price,Exact,Seller,Buyer]','index':1},'consumer_surplus':{'units':'USD','index':2},'average_consumer_surplus':{'units':'USD','index':3},'supplier_surplus':{'units':'USD','index':4}}
        self.prosumer_meta = {'bid_price':{'units':'USD','index':0},'bid_quantity':{'units':unit,'index':1}, 'hvac_needed':{'units':unit,'index':2}, 'role':{'units':unit,'index':3}}
        self.auction_metrics = {'Metadata':self.auction_meta,'StartTime':StartTime}
        self.prosumer_metrics = {'Metadata':self.prosumer_meta,'StartTime':StartTime}

        self.processes_list = []

    def create_broker(self):
        cmd0 = "helics_broker -f 6 --loglevel=1 --name=mainbroker >helics_broker.log 2>&1"
        self.processes_list.append(subprocess.Popen(cmd0, stdout=subprocess.PIPE, shell=True))
        print("HELICS broker created!")

    def create_federate(self):
        self.hFed = helics.helicsCreateValueFederateFromConfig(self.helicsConfig) # the helics period is 15 seconds

    def register_pubssubs(self):
        self.pubCount = helics.helicsFederateGetPublicationCount(self.hFed)
        self.subCount = helics.helicsFederateGetInputCount(self.hFed)

        self.subFeeder = helics.helicsFederateGetSubscription (self.hFed, self.gldName + '/distribution_load')
        self.subLMP = helics.helicsFederateGetSubscription (self.hFed, self.bulkName + '/LMP_B7')
        self.pubC1 = helics.helicsFederateGetPublication (self.hFed, self.fedName + '/responsive_c1')
        self.pubC2 = helics.helicsFederateGetPublication (self.hFed, self.fedName + '/responsive_c2')
        self.pubDeg = helics.helicsFederateGetPublication (self.hFed, self.fedName + '/responsive_deg')
        self.pubMax = helics.helicsFederateGetPublication (self.hFed, self.fedName + '/responsive_max_mw')
        self.pubUnresp = helics.helicsFederateGetPublication (self.hFed, self.fedName + '/unresponsive_mw')
        self.pubAucPrice = helics.helicsFederateGetPublication (self.hFed, self.fedName + '/clear_price')

        for house_name, val in self.housesInfo_dict.items():
            hvac_name = val['HVAC']
            meter_name = val['meter']
            house_meter_name = self.agents_dict['houses'][house_name]['parent']

            houseSubTopic = self.gldName + '/' + house_name  # subs from gridlabd
            billMeterSubTopic = self.gldName + '/' + meter_name  # subs from meter
            houseMeterSubTopic = self.gldName + '/' + house_meter_name
            billMeterPubTopic = self.fedName + '/' + meter_name  # publication for meter
            hvacPubTopic = self.fedName + '/' + hvac_name   # publication for HVAC controller

            self.pubsMtrMode[house_name] = helics.helicsFederateGetPublication (self.hFed, billMeterPubTopic + '/bill_mode')
            self.pubsMtrPrice[house_name] = helics.helicsFederateGetPublication (self.hFed, billMeterPubTopic + '/price')
            self.pubsMtrMonthly[house_name] = helics.helicsFederateGetPublication (self.hFed, billMeterPubTopic + '/monthly_fee')
            self.subsVolt[house_name] = helics.helicsFederateGetSubscription (self.hFed, billMeterSubTopic + '#measured_voltage_1')
            self.subsMtrPower[house_name] = helics.helicsFederateGetSubscription (self.hFed, billMeterSubTopic + '#measured_power')
            self.subsMtrDemand[house_name] = helics.helicsFederateGetSubscription (self.hFed, billMeterSubTopic + '#measured_demand')
            self.subsHousePower[house_name] = helics.helicsFederateGetSubscription (self.hFed, houseMeterSubTopic + '#measured_power')

            self.subsTemp[house_name] = helics.helicsFederateGetSubscription (self.hFed, houseSubTopic + '#air_temperature')
            self.subsState[house_name] = helics.helicsFederateGetSubscription (self.hFed, houseSubTopic + '#power_state')
            self.subsHVACLoad[house_name] = helics.helicsFederateGetSubscription (self.hFed, houseSubTopic + '#hvac_load')
            self.subsHouseLoad[house_name] = helics.helicsFederateGetSubscription (self.hFed, houseSubTopic + '#total_load')
            self.pubsHeatingSetpoint[house_name] = helics.helicsFederateGetPublication (self.hFed, hvacPubTopic + '/heating_setpoint')
            self.pubsCoolingSetpoint[house_name] = helics.helicsFederateGetPublication (self.hFed, hvacPubTopic + '/cooling_setpoint')
            self.pubsDeadband[house_name] = helics.helicsFederateGetPublication (self.hFed, hvacPubTopic + '/thermostat_deadband')
            self.pubsThermostatState[house_name] = helics.helicsFederateGetPublication (self.hFed, hvacPubTopic + '/thermostat_mode') # new added by Yuanliang

            if val['PV'] != None:
                solar_meter_name = self.agents_dict['inverters'][val['PV']]['parent']
                solar_array_name = self.agents_dict['inverters'][val['PV']]['resource_name']
                pvMeterSubTopic = self.gldName + '/' + solar_meter_name
                pvArraySubTopic = self.gldName + '/' + solar_array_name
                self.subsSolarPower[house_name] =  helics.helicsFederateGetSubscription (self.hFed, pvMeterSubTopic + '#measured_power')
                self.subsSolarVout[house_name] =  helics.helicsFederateGetSubscription (self.hFed, pvArraySubTopic + '#V_Out')
                self.subsSolarIout[house_name] =  helics.helicsFederateGetSubscription (self.hFed, pvArraySubTopic + '#I_Out')

                solar_inv_name = val['PV']
                pvCtlSubTopic = self.fedName + '/' + solar_inv_name
                self.pubsPVPout[house_name] = helics.helicsFederateGetPublication (self.hFed, pvCtlSubTopic + '/P_Out')
                self.pubsPVQout[house_name] = helics.helicsFederateGetPublication (self.hFed, pvCtlSubTopic + '/Q_Out')

            if val['battery'] != None:
                battery_meter_name = self.agents_dict['inverters'][val['battery']]['parent']
                battery_name = self.agents_dict['inverters'][val['battery']]['resource_name']
                battMeterSubTopic = self.gldName + '/' + battery_meter_name
                battSubTopic = self.gldName + '/' + battery_name
                self.subsBattPower[house_name] =  helics.helicsFederateGetSubscription (self.hFed, battMeterSubTopic + '#measured_power')
                self.subsBattSoC[house_name] =  helics.helicsFederateGetSubscription (self.hFed, battSubTopic + '#state_of_charge')

                battery_inv_name = val['battery']
                battCtlPubTopic = self.fedName + '/' + battery_inv_name
                self.pubsCharge_on_threshold[house_name] =  helics.helicsFederateGetPublication (self.hFed, battCtlPubTopic + '/charge_on_threshold')
                self.pubsCharge_off_threshold[house_name] =  helics.helicsFederateGetPublication (self.hFed, battCtlPubTopic + '/charge_off_threshold')
                self.pubsDischarge_on_threshold[house_name] =  helics.helicsFederateGetPublication (self.hFed, battCtlPubTopic + '/discharge_on_threshold')
                self.pubsDischarge_off_threshold[house_name] =  helics.helicsFederateGetPublication (self.hFed, battCtlPubTopic + '/discharge_off_threshold')


        for i, vpp_name in enumerate(self.vpp_name_list):
            vpp_meter_name =  self.agents_dict['VPPs'][vpp_name]['VPP_meter']
            vppSubTopic = self.gldName + '/' + vpp_meter_name
            self.subsVPPMtrPower[vpp_name] = helics.helicsFederateGetSubscription (self.hFed, vppSubTopic + '#measured_power')


    def get_agent_pubssubs(self,key, category, info = None):
        # get publications and subscriptions for a specific agent
        agent_subs = {}
        agent_pubs = {}

        if category == 'house': # the key is the house name
            # for HVAC
            agent_subs['subTemp'] = self.subsTemp[key]
            agent_subs['subState'] = self.subsState[key]
            agent_subs['subHVACLoad'] = self.subsHVACLoad[key]
            agent_pubs['pubHeatingSetpoint'] = self.pubsHeatingSetpoint[key]
            agent_pubs['pubCoolingSetpoint'] = self.pubsCoolingSetpoint[key]
            agent_pubs['pubDeadband'] = self.pubsDeadband[key]
            agent_pubs['pubThermostatState'] = self.pubsThermostatState[key]

            # for meters (including sub-meters)
            agent_subs['subVolt'] = self.subsVolt[key]
            agent_subs['subMtrPower'] = self.subsMtrPower[key]
            agent_subs['subMtrDemand'] = self.subsMtrDemand[key]
            agent_pubs['pubMtrMode'] = self.pubsMtrMode[key]
            agent_pubs['pubMtrPrice'] = self.pubsMtrPrice[key]
            agent_pubs['pubMtrMonthly'] = self.pubsMtrMonthly[key]
            agent_subs['subHousePower'] = self.subsHousePower[key]
            agent_subs['subHouseLoad'] = self.subsHouseLoad[key]
            if info['PV'] != None:
                agent_subs['subSolarPower'] = self.subsSolarPower[key]
                agent_subs['subSolarVout'] = self.subsSolarVout[key]
                agent_subs['subSolarIout'] = self.subsSolarIout[key]
                agent_pubs['pubPVPout'] = self.pubsPVPout[key]
                agent_pubs['pubPVQout'] = self.pubsPVQout[key]

            if info['battery'] != None:
                agent_subs['subBattPower'] = self.subsBattPower[key]
                agent_subs['subBattSoC'] = self.subsBattSoC[key]
                agent_pubs['pubCharge_on_threshold'] = self.pubsCharge_on_threshold[key]
                agent_pubs['pubCharge_off_threshold'] = self.pubsCharge_off_threshold[key]
                agent_pubs['pubDischarge_on_threshold'] = self.pubsDischarge_on_threshold[key]
                agent_pubs['pubDischarge_off_threshold'] = self.pubsDischarge_off_threshold[key]

        if category == "auction": # the key is the auction name
            agent_subs['subLMP'] = self.subLMP
            agent_subs['subFeeder'] = self.subFeeder
            agent_pubs['pubAucPrice'] = self.pubAucPrice
            agent_pubs['pubUnresp'] = self.pubUnresp
            agent_pubs['pubMax'] = self.pubMax
            agent_pubs['pubC2'] = self.pubC2
            agent_pubs['pubC1'] = self.pubC1
            agent_pubs['pubDeg'] = self.pubDeg
            # for i, vpp_name in enumerate(self.vpp_name_list):
            #     agent_subs['vppPower'] = self.subsVPPMtrPower[vpp_name]

        if category == "VPP": # the key is the vpp name
            agent_subs['subFeeder'] = self.subFeeder
            agent_subs['vppPower'] = self.subsVPPMtrPower[key]

        if category == "weather":
            pass

        return agent_subs, agent_pubs


    def FederateEnterExecutingMode(self):
        helics.helicsFederateEnterExecutingMode(self.hFed)
        print("Substation federate launched!")

    def destroy_federate(self):
        helics.helicsFederateDestroy(self.hFed)
        self.is_destroyed = True
        print("Federate {} has been destroyed".format(self.fedName))

    def cosimulation_start(self):

        # 1. kill processes of all federates and broker
        self.kill_processes(True)
        # 2. create a global broker
        self.create_broker()
        # 3. create the main federate
        while not self.is_destroyed:
            self.destroy_federate()
        self.create_federate()
        self.register_pubssubs()
        self.is_destroyed = False
        # 4. execute other federates
        self.run_other_federates()
        # 5. execute the main federate (it should be in the final)
        self.FederateEnterExecutingMode()

    def run_other_federates(self):
        TESP_INSTALL = os.environ['TESP_INSTALL']
        TESP_SUPPORT = TESP_INSTALL+'/share/support'
        SCHED_PATH = TESP_SUPPORT+'/schedules'
        EPW = TESP_SUPPORT+'/energyplus/USA_AZ_Tucson.Intl.AP.722740_TMY3.epw'
        duration = str(self.duration)

        # command to launch gridlabd federate
        cmd1 = "cd ../fed_gridlabd/ && gridlabd -D SCHED_PATH={} -D USE_HELICS -D METRICS_FILE=TE_ChallengeH_metrics.json TE_Challenge.glm >gridlabd.log 2>&1".format(SCHED_PATH)
        # command to launch weather federate
        cmd2 = "cd ../fed_weather/ && python3 launch_weather.py >weather.log 2>&1"
        # command to launch pypower federate
        cmd3 = "cd ../fed_pypower/ && python3 launch_pypower.py >pypower.log 2>&1"
        # command to launch energyplus federate
        cmd4 = "cd ../fed_energyplus/ && export HELICS_CONFIG_FILE=helics_eplus.json && exec energyplus -w {} -d output -r MergedH.idf >eplus.log 2>&1".format(EPW)
        # command to launch energyplus agent (it is also a federate)
        cmd5 = "cd ../fed_energyplus/ && eplus_agent_helics {} 300s SchoolDualController eplus_TE_ChallengeH_metrics.json  0.02 25 4 4 helics_eplus_agent.json >eplus_agent.log 2>&1".format(duration)

        self.processes_list.append(subprocess.Popen(cmd1, stdout=subprocess.PIPE, shell=True))
        self.processes_list.append(subprocess.Popen(cmd2, stdout=subprocess.PIPE, shell=True))
        self.processes_list.append(subprocess.Popen(cmd3, stdout=subprocess.PIPE, shell=True))
        self.processes_list.append(subprocess.Popen(cmd4, stdout=subprocess.PIPE, shell=True))
        self.processes_list.append(subprocess.Popen(cmd5, stdout=subprocess.PIPE, shell=True))
        print("Gridlabd, Weather, Pypower, EnergyPlus, EnergyPlus Agent, launched!")



    def kill_processes(self, kill_subprocess = False):
        killed_list = []
        for proc in psutil.process_iter():
            if proc.name() == "helics_broker":
                os.system("kill -9 {}".format(proc.pid))
                killed_list.append("helics_broker")
                continue
            if proc.name() == "gridlabd" and "gridlabd" in proc.cmdline():
                os.system("kill -9 {}".format(proc.pid))
                killed_list.append("gridlabd")
                continue
            if proc.name() == "python3" and "launch_weather.py" in proc.cmdline():
                os.system("kill -9 {}".format(proc.pid))
                killed_list.append("launch_weather.py")
                continue
            if proc.name() == "python3" and "launch_pypower.py" in proc.cmdline():
                os.system("kill -9 {}".format(proc.pid))
                killed_list.append("launch_pypower.py")
                continue
            if proc.name() == "energyplus" and "energyplus" in proc.cmdline():
                os.system("kill -9 {}".format(proc.pid))
                killed_list.append("energyplus")
                continue
            if proc.name() == "eplus_agent_helics" and "eplus_agent_helics" in proc.cmdline():
                os.system("kill -9 {}".format(proc.pid))
                killed_list.append("eplus_agent_helics")
                continue

        if kill_subprocess : # kill subprocesses
            if len(self.processes_list)>0:
                for process in self.processes_list:
                    while(str(process.poll())=="None"):
                        pass
                for process in self.processes_list:
                    process.kill()
                num_processes = len(self.processes_list)
                for i in range(num_processes): # maybe it can free the memory for all processes
                    del self.processes_list[0]
        if len(killed_list) > 0:
            print("Processes: ", killed_list, " has been killed successfully!")

    def show_resource_consumption (self):
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


class CURVES_TO_PLOT:
    def __init__(self, num_prosumers):

        self.num_prosumers = num_prosumers
        number_points = 48*12


        self.house_load_mean = []
        self.curve_house_load_mean = deque(maxlen = number_points)

        self.house_load_max = []
        self.curve_house_load_max = deque(maxlen = number_points)

        self.house_load_min = []
        self.curve_house_load_min = deque(maxlen = number_points)

        self.temp_mean = []
        self.curve_temp_mean = deque(maxlen = number_points)

        self.temp_max = []
        self.curve_temp_max = deque(maxlen = number_points)

        self.temp_min = []
        self.curve_temp_min = deque(maxlen = number_points)

        self.basepoint_mean = []
        self.curve_basepoint_mean = deque(maxlen = number_points)

        self.setpoint_mean = []
        self.curve_setpoint_mean = deque(maxlen = number_points)

        self.hvac_load_mean = []
        self.curve_hvac_load_mean = deque(maxlen = number_points)

        self.hvac_load_max = []
        self.curve_hvac_load_max = deque(maxlen = number_points)

        self.hvac_load_min = []
        self.curve_hvac_load_min = deque(maxlen = number_points)

        self.house_unres_mean = []
        self.curve_house_unres_mean = deque(maxlen = number_points)

        self.house_unres_max = []
        self.curve_house_unres_max = deque(maxlen = number_points)

        self.house_unres_min = []
        self.curve_house_unres_min = deque(maxlen = number_points)

        self.system_hvac_load = []
        self.system_house_load = []
        self.system_house_unres = []
        self.system_PV = []
        self.house_PV_mean = []
        self.house_PV_max = []
        self.house_PV_min = []

        self.hvac_on_ratio = []
        self.curve_hvac_on_ratio = deque(maxlen = number_points)

        self.seller_ratio = []
        self.curve_seller_ratio = deque(maxlen = number_points)

        self.buyer_ratio = []
        self.curve_buyer_ratio = deque(maxlen = number_points)

        self.nontcp_ratio = []
        self.curve_nontcp_ratio = deque(maxlen = number_points)

        self.cleared_price = []
        self.curve_cleared_price = deque(maxlen = number_points)

        self.distri_load_p = []
        self.curve_distri_load_p = deque(maxlen = number_points)

        self.distri_load_q = []
        self.curve_distri_load_q = deque(maxlen = number_points)

        self.vpp_load_p = []
        self.curve_vpp_load_p = deque(maxlen = number_points)

        self.vpp_load_q = []
        self.curve_vpp_load_q = deque(maxlen = number_points)

        self.cleared_price = []
        self.curve_cleared_price = deque(maxlen = number_points)

        self.buyer_ratio = []
        self.curve_buyer_ratio = deque(maxlen = number_points)

        self.seller_ratio = []
        self.curve_seller_ratio = deque(maxlen = number_points)

        self.nontcp_ratio = []
        self.curve_nontcp_ratio = deque(maxlen = number_points)

        self.LMP = []

        self.time_hour_curve = deque(maxlen = number_points)
        self.time_hour_system = []
        self.time_hour_auction = []


    def save_statistics(self, path):
        data_dict = {}
        data_dict['time_hour_auction'] = self.time_hour_auction
        data_dict['buyer_ratio'] = self.buyer_ratio
        data_dict['seller_ratio'] = self.seller_ratio
        data_dict['nontcp_ratio'] = self.nontcp_ratio
        data_dict['cleared_price'] = self.cleared_price
        data_dict['LMP'] = self.LMP

        data_dict['time_hour_system'] = self.time_hour_system
        data_dict['temp_mean'] = self.temp_mean
        data_dict['temp_max'] = self.temp_max
        data_dict['temp_min'] = self.temp_min
        data_dict['basepoint_mean'] = self.basepoint_mean
        data_dict['setpoint_mean'] = self.setpoint_mean

        data_dict['hvac_load_mean'] = self.hvac_load_mean
        data_dict['hvac_load_max'] = self.hvac_load_max
        data_dict['hvac_load_min'] = self.hvac_load_min
        data_dict['system_hvac_load'] = self.system_hvac_load
        data_dict['house_load_mean'] = self.house_load_mean
        data_dict['house_load_max'] = self.house_load_max
        data_dict['house_load_min'] = self.house_load_min
        data_dict['system_house_load'] = self.system_house_load
        data_dict['house_unres_mean'] = self.house_unres_mean
        data_dict['house_unres_max'] = self.house_unres_max
        data_dict['house_unres_min'] = self.house_unres_min
        data_dict['system_house_unres'] = self.system_house_unres

        data_dict['system_PV'] = self.system_PV
        data_dict['house_PV_mean'] = self.house_PV_mean
        data_dict['house_PV_max'] = self.house_PV_max
        data_dict['house_PV_min'] = self.house_PV_min

        data_dict['hvac_on_ratio'] = self.hvac_on_ratio

        data_dict['distri_load_p'] = self.distri_load_p
        data_dict['distri_load_q'] = self.distri_load_q

        data_dict['vpp_load_p'] = self.vpp_load_p
        data_dict['vpp_load_q'] = self.vpp_load_q

        with open(path+'data.pkl', 'wb') as f:
            pickle.dump(data_dict, f)



    def record_auction_statistics(self, seconds, houseObjs, aucObj):
        self.time_hour_auction.append(seconds/3600)

        self.buyer_ratio.append(aucObj.num_buyers/len(houseObjs))
        self.seller_ratio.append(aucObj.num_sellers/len(houseObjs))
        self.nontcp_ratio.append(aucObj.num_nontcp/len(houseObjs))

        self.cleared_price.append(aucObj.clearing_price)
        self.LMP.append(aucObj.lmp)


    def record_state_statistics(self, seconds, houseObjs, aucObj, vpp):

        self.time_hour_system.append(seconds/3600)

        # temperature related
        temp_list = []
        base_temp_list = []
        set_temp_list = []
        num_hvac_on = 0
        hvac_load_list = []
        house_load_list = []
        house_unres_list = []
        pv_power_list = []
        battery_power_list = []
        battery_soc_list = []

        for key, house in houseObjs.items():

            # temperature related data ============
            # house temperature
            temp_list.append(house.air_temp)
            # base-point
            base_temp_list.append(house.hvac.basepoint)
            # set-point
            set_temp_list.append(house.hvac.basepoint + house.hvac.offset)

            # power related data ============
            hvac_load_list.append(house.hvac_kw)
            house_load_list.append(house.house_kw)
            house_unres_list.append(house.unres_kw)
            pv_power_list.append(house.solar_kw)
            battery_power_list.append(house.battery_kw)
            battery_soc_list.append(house.battery_SoC)

            # hvac on ratio ===============
            if house.hvac_on:
                num_hvac_on += 1


        self.temp_mean.append(sum(temp_list)/len(temp_list)) # mean temperature
        self.temp_max.append(max(temp_list)) # max temperature
        self.temp_min.append(min(temp_list)) # min temperature
        self.basepoint_mean.append(sum(base_temp_list)/len(base_temp_list)) # mean basepoint
        self.setpoint_mean.append(sum(set_temp_list)/len(set_temp_list))    # mean setpoint

        self.system_hvac_load.append(sum(hvac_load_list))
        self.hvac_load_mean.append(sum(hvac_load_list)/len(hvac_load_list))
        self.hvac_load_max.append(max(hvac_load_list))
        self.hvac_load_min.append(min(hvac_load_list))

        self.system_house_load.append(sum(house_load_list))
        self.house_load_mean.append(sum(house_load_list)/len(house_load_list))
        self.house_load_max.append(max(house_load_list))
        self.house_load_min.append(min(house_load_list))

        self.system_PV.append(sum(pv_power_list))
        self.house_PV_mean.append(sum(pv_power_list)/len(pv_power_list))
        self.house_PV_max.append(max(pv_power_list))
        self.house_PV_min.append(min(pv_power_list))

        self.system_house_unres.append(sum(house_unres_list))
        self.house_unres_mean.append(sum(house_unres_list)/len(house_unres_list))
        self.house_unres_max.append(max(house_unres_list))
        self.house_unres_min.append(min(house_unres_list))


        self.hvac_on_ratio.append(num_hvac_on/len(houseObjs))

        self.distri_load_p.append(aucObj.refload_p)
        self.distri_load_q.append(aucObj.refload_q)

        self.vpp_load_p.append(vpp.vpp_load_p)
        self.vpp_load_q.append(vpp.vpp_load_q)


    def update_curves(self, seconds):
        self.time_hour_curve.append(seconds/3600)

        # for system statistics
        self.curve_temp_mean.append(self.temp_mean[-1])
        self.curve_temp_max.append(self.temp_max[-1])
        self.curve_temp_min.append(self.temp_min[-1])
        self.curve_basepoint_mean.append(self.basepoint_mean[-1])
        self.curve_setpoint_mean.append(self.setpoint_mean[-1])

        self.curve_hvac_load_mean.append(self.hvac_load_mean[-1])
        self.curve_hvac_load_max.append(self.hvac_load_max[-1])
        self.curve_hvac_load_min.append(self.hvac_load_min[-1])
        self.curve_house_load_mean.append(self.house_load_mean[-1])
        self.curve_house_load_max.append(self.house_load_max[-1])
        self.curve_house_load_min.append(self.house_load_min[-1])

        self.curve_distri_load_p.append(self.distri_load_p[-1])
        self.curve_vpp_load_p.append(self.vpp_load_p[-1])

        self.curve_hvac_on_ratio.append(self.hvac_on_ratio[-1])

        self.curve_buyer_ratio.append(self.buyer_ratio[-1])
        self.curve_seller_ratio.append(self.seller_ratio[-1])
        self.curve_nontcp_ratio.append(self.nontcp_ratio[-1])


        self.curve_cleared_price.append(self.cleared_price[-1])

        # for auction statistics



        # self.add_time_hour_point(seconds)
        # self.add_temp_point(houseObjs)
        # self.add_hvac_load_point(houseObjs)
        # self.add_hvac_on_point(houseObjs)
        # self.add_house_load_point(houseObjs)
        # self.add_distribution_load_point(aucObj)
        # self.add_cleared_price_point(aucObj)




