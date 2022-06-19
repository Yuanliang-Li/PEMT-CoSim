import time
import helics
import os
import sys
import json
import pickle
import psutil
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
        self.gldName = self.agents_dict['GridLABD']
        self.bulkName = 'pypower'
        self.hFed = None # the helics period is 15 seconds
        self.fedName = self.helics_config['name']
        self.is_destroyed = True
        self.pubCount = 0
        self.subCount = 0

        self.vpp_name_list = list(self.agents_dict['VPPs'].keys())
        self.hvac_name_list = list(self.agents_dict['hvacs'].keys()) # list of HVAC name
        self.house_name_list = [self.agents_dict['hvacs'][hvac]['houseName'] for hvac in self.hvac_name_list]
        self.meter_name_list =  [self.agents_dict['hvacs'][hvac]['meterName'] for hvac in self.hvac_name_list]
        self.inverter_name_list = list(self.agents_dict['inverters'].keys())

        self.houseMeters_dict = {}
        for hvac in self.agents_dict['hvacs']:
            name = self.agents_dict['hvacs'][hvac]['meterName']
            self.houseMeters_dict[name] = {}
            self.houseMeters_dict[name]['meter'] = name
            self.houseMeters_dict[name]['house'] = self.agents_dict['hvacs'][hvac]['houseName']
            self.houseMeters_dict[name]['VPP'] = self.agents_dict['hvacs'][hvac]['houseClass']
            self.houseMeters_dict[name]['HVAC'] = hvac
            self.houseMeters_dict[name]['PV'] = None
            self.houseMeters_dict[name]['battery'] = None
        for key, dict in self.agents_dict['inverters'].items():
            billingmeter_id = dict['billingmeter_id']
            resource = dict['resource']
            if billingmeter_id in self.meter_name_list:
                if resource == 'solar':
                    self.houseMeters_dict[billingmeter_id]['PV'] = key
                if resource == 'battery':
                    self.houseMeters_dict[billingmeter_id]['battery'] = key

        # initialize objects for subscriptions and the publications, and save these objects in dictionary
        # for House
        self.subsTemp = {} # subscriptions dict for HVAC temperature
        self.subsVolt = {} # subscriptions dict for house meter measured_voltage_1
        self.subsMtrPower = {} # subscriptions dict for house meter measured_power
        self.subsMtrDemand = {} # subscriptions dict for house meter measured_demand
        self.subsState = {} # subscriptions dict for HVAC power state
        self.subsHVACLoad = {}  # subscriptions dict for HVAC load
        self.pubsMtrMode = {}   # publications dict for billing mode
        self.pubsMtrPrice = {}  # publications dict for price
        self.pubsMtrMonthly = {} # publications dict for monthly_fee
        self.pubsHeatingSetpoint = {}  # publications dict for heating setpoint
        self.pubsCoolingSetpoint = {}  # publications dict for cooling setpoint
        self.pubsDeadband = {} # publications dict for cooling Deadband
        self.pubsThermostatState = {} # publications for thermostat state
        self.subsVPPMtrPower = {} # subscription dict for VPP measured power
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
        self.prosumer_meta = {'bid_price':{'units':'USD','index':0},'bid_quantity':{'units':unit,'index':1}}
        self.load_meta = {}
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

        hvac_name_list = list(self.agents_dict['hvacs'].keys()) # list of HVAC name
        house_name_list = [self.agents_dict['hvacs'][hvac]['houseName'] for hvac in hvac_name_list]
        meter_name_list =  [self.agents_dict['hvacs'][hvac]['meterName'] for hvac in hvac_name_list]
        inverter_name_list = list(self.agents_dict['inverters'].keys())
        vpp_name_list = list(self.agents_dict['VPPs'].keys())
        for i, hvac_name in enumerate(hvac_name_list):
            house_name = house_name_list[i]
            meter_name = meter_name_list[i]
            hseSubTopic = self.gldName + '/' + house_name  # subs from gridlabd
            mtrSubTopic = self.gldName + '/' + meter_name  # subs from meter
            mtrPubTopic = self.fedName + '/' + meter_name # publication for meter
            ctlPubTopic = self.fedName + '/' + hvac_name      # publication for controller

            self.pubsMtrMode[meter_name] = helics.helicsFederateGetPublication (self.hFed, mtrPubTopic + '/bill_mode')
            self.pubsMtrPrice[meter_name] = helics.helicsFederateGetPublication (self.hFed, mtrPubTopic + '/price')
            self.pubsMtrMonthly[meter_name] = helics.helicsFederateGetPublication (self.hFed, mtrPubTopic + '/monthly_fee')
            self.subsVolt[meter_name] = helics.helicsFederateGetSubscription (self.hFed, mtrSubTopic + '#measured_voltage_1')
            self.subsMtrPower[meter_name] = helics.helicsFederateGetSubscription (self.hFed, mtrSubTopic + '#measured_power')
            self.subsMtrDemand[meter_name] = helics.helicsFederateGetSubscription (self.hFed, mtrSubTopic + '#measured_demand')

            self.subsTemp[hvac_name] = helics.helicsFederateGetSubscription (self.hFed, hseSubTopic + '#air_temperature')
            self.subsState[hvac_name] = helics.helicsFederateGetSubscription (self.hFed, hseSubTopic + '#power_state')
            self.subsHVACLoad[hvac_name] = helics.helicsFederateGetSubscription (self.hFed, hseSubTopic + '#hvac_load')
            self.pubsHeatingSetpoint[hvac_name] = helics.helicsFederateGetPublication (self.hFed, ctlPubTopic + '/heating_setpoint')
            self.pubsCoolingSetpoint[hvac_name] = helics.helicsFederateGetPublication (self.hFed, ctlPubTopic + '/cooling_setpoint')
            self.pubsDeadband[hvac_name] = helics.helicsFederateGetPublication (self.hFed, ctlPubTopic + '/thermostat_deadband')
            self.pubsThermostatState[hvac_name] = helics.helicsFederateGetPublication (self.hFed, ctlPubTopic + '/thermostat_mode') # new added by Yuanliang

        for i, vpp_name in enumerate(vpp_name_list):
            vpp_meter_name =  self.agents_dict['VPPs'][vpp_name]['VPP_meter']
            vppSubTopic = self.gldName + '/' + vpp_meter_name
            self.subsVPPMtrPower[vpp_name] = helics.helicsFederateGetSubscription (self.hFed, vppSubTopic + '#measured_power')




    def get_agent_pubssubs(self,key, category):
        # get publications and subscriptions for a specific agent
        agent_subs = {}
        agent_pubs = {}

        if category == 'HVAC':
            agent_subs['subTemp'] = self.subsTemp[key]
            agent_subs['subState'] = self.subsState[key]
            agent_subs['subHVACLoad'] = self.subsHVACLoad[key]
            agent_pubs['pubHeatingSetpoint'] = self.pubsHeatingSetpoint[key]
            agent_pubs['pubCoolingSetpoint'] = self.pubsCoolingSetpoint[key]
            agent_pubs['pubDeadband'] = self.pubsDeadband[key]
            agent_pubs['pubThermostatState'] = self.pubsThermostatState[key]

        if category == "meter":
            agent_subs['subVolt'] = self.subsVolt[key]
            agent_subs['subMtrPower'] = self.subsMtrPower[key]
            agent_subs['subMtrDemand'] = self.subsMtrDemand[key]
            agent_pubs['pubMtrMode'] = self.pubsMtrMode[key]
            agent_pubs['pubMtrPrice'] = self.pubsMtrPrice[key]
            agent_pubs['pubMtrMonthly'] = self.pubsMtrMonthly[key]

        if category == "auction":
            agent_subs['subLMP'] = self.subLMP
            agent_subs['subFeeder'] = self.subFeeder
            agent_pubs['pubAucPrice'] = self.pubAucPrice
            agent_pubs['pubUnresp'] = self.pubUnresp
            agent_pubs['pubMax'] = self.pubMax
            agent_pubs['pubC2'] = self.pubC2
            agent_pubs['pubC1'] = self.pubC1
            agent_pubs['pubDeg'] = self.pubDeg

        if category == "VPP":
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

        # command to launch gridlabd federate
        cmd1 = "cd ../fed_gridlabd/ && gridlabd -D SCHED_PATH={} -D USE_HELICS -D METRICS_FILE=TE_ChallengeH_metrics.json TE_Challenge.glm >gridlabd.log 2>&1".format(SCHED_PATH)
        # command to launch weather federate
        cmd2 = "cd ../fed_weather/ && python3 launch_weather.py >weather.log 2>&1"
        # command to launch pypower federate
        cmd3 = "cd ../fed_pypower/ && python3 launch_pypower.py >pypower.log 2>&1"
        # command to launch energyplus federate
        cmd4 = "cd ../fed_energyplus/ && export HELICS_CONFIG_FILE=helics_eplus.json && exec energyplus -w {} -d output -r MergedH.idf >eplus.log 2>&1".format(EPW)
        # command to launch energyplus agent (it is also a federate)
        cmd5 = "cd ../fed_energyplus/ && eplus_agent_helics 172800s 300s SchoolDualController eplus_TE_ChallengeH_metrics.json  0.02 25 4 4 helics_eplus_agent.json >eplus_agent.log 2>&1"

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
    def __init__(self):
        self.curve_house_load_mean = []
        self.curve_house_load_max = []
        self.curve_house_load_min = []
        self.curve_temp_mean = []
        self.curve_temp_max = []
        self.curve_temp_min = []
        self.curve_temp_basepoint_mean = []
        self.curve_havc_load_mean = []
        self.curve_havc_load_max = []
        self.curve_havc_load_min = []
        self.curve_probability_mean =[]
        self.curve_on_ratio = []
        self.curve_distri_load_p = []
        self.curve_distri_load_q = []
        self.curve_vpp_load_p = []
        self.curve_vpp_load_q = []
        self.curve_cleared_price = []
        self.curve_lmp = []
        self.curve_balancing_signal = []
        self.curve_request_ratio = []
        self.curve_accepted_ratio = []
        self.curve_time_hour = []


        self.house_load_mean = []
        self.house_load_max = []
        self.house_load_min = []
        self.temp_mean = []
        self.temp_max = []
        self.temp_min = []
        self.temp_basepoint_mean = []
        self.havc_load_mean = []
        self.havc_load_max = []
        self.havc_load_min = []
        self.probability_mean =[]
        self.on_ratio = []
        self.distri_load_p = []
        self.distri_load_q = []
        self.vpp_load_p = []
        self.vpp_load_q = []
        self.cleared_price = []
        self.lmp = []
        self.balancing_signal = []
        self.request_ratio = []
        self.accepted_ratio = []
        self.time_hour = []


    def record_data(self, seconds, houseObjs, aucObj, vppObj):
        self.time_hour.append(seconds/3600)

        temp_list = []
        base_temp_list = []
        p_list = []
        hvac_kw_list = []
        house_load_list = []
        num_on = 0

        for key, house in houseObjs.items():
            hvac_kw_list.append(house.hvac.hvac_kw)
            base_temp_list.append(house.hvac.basepoint)
            house_load_list.append(house.mtr_power)
            temp_list.append(house.hvac.air_temp)
            p_list.append(house.hvac.probability)
            if house.hvac.hvac_on:
                num_on += 1


        self.temp_basepoint_mean.append(sum(base_temp_list)/len(base_temp_list))
        self.temp_mean.append(sum(temp_list)/len(temp_list))
        self.temp_max.append(max(temp_list))
        self.temp_min.append(min(temp_list))
        self.havc_load_mean.append(sum(hvac_kw_list)/len(hvac_kw_list))
        self.havc_load_max.append(max(hvac_kw_list))
        self.havc_load_min.append(min(hvac_kw_list))
        self.house_load_mean.append(sum(house_load_list)/len(house_load_list))
        self.house_load_max.append(max(house_load_list))
        self.house_load_min.append(min(house_load_list))

        self.on_ratio.append(num_on/len(houseObjs))
        self.probability_mean.append(sum(p_list)/len(p_list))

        self.vpp_load_p.append(vppObj.vpp_load)
        self.balancing_signal.append(vppObj.balance_signal)
        self.lmp.append(aucObj.lmp)

        self.request_ratio.append(vppObj.request_ratio)
        self.accepted_ratio.append(vppObj.accepted_ratio)


    def save_statistics(self, path):
        data_dict = {}

        data_dict['time_hour'] = self.time_hour
        data_dict['house_load_mean'] = self.house_load_mean
        data_dict['house_load_max'] = self.house_load_max
        data_dict['house_load_min'] = self.house_load_min
        data_dict['temp_mean'] = self.temp_mean
        data_dict['temp_max'] = self.temp_max
        data_dict['temp_min'] = self.temp_min
        data_dict['temp_basepoint_mean'] = self.temp_basepoint_mean
        data_dict['havc_load_mean'] = self.havc_load_mean
        data_dict['havc_load_max'] = self.havc_load_max
        data_dict['havc_load_min'] = self.havc_load_min
        data_dict['probability_mean'] = self.probability_mean
        data_dict['on_ratio'] = self.on_ratio
        data_dict['distri_load_p'] = self.distri_load_p
        data_dict['distri_load_q'] = self.distri_load_q
        data_dict['vpp_load_p'] = self.vpp_load_p
        data_dict['vpp_load_q'] = self.vpp_load_q
        data_dict['cleared_price'] = self.cleared_price
        data_dict['lmp'] = self.lmp
        data_dict['balancing_signal'] = self.balancing_signal
        data_dict['request_ratio'] = self.request_ratio
        data_dict['accepted_ratio'] = self.accepted_ratio


        with open(path + 'data.pkl', 'wb') as f:
            pickle.dump(data_dict, f)



    def update_curves(self, seconds, houseObjs, aucObj, vppObj):
        # the input is the current simulation time with second unit
        # the time added to the curve is with hour unit
        self.curve_time_hour.append(seconds/3600)

        temp_list = []
        base_temp_list = []
        for key, house in houseObjs.items():
            base_temp_list.append(house.hvac.basepoint)
            temp_list.append(house.hvac.air_temp)
        self.curve_temp_mean.append(sum(temp_list)/len(temp_list))
        self.curve_temp_max.append(max(temp_list))
        self.curve_temp_min.append(min(temp_list))
        self.curve_temp_basepoint_mean.append(sum(base_temp_list)/len(base_temp_list))


        p_list = []
        num_on = 0
        for key, house in houseObjs.items():
            p_list.append(house.hvac.probability)
            if house.hvac.hvac_on:
                num_on += 1
        self.curve_on_ratio.append(num_on/len(houseObjs))
        self.curve_probability_mean.append(sum(p_list)/len(p_list))


        load_list = []
        for key, house in houseObjs.items():
            load_list.append(house.hvac.hvac_kw)
        self.curve_havc_load_mean.append(sum(load_list)/len(load_list))
        self.curve_havc_load_max.append(max(load_list))
        self.curve_havc_load_min.append(min(load_list))


        self.curve_distri_load_p.append(aucObj.refload_p)
        self.curve_distri_load_q.append(aucObj.refload_q)

        self.curve_vpp_load_p.append(vppObj.vpp_load)

        self.curve_cleared_price.append(aucObj.clearing_price)
        self.curve_lmp.append(aucObj.lmp)


        load_list = []
        for key, house in houseObjs.items():
            load_list.append(house.mtr_power)
        self.curve_house_load_mean.append(sum(load_list)/len(load_list))
        self.curve_house_load_max.append(max(load_list))
        self.curve_house_load_min.append(min(load_list))

        self.curve_balancing_signal.append(vppObj.balance_signal)
        self.curve_request_ratio.append(vppObj.request_ratio)
        self.curve_accepted_ratio.append(vppObj.accepted_ratio)


