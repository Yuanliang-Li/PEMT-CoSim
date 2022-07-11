import sys
sys.path.append('..')
# this is necessary since running this file is actually opening a new process
# where my_tesp_support_api package is not inside the path list
import my_tesp_support_api.api as tesp


tesp.startWeatherAgent('weather.dat', 'TE_Challenge_HELICS_Weather_Config.json')
