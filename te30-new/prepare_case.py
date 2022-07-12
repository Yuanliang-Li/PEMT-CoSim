# file: prepare_case.py
"""
Function:
        generate a co-simulation testbed based on user-defined configurations
last update time: 2021-11-11
modified by Yuanliang Li

"""

import my_tesp_support_api.api as tesp
import os

"""1. configure simulation time period"""
year = 2013
start_time = '2013-07-01 00:00:00'
stop_time  = '2013-07-03 00:00:00'


"""2. configure weather data"""
tmy_file_name = 'AZ-Tucson_International_Ap.tmy3' # choose a .tmy3 file to specify the weather in a specific location
tmy_file_dir = os.getenv('TESP_INSTALL') + '/share/support/weather/'
tmy_file = tmy_file_dir + tmy_file_name
tesp.weathercsv (tmy_file, 'weather.dat', start_time, stop_time, year) # it will output weather.dat in the weather fold as the input of the weather federate

"""3. generate configuration files for gridlabd, substation, pypower, and weather"""
tesp.glm_dict ('TE_Challenge',te30=True)
tesp.prep_substation ('TE_Challenge')

# to run the original E+ model with heating/cooling, copy the following file to Merged.idf
#base_idf = os.getenv('TESP_INSTALL') + '/share/support/energyplus/SchoolDualController.idf'

"""4. genereate configuration files for energyplus"""
base_idf = './fed_energyplus/SchoolBase.idf'
ems_idf = './fed_energyplus/emsSchoolBaseH.idf'
tesp.merge_idf (base_idf, ems_idf, start_time, stop_time, './fed_energyplus/MergedH.idf', 12)

