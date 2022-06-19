import pickle
import numpy as np
import json
import matplotlib.pyplot as plt

path_base = './fed_substation/data/'
exp1 = 'exp(PEM-exit-200-db)'
exp2 = 'exp(PEM-noexit-200-db)'
exp3 = 'exp(noPEM-db)'

path = path_base + exp1 +'/'
with open(path+'data.pkl', 'rb') as f:
    data_dict = pickle.load(f)

path = path_base + exp2 +'/'
with open(path+'data.pkl', 'rb') as f:
    data_dict2 = pickle.load(f)

path = path_base + exp3 +'/'
with open(path+'data.pkl', 'rb') as f:
    data_dict3 = pickle.load(f)


def smooth(x, box_pts):
    list = []
    out = []
    for i in range(len(x)):
        list.append(x[i])
        out.append(np.mean(list[-box_pts:]))
    return out

def smoothSum(x, box_pts):
    list = []
    out = []
    for i in range(len(x)):
        list.append(x[i])
        out.append(np.sum(list[-box_pts:]))
    out = smooth(out, box_pts)
    return out

time_hour = data_dict['time_hour']
house_load_mean = data_dict['house_load_mean']
house_load_max = data_dict['house_load_max']
house_load_min = data_dict['house_load_min']
temp_mean = data_dict['temp_mean']
temp_max = data_dict['temp_max']
temp_min = data_dict['temp_min']
temp_basepoint_mean = data_dict['temp_basepoint_mean']
havc_load_mean = data_dict['havc_load_mean']
havc_load_max = data_dict['havc_load_max']
havc_load_min = data_dict['havc_load_min']
probability_mean = data_dict['probability_mean']
on_ratio = data_dict['on_ratio']
distri_load_p = data_dict['distri_load_p']
distri_load_q = data_dict['distri_load_q']
vpp_load_p = data_dict['vpp_load_p']
vpp_load_q = data_dict['vpp_load_q']
cleared_price = data_dict['cleared_price']
lmp = data_dict['lmp']
balancing_signal = data_dict['balancing_signal']
request_ratio = data_dict['request_ratio']
accepted_ratio = data_dict['accepted_ratio']

time_hour2 = data_dict2['time_hour']
house_load_mean2 = data_dict2['house_load_mean']
house_load_max2 = data_dict2['house_load_max']
house_load_min2 = data_dict2['house_load_min']
temp_mean2 = data_dict2['temp_mean']
temp_max2 = data_dict2['temp_max']
temp_min2 = data_dict2['temp_min']
temp_basepoint_mean2 = data_dict2['temp_basepoint_mean']
havc_load_mean2 = data_dict2['havc_load_mean']
havc_load_max2 = data_dict2['havc_load_max']
havc_load_min2 = data_dict2['havc_load_min']
probability_mean2 = data_dict2['probability_mean']
on_ratio2 = data_dict2['on_ratio']
distri_load_p2 = data_dict2['distri_load_p']
distri_load_q2 = data_dict2['distri_load_q']
vpp_load_p2 = data_dict2['vpp_load_p']
vpp_load_q2 = data_dict2['vpp_load_q']
cleared_price2 = data_dict2['cleared_price']
lmp2 = data_dict2['lmp']
balancing_signal2 = data_dict2['balancing_signal']
request_ratio2 = data_dict2['request_ratio']
accepted_ratio2 = data_dict2['accepted_ratio']


time_hour3 = data_dict3['time_hour']
house_load_mean3 = data_dict3['house_load_mean']
house_load_max3 = data_dict3['house_load_max']
house_load_min3 = data_dict3['house_load_min']
temp_mean3 = data_dict3['temp_mean']
temp_max3 = data_dict3['temp_max']
temp_min3 = data_dict3['temp_min']
temp_basepoint_mean3 = data_dict3['temp_basepoint_mean']
havc_load_mean3 = data_dict3['havc_load_mean']
havc_load_max3 = data_dict3['havc_load_max']
havc_load_min3 = data_dict3['havc_load_min']
probability_mean3 = data_dict3['probability_mean']
on_ratio3 = data_dict3['on_ratio']
distri_load_p3 = data_dict3['distri_load_p']
distri_load_q3 = data_dict3['distri_load_q']
vpp_load_p3 = data_dict3['vpp_load_p']
vpp_load_q3 = data_dict3['vpp_load_q']
cleared_price32 = data_dict3['cleared_price']
lmp3 = data_dict3['lmp']
balancing_signal3 = data_dict3['balancing_signal']
request_ratio3 = data_dict3['request_ratio']
accepted_ratio3 = data_dict3['accepted_ratio']



fig, (ax1, ax2, ax3) = plt.subplots(3)
ax1.set_ylabel('Power (kW)', size = 13)
ax1.tick_params(axis='x', labelsize=13)
ax1.tick_params(axis='y', labelsize=13)
ax1.plot(time_hour, balancing_signal, '--', color = 'k', linewidth = 1)
ax1.plot(time_hour, smooth(vpp_load_p,100), color = 'b', linewidth = 2)
ax1.plot(time_hour, smooth(vpp_load_p2,100), color = 'g', linewidth = 2)
ax1.plot(time_hour, smooth(vpp_load_p3,100), color = 'm', linewidth = 2)
ax1.legend(['balancing signal', 'grid consumption\n(PEM with exit-mode)', 'grid consumption\n(PEM without exit-mode)', 'grid consumption\n(no PEM)'])#, 'total HVAC load', 'total base load'])

ax2.set_ylabel('Temperature \n(degF)', size = 13)
ax2.tick_params(axis='x', labelsize=13)
ax2.tick_params(axis='y', labelsize=13)
ax2.plot(time_hour, temp_basepoint_mean,  '--', color = 'k', linewidth = 1)
ax2.plot(time_hour, temp_mean, color = 'b', linewidth = 2)
ax2.plot(time_hour, temp_mean2, color = 'g', linewidth = 2)
ax2.plot(time_hour, temp_mean3, color = 'm', linewidth = 2)
ax2.legend(['set-point', 'mean (PEM with exit-mode)', 'mean (PEM without exit-mode)', 'mean (no PEM)'])


ax3.set_ylabel('Ratio', size = 13)
ax3.set_xlabel("Time (h)", size = 13)
ax3.tick_params(axis='x', labelsize=13)
ax3.tick_params(axis='y', labelsize=13)
ax3.plot(time_hour, smooth(request_ratio,100), color = 'b', linewidth = 2)
ax3.plot(time_hour, smooth(accepted_ratio,100), color = 'g', linewidth = 2)
ax3.plot(time_hour, smooth(request_ratio2,100), color = 'm', linewidth = 2)
ax3.plot(time_hour, smooth(accepted_ratio2,100), color = 'k', linewidth = 2)
ax3.legend(['request\n(PEM with exit-mode)', 'accepted\n(PEM with exit-mode)', 'request\n(PEM without exit-mode)', 'accepted\n(PEM without exit-mode)'])



plt.show()
