# file: plot.py
"""
Function:
        visualize all generated data after the co-simulation
last update time: 2021-11-11
modified by Yuanliang Li

"""
import sys
import os
import my_tesp_support_api.process_pypower as pp
import my_tesp_support_api.process_agents as ap
import my_tesp_support_api.process_gld as gp
import my_tesp_support_api.process_houses as hp
import my_tesp_support_api.process_eplus as ep
import my_tesp_support_api.process_inv as ip
import my_tesp_support_api.process_voltages as vp

# rootname = sys.argv[1]

"""1. plot data from pypower federate"""
nameroot = 'TE_ChallengeH'
pypower_dir = './fed_pypower/'
pmetrics = pp.read_pypower_metrics (pypower_dir, nameroot)
pp.plot_pypower (pmetrics)

"""2. plot data from substation federate, including the auction-related data"""
substation_dir = './fed_substation/'
if os.path.exists (substation_dir + 'auction_' + nameroot + '_metrics.json'):
  ametrics = ap.read_agent_metrics (substation_dir, nameroot, 'TE_Challenge_agent_dict.json')
  ap.plot_agents (ametrics)

"""3. plot data from gridlabd federate"""
gridlabd_dir = './fed_gridlabd/'
gmetrics = gp.read_gld_metrics (gridlabd_dir, nameroot, 'TE_Challenge_glm_dict.json')
gp.plot_gld (gmetrics)
hp.plot_houses (gmetrics)
vp.plot_voltages (gmetrics)

"""4. plot data from energyplus federate"""
energyplus_dir = './fed_energyplus/'
emetrics = ep.read_eplus_metrics (energyplus_dir, nameroot)
ep.plot_eplus (emetrics)
