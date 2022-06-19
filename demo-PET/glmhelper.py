import os
import csv
import json
import numpy as np
import math
import random
from scipy import interpolate
from texthelper import replace_line_in_text, replaceInPattern


helics_msg_code = "\n\
module connection;\n\
object helics_msg {\n\
  configure TE_Challenge_HELICS_gld_msg.json;\n\
}\n"

# base code for a vpp infrastructure including a overhead line, meter for a vpp,
# center tap transformers for three phases, triple lines and triple meters for three phases
line_to_tripmeter_code = ""

house_code = ""

PV_code = ""

batt_code = ""


class GLM_HELPER:

    """
    A class used to define the functions for generating .glm for Gridlab-d federate.
    ...
    Attributes
    ----------

    Methods
    -------
    configure_minimum_timestep()
        Configure simulation timestep for .glm file
    configure_houses()
        Add houses objects in .glm file
    configure_PV()
        Add PV objects in .glm file
    configure_Bat()
        Add battery objects in .glm file
    configure_helics_msg()
        Add helics module in .glm file


    """

    def __init__(self, config):
        """
        Parameters
        ----------
        config: class object
            The GLM_Configuration class object which contains the configurations for
            .glm file of the GridLAB-D federate
        """
        self.file_name_np = "TE_Challenge.glm"  # the file name of the .glm file without path added
        self.file_name = "./fed_gridlabd/" + self.file_name_np
        os.system("cp ./fed_gridlabd/glm-template/template.glm "+self.file_name+"") # copy a standard .glm file

        # get configured time step configuration
        self.minimum_timestep = config.minimum_timestep
        self.helics_connected = config.helics_connected

        self.num_VPPs = config.num_VPPs # number of VPPs, each VPP manages a number of houses
        self.VPP_phase_list = config.VPP_phase_list
        self.num_house_phase_list = config.num_house_phase_list # number of houses of each phase for each VPP
        self.num_house_list = config.num_house_list # number of houses for each VPP
        self.ratio_PV_only_list = config.ratio_PV_only_list # ratio of houses that have only PV installed for each VPP
        self.ratio_Bat_only_list = config.ratio_Bat_only_list# ratio of houses that have only battery installed for each VPP
        self.ratio_PV_Bat_list = config.ratio_PV_Bat_list # ratio oh houses that have both PV and battery installed for each VP
        self.ratio_PV_generation_list = config.ratio_PV_generation_list # PV generation ratio for each VPP
        self.battery_mode = config.battery_mode


        global line_to_tripmeter_code
        with open('./fed_gridlabd/glm-template/line_to_tripmeter_template', 'r') as f:
            line_to_tripmeter_code = f.read()
        global house_code
        with open('./fed_gridlabd/glm-template/house_template', 'r') as f:
            house_code = f.read()
        global PV_code
        with open('./fed_gridlabd/glm-template/pv_template', 'r') as f:
            PV_code = f.read()
        global batt_code
        with open('./fed_gridlabd/glm-template/battery_template', 'r') as f:
            batt_code = f.read()
        with open('./fed_gridlabd/glm-template/objects.json', encoding='utf-8') as f:
            object_dict = json.loads(f.read()) # federate_config is the dict data structure
            f.close()
        global  template_houses_list
        template_houses_list = object_dict['houses_list']




        pass




    def configure_minimum_timestep(self):
        """configure the minimum time step for .glm file
        """
        replaceInPattern(self.file_name, "{minimum_timestep}", str(self.minimum_timestep))


    def configure_helics_msg(self):
        """configure helics msg module in .glm file
        """

        code_text = ""
        hm_code = helics_msg_code
        code_text += hm_code

        # write codes to the .glm file
        with open (self.file_name, 'a+' ) as f:
            f.write(code_text)

    def configure_vpp_infrastructure(self):

        code_text = ""

        for i in range(self.num_VPPs):
            phase = self.VPP_phase_list[i]
            ltt_code = line_to_tripmeter_code
            ltt_code = ltt_code.replace("{vpp_idx}", str(i))
            ltt_code = ltt_code.replace("{phase}", phase)
            code_text += ltt_code

        # write codes to the .glm file
        with open (self.file_name, 'a+' ) as f:
            f.write(code_text)


    def configure_houses(self):

        code_text = ""

        for vpp_idx in range(self.num_VPPs):
            num_houses_phase = self.num_house_phase_list[vpp_idx]
            phase = self.VPP_phase_list[vpp_idx]
            # for phase in "ABC":
            count_pv_only = self.ratio_PV_only_list[vpp_idx]*self.num_house_phase_list[vpp_idx]
            count_bat_only = self.ratio_Bat_only_list[vpp_idx]*self.num_house_phase_list[vpp_idx]
            count_pv_bat = self.ratio_PV_Bat_list[vpp_idx]*self.num_house_phase_list[vpp_idx]
            for house_idx in range(num_houses_phase):
                h_code = house_code
                h_code = h_code.replace("{vpp_idx}", str(vpp_idx))
                h_code = h_code.replace("{phase}", phase)
                h_code = h_code.replace("{house_idx}", str(house_idx))
                h_par_dict = self.get_house_parameters(vpp_idx, phase, house_idx)
                h_code = h_code.replace("{skew}", str(h_par_dict['skew']))
                h_code = h_code.replace("{Rroof}", str(h_par_dict['Rroof']))
                h_code = h_code.replace("{Rwall}", str(h_par_dict['Rwall']))
                h_code = h_code.replace("{Rfloor}", str(h_par_dict['Rfloor']))
                h_code = h_code.replace("{Rdoors}", str(h_par_dict['Rdoors']))
                h_code = h_code.replace("{Rwindows}", str(h_par_dict['Rwindows']))
                h_code = h_code.replace("{airchange_per_hour}", str(h_par_dict['airchange_per_hour']))
                h_code = h_code.replace("{total_thermal_mass_per_floor_area}", str(h_par_dict['total_thermal_mass_per_floor_area']))
                h_code = h_code.replace("{cooling_COP}", str(h_par_dict['cooling_COP']))
                h_code = h_code.replace("{floor_area}", str(h_par_dict['floor_area']))
                h_code = h_code.replace("{number_of_doors}", str(h_par_dict['number_of_doors']))
                h_code = h_code.replace("{air_temperature}", str(h_par_dict['air_temperature']))
                h_code = h_code.replace("{mass_temperature}", str(h_par_dict['mass_temperature']))
                h_code = h_code.replace("{ZIP_code}", str(h_par_dict['ZIP_code']))

                if count_pv_only>0:
                    h_code += self.configure_PV(h_par_dict, vpp_idx, phase, house_idx)
                    count_pv_only -= 1

                elif count_pv_only<=0 and count_bat_only>0:
                    h_code += self.configure_battery(h_par_dict, vpp_idx, phase, house_idx)
                    count_bat_only -= 1

                elif count_pv_only<=0 and count_bat_only<=0 and count_pv_bat>0:
                    h_code += self.configure_PV(h_par_dict, vpp_idx, phase, house_idx)
                    h_code += self.configure_battery(h_par_dict, vpp_idx, phase, house_idx)
                    count_pv_bat -= 1

                code_text += h_code

        # write codes to the .glm file
        with open (self.file_name, 'a+' ) as f:
            f.write(code_text)

    def configure_PV(self, house_par_dict, vpp_idx, phase, house_idx):

        pv_code = PV_code
        pv_code = pv_code.replace("{vpp_idx}", str(vpp_idx))
        pv_code = pv_code.replace("{phase}", phase)
        pv_code = pv_code.replace("{house_idx}", str(house_idx))

        seed = int(vpp_idx*1000+house_idx)
        random.seed(seed)
        # num_pv_panels = max(2, int((house_par_dict['floor_area']/240.3+random.randint(-2,2))*self.ratio_PV_generation_list[vpp_idx]))
        num_pv_panels = int(random.randint(8,20)* self.ratio_PV_generation_list[vpp_idx])
        rated_power_solar = 480*num_pv_panels # W
        pv_code = pv_code.replace("{rated_power_solar}", str(rated_power_solar))
        pv_code = pv_code.replace("{maximum_dc_power}", str(rated_power_solar*0.9))
        pv_code = pv_code.replace("{rated_power_inv}", str(rated_power_solar*0.9))

        return pv_code



    def configure_battery(self, house_par_dict, vpp_idx, phase, house_idx):

        b_code = batt_code
        b_code = b_code.replace("{vpp_idx}", str(vpp_idx))
        b_code = b_code.replace("{phase}", phase)
        b_code = b_code.replace("{house_idx}", str(house_idx))

        seed = int(vpp_idx*1000+house_idx)

        battery_capacity = 100 # 10 kWh
        random.seed(seed)
        state_of_charge = 0.5 #round(random.uniform(0.4,0.6),2)

        b_code = b_code.replace("{battery_capacity}", str(battery_capacity))
        b_code = b_code.replace("{state_of_charge}", str(state_of_charge))
        b_code = b_code.replace("{battery_mode}", self.battery_mode)


        return b_code

    def get_house_parameters(self, vpp_idx, phase, house_idx):

        dict = {}
        if phase == 'A':
            phase_num = 0
        elif phase == 'B':
            phase_num = 1
        else:
            phase_num = 2

        seed = int(vpp_idx*1000 + phase_num*300 + house_idx*10) # initial seed

        # select a template house from template_houses_list of TESP's TE30 example
        random.seed(seed)
        template_idx = random.randint(0,len(template_houses_list)-1)
        seed+=1
        template_house = template_houses_list[template_idx]

        # change parameters based this template
        random.seed(seed)
        dict['skew'] = int(template_house['attributes']['schedule_skew']) + random.randint(-10,10)
        seed+=1
        random.seed(seed)
        dict['Rroof'] = float(template_house['attributes']['Rroof']) + round(random.uniform(-1,1),2)
        seed+=1
        random.seed(seed)
        dict['Rwall'] = float(template_house['attributes']['Rwall']) + round(random.uniform(-1,1),2)
        seed+=1
        random.seed(seed)
        dict['Rfloor'] = float(template_house['attributes']['Rfloor']) + round(random.uniform(-1,1),2)
        seed+=1
        random.seed(seed)
        dict['Rdoors'] = int(template_house['attributes']['Rdoors'])
        seed+=1
        random.seed(seed)
        dict['Rwindows'] = float(template_house['attributes']['Rwindows']) + round(random.uniform(-0.1,0.1),2)
        seed+=1
        random.seed(seed)
        dict['airchange_per_hour'] = float(template_house['attributes']['airchange_per_hour']) + round(random.uniform(-0.1,0.1),2)
        seed+=1
        random.seed(seed)
        dict['total_thermal_mass_per_floor_area'] = float(template_house['attributes']['total_thermal_mass_per_floor_area']) + round(random.uniform(-0.2,0.2),2)
        seed+=1
        random.seed(seed)
        dict['cooling_COP'] = float(template_house['attributes']['cooling_COP']) + round(random.uniform(-0.1,0.1),2)
        seed+=1
        random.seed(seed)
        dict['floor_area'] = float(template_house['attributes']['floor_area']) + round(random.uniform(-20,20),2)
        seed+=1
        random.seed(seed)
        dict['number_of_doors'] = int(template_house['attributes']['number_of_doors'])
        seed+=1
        random.seed(seed)
        dict['air_temperature'] = float(template_house['attributes']['air_temperature']) + round(random.uniform(-1,1),2)
        seed+=1
        random.seed(seed)
        dict['mass_temperature'] = dict['air_temperature']
        seed+=1

        ZIP_code = ""
        for child in template_house['children']:
            if child['name'] == 'ZIPload':
                ZIP_code += "object ZIPload {\n"
                for attr in child['attributes']:
                    if attr == 'schedule_skew':
                        ZIP_code += '  ' + attr + ' ' + str(dict['skew']) + ';\n'
                    else:
                        ZIP_code += '  ' + attr + ' ' + child['attributes'][attr] + ';\n'
                ZIP_code += '};\n'
        # print(ZIP_code)
        dict['ZIP_code'] = ZIP_code

        # random.seed(seed)
        # dict['ratio_LIGHTS'] = float(template_house['children'][0]['attributes']['base_power'].replace('LIGHTS*','')) + round(random.uniform(-0.1,0.1),2)
        # seed+=1
        #
        # random.seed(seed)
        # dict['ratio_CLOTHESWASHER'] = float(template_house['children'][1]['attributes']['base_power'].replace('CLOTHESWASHER*','')) + round(random.uniform(-0.1,0.1),2)
        # seed+=1
        #
        # random.seed(seed)
        # dict['ratio_REFRIGERATOR'] = float(template_house['children'][2]['attributes']['base_power'].replace('REFRIGERATOR*','')) + round(random.uniform(-0.1,0.1),2)
        # seed+=1
        #
        # random.seed(seed)
        # dict['ratio_DRYER'] = float(template_house['children'][3]['attributes']['base_power'].replace('DRYER*','')) + round(random.uniform(-0.1,0.1),2)
        # seed+=1
        #
        # random.seed(seed)
        # dict['ratio_RANGE'] = float(template_house['children'][4]['attributes']['base_power'].replace('RANGE*','')) + round(random.uniform(-0.1,0.1),2)
        # seed+=1
        #
        # random.seed(seed)
        # dict['ratio_MICROWAVE'] = float(template_house['children'][5]['attributes']['base_power'].replace('MICROWAVE*','')) + round(random.uniform(-0.1,0.1),2)
        # seed+=1
        return  dict


    def generate_glm(self):
        """generate .glm file for GridLAB-D federate
        """

        # 1.1 configure the time step for gridlabd simulation
        self.configure_minimum_timestep()

        # 1.2 configure vpp infrastructure
        self.configure_vpp_infrastructure()

        # 1.3 configure houses
        self.configure_houses()




        if self.helics_connected:
            self.configure_helics_msg()
