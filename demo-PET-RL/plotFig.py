import pickle
import numpy as np
import json
import matplotlib.pyplot as plt

path_base = './fed_substation/data/'
exp1 = 'exp(RL-test)'
path = path_base + exp1 +'/'
with open(path+'data.pkl', 'rb') as f:
    data_dict = pickle.load(f)

with open(path+'house_TE_ChallengeH_metrics.json', encoding='utf-8') as f:
    prosumer_dict = json.loads(f.read()) # federate_config is the dict data structure
    f.close()

with open(path+'auction_TE_ChallengeH_metrics.json', encoding='utf-8') as f:
    auction_dict = json.loads(f.read()) # federate_config is the dict data structure
    f.close()


time_hour_auction = data_dict['time_hour_auction']
buyer_ratio = data_dict['buyer_ratio']
seller_ratio = data_dict['seller_ratio']
nontcp_ratio = data_dict['nontcp_ratio']
cleared_price = data_dict['cleared_price']
LMP = data_dict['LMP']

time_hour_system = data_dict['time_hour_system']
temp_mean = data_dict['temp_mean']
temp_max = data_dict['temp_max']
temp_min = data_dict['temp_min']
basepoint_mean = data_dict['basepoint_mean']
setpoint_mean = data_dict['setpoint_mean']

system_hvac_load = data_dict['system_hvac_load']
hvac_load_mean = data_dict['hvac_load_mean']
hvac_load_max = data_dict['hvac_load_max']
hvac_load_min = data_dict['hvac_load_min']
system_house_load = data_dict['system_house_load']
house_load_mean = data_dict['house_load_mean']
house_load_max = data_dict['house_load_max']
house_load_min = data_dict['house_load_min']
system_house_unres = data_dict['system_house_unres']
house_unres_mean = data_dict['house_unres_mean']
house_unres_max = data_dict['house_unres_max']
house_unres_min = data_dict['house_unres_min']

system_PV = data_dict['system_PV']
house_PV_mean = data_dict['house_PV_mean']
house_PV_max = data_dict['house_PV_max']
house_PV_min = data_dict['house_PV_min']

hvac_on_ratio = data_dict['hvac_on_ratio']

distri_load_p = data_dict['distri_load_p']
# distri_load_q = data_dict['distri_load_q']

vpp_load_p = data_dict['vpp_load_p']
vpp_load_q = data_dict['vpp_load_q']


house = 'F0_house_A6'
bids = []
prices = []
roles = []
quantitys = []
for i in range(len(time_hour_auction)):
    t = int((i+1)*300)
    bid = prosumer_dict[str(t)][house] # bid_price, quantity, hvac.power_needed, role
    price = bid[0]
    quantity = bid[1]
    role = bid[3]
    if role == 'seller':
        quantitys.append(int(-quantity/3))
        roles.append(-1)
    elif role == 'buyer':
        quantitys.append(int(quantity/3))
        roles.append(1)
    else:
        quantitys.append(0)
        roles.append(0)
    prices.append(price)


fig2, (ax11, ax12, ax13) = plt.subplots(3)
ax11.set_ylabel('Role', size = 13)
ax11.tick_params(axis='x', labelsize=13)
ax11.tick_params(axis='y', labelsize=13)
ax11.set_yticks((-1, 0, 1))
ax11.set_yticklabels(("seller", "none-\nptcpt","buyer"))
ax11.plot(time_hour_auction, roles, 's--', color = 'k', linewidth = 1)

ax12.set_ylabel('Bid-Quantity \n(packet)', size = 13)
ax12.tick_params(axis='x', labelsize=13)
ax12.tick_params(axis='y', labelsize=13)
ax12.plot(time_hour_auction, quantitys, 's--', color = 'k', linewidth = 1)

ax13.set_ylabel('Bid-Price \n($/kWh)', size = 13)
ax13.set_xlabel("Time (h)", size = 13)
ax13.tick_params(axis='x', labelsize=13)
ax13.tick_params(axis='y', labelsize=13)
ax13.plot(time_hour_auction, prices,  color = 'k', linewidth = 1.5)
ax13.plot(time_hour_auction, cleared_price, color = 'g', linewidth = 1.5)
ax13.legend(['bid price', 'cleared price'])


# plt.figure(1)
# time = time_hour_auction
# plt.plot(time, quantitys , 's-')
# plt.xlabel('Time (h)')
# plt.ylabel('Bid-Quantity (1 packet)')
#
# plt.figure(2)
# time = time_hour_auction
# plt.plot(time, prices , '*-')
# plt.xlabel('Time (h)')
# plt.ylabel('Bid-Price ($/kWh)')
# # plt.legend()




fig, (ax1, ax2, ax3, ax4) = plt.subplots(4)
ax1.set_ylabel('Power (kW)', size = 13)
ax1.tick_params(axis='x', labelsize=13)
ax1.tick_params(axis='y', labelsize=13)
ax1.plot(time_hour_system, system_PV, color = 'g', linewidth = 1.5)
ax1.plot(time_hour_system, system_house_load, color = 'b', linewidth = 1.5)
ax1.plot(time_hour_system, vpp_load_p, color = 'k', linewidth = 2)
# ax1.plot(time_hour_system, system_hvac_load)
# ax1.plot(time_hour_system, system_house_unres)
ax1.legend(['total PV generation', 'total house load', 'grid power flow'])#, 'total HVAC load', 'total base load'])

ax2.set_ylabel('Temperature \n(degF)', size = 13)
ax2.tick_params(axis='x', labelsize=13)
ax2.tick_params(axis='y', labelsize=13)
ax2.plot(time_hour_system, basepoint_mean,  '--', color = 'k', linewidth = 1.5)
ax2.plot(time_hour_system, temp_max, color = 'g', linewidth = 1)
ax2.plot(time_hour_system, temp_min, color = 'm', linewidth = 1)
ax2.plot(time_hour_system, temp_mean, color = 'b', linewidth = 1.5)
ax2.legend(['set-point', 'max', 'min', 'mean'])

ax3.set_ylabel('Cleared Price \n($/kWh)', size = 13)
ax3.tick_params(axis='x', labelsize=13)
ax3.tick_params(axis='y', labelsize=13)
ax3.plot(time_hour_auction, LMP, color = 'g', linewidth = 1.5)
ax3.plot(time_hour_auction, cleared_price, color = 'b', linewidth = 1.5)
ax3.legend(['local marginal price', 'cleared price'])

ax4.set_ylabel('Ratio', size = 13)
ax4.set_xlabel("Time (h)", size = 13)
ax4.tick_params(axis='x', labelsize=13)
ax4.tick_params(axis='y', labelsize=13)
ax4.plot(time_hour_system, hvac_on_ratio, color = 'k', linewidth = 1.5)
ax4.plot(time_hour_auction, buyer_ratio, color = 'b', linewidth = 1.5)
ax4.plot(time_hour_auction, seller_ratio, color = 'g', linewidth = 1.5)
ax4.plot(time_hour_auction, nontcp_ratio, color = 'm', linewidth = 1.5)

ax4.legend(['HVAC ON', 'buyer', 'seller', 'none-ptcp'])






# # system load, PV, house load
# plt.figure(1)
# time = time_hour_system
# plt.plot(time, vpp_load_p , label = "grid consumption")
# plt.plot(time, system_PV , label = "total PV generation")
# plt.plot(time, system_house_load , label = "total house load")
# plt.plot(time, system_hvac_load , label = "total HVAC load")
# plt.plot(time, system_house_unres , label = "total base load")
# plt.xlabel('Time (h)')
# plt.ylabel('Power (kW)')
# plt.legend()
#
#
# # temperate
# plt.figure(2)
# time = time_hour_system
# plt.plot(time, setpoint_mean , label = "average set-point")
# plt.plot(time, temp_max , label = "maximum")
# plt.plot(time, temp_min , label = "minimum")
# plt.plot(time, temp_mean , label = "mean")
# plt.xlabel('Time (h)')
# plt.ylabel('House Temperature (degF)')
# plt.legend()
#
# # cleared price
# plt.figure(3)
# time = time_hour_auction
# plt.plot(time, cleared_price )
# plt.xlabel('Time (h)')
# plt.ylabel('Price ($/kWh)')
#
# # ratio
# plt.figure(4)
# plt.plot(time_hour_auction, buyer_ratio, label = 'buyer ratio')
# plt.plot(time_hour_auction, seller_ratio, label = 'seller ratio')
# plt.plot(time_hour_auction, nontcp_ratio, label = 'none-participant ratio')
# plt.plot(time_hour_system, hvac_on_ratio, label = 'HVAC ON ratio')
# plt.xlabel('Time (h)', size = 14)
# plt.ylabel('Ratio', size = 14)
# plt.legend()

#############################################################################333




plt.show()
