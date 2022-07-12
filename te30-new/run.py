# file: run.py
"""
Function:
        run testbed
last update time: 2021-11-11
modified by Yuanliang Li

"""

import time
import os
import subprocess

"""declare something"""
TESP_INSTALL = os.environ['TESP_INSTALL']
TESP_SUPPORT = TESP_INSTALL+'/share/support'
SCHED_PATH = TESP_SUPPORT+'/schedules'
EPW = TESP_SUPPORT+'/energyplus/USA_AZ_Tucson.Intl.AP.722740_TMY3.epw'


"""run commands by using python subprocess"""
processes_list = [] # list to save all subprocesses for process management
# command to launch helics broker
cmd0 = "helics_broker -f 6 --loglevel=1 --name=mainbroker >helics_broker.log 2>&1"
# command to launch gridlabd federate
cmd1 = "cd ./fed_gridlabd/ && gridlabd -D SCHED_PATH={} -D USE_HELICS -D METRICS_FILE=TE_ChallengeH_metrics.json TE_Challenge.glm >gridlabd.log 2>&1".format(SCHED_PATH)
# command to launch weather federate
cmd2 = "cd ./fed_weather/ && python3 launch_weather.py >weather.log 2>&1"
# command to launch pypower federate
cmd3 = "cd ./fed_pypower/ && python3 launch_pypower.py >pypower.log 2>&1"
# command to launch substation federate
cmd4 = "cd ./fed_substation/ && python3 launch_substation.py >substation.log 2>&1"
# command to launch energyplus federate
cmd5 = "cd ./fed_energyplus/ && export HELICS_CONFIG_FILE=helics_eplus.json && exec energyplus -w {} -d output -r MergedH.idf >eplus.log 2>&1".format(EPW)
# command to launch energyplus agent (it is also a federate)
cmd6 = "cd ./fed_energyplus/ && eplus_agent_helics 172800s 300s SchoolDualController eplus_TE_ChallengeH_metrics.json  0.02 25 4 4 helics_eplus_agent.json >eplus_agent.log 2>&1"

processes_list.append(subprocess.Popen(cmd0, stdout=subprocess.PIPE, shell=True))
processes_list.append(subprocess.Popen(cmd1, stdout=subprocess.PIPE, shell=True))
processes_list.append(subprocess.Popen(cmd2, stdout=subprocess.PIPE, shell=True))
processes_list.append(subprocess.Popen(cmd3, stdout=subprocess.PIPE, shell=True))
processes_list.append(subprocess.Popen(cmd4, stdout=subprocess.PIPE, shell=True))
processes_list.append(subprocess.Popen(cmd5, stdout=subprocess.PIPE, shell=True))
processes_list.append(subprocess.Popen(cmd6, stdout=subprocess.PIPE, shell=True))

