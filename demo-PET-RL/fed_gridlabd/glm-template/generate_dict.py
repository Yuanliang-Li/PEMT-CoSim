"""Generate a gridlabd json file (dict)
Generate a dict file including loads/generators based on a template file.
It is able to scale
"""



import json
import sys
import math
import os
import glm
import matplotlib.pyplot as plt


"""1. load a template file from a existing system"""
data = glm.load("./TE_Challenge(beifeng).glm")
# 1.1 extract house objects
objects_list = data['objects']
houses_list = [obj for obj in objects_list if obj['name']=='house']
houses_dict = {}
for house in houses_list:
  name = house['attributes']['name']
  houses_dict[name] = {}
  houses_dict[name]['attributes'] = house['attributes']
  houses_dict[name]['children'] = house['children']

federate_dict = {'houses_list':houses_list}
json_code = json.dumps(federate_dict,indent = 4)
with open ('objects.json', 'w' ) as f:
    f.write(json_code)

area_list = [float(house['attributes']['floor_area'])  for house in houses_list]
print(max(area_list))
print(min(area_list))















