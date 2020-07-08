#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jun 12 11:21:39 2020

@author: doorleyr
"""

from toolbox import Handler, Indicator, CompositeIndicator
from proximity_indicator import ProxIndicator
from innovation_indicator import InnoIndicator
from mobility_indicator import MobilityIndicator
from aggregate_indicator import AggregateIndicator
from economic_indicator import EconomicIndicator
from buildings_indicator import BuildingsIndicator
from diversity_indicator import DiversityIndicator

import urllib
import json
import pandas as pd



folder='../Scenarios/24_Jun_20/'


I = InnoIndicator()    
P = ProxIndicator(name='proximity',   indicator_type_in='numeric', table_name='corktown')
#P_hm = ProxIndicator(name='proximity_heatmap',  indicator_type_in='heatmap', table_name='corktown')
M = MobilityIndicator(name='mobility', table_name='corktown')
B= BuildingsIndicator(name='buildings',  table_name='corktown')
D= DiversityIndicator(name='diversity',  table_name='corktown')

# 2nd order  individual indicators 
E = EconomicIndicator(name='Economic',
                      table_name='corktown')

#H = Handler('corktown', quietly=False)
#
#H.add_indicators([
#        I,
#        P,
##        P_hm,
#        M,
#        E,
#        B,
#        D
#        ])

geogrid=json.load(open('../CS_Grid_Maker/examples/results/corktown_geogrid.geojson'))

types=json.load(open('../CS_Grid_Maker/examples/type_definitions/corktown_types.json'))

static_types=json.load(open('../CS_Grid_Maker/examples/type_definitions/corktown_static_types.json'))

types.update(static_types)

reporting_types=[t for t in types if t not in ['None','Residential Low Density', 'Industrial']]

for ind in [I, P, 
#             P_hm, 
            M, B, D, E]:
    ind.types_def=types
    ind.geogrid_header=geogrid['properties']['header']
    
I.types_def



geogrid_data_base=json.load(open('{}ford_base.json'.format(folder)))
geogrid_data_campus=json.load(open('{}ford_campus.json'.format(folder)))
geogrid_data_housing=json.load(open('{}ford_housing.json'.format(folder)))
geogrid_data_inno_com=json.load(open('{}ford_inno_com.json'.format(folder)))

cell_area=geogrid['properties']['header']['cellSize']**2

updatable=[((feat['properties']['interactive'])or (feat['properties']['static_new'])
           ) for feat in geogrid['features']]
    
    
def get_type_stats(geogrid_data, reporting_types, updatable,cell_area, types_def=types):
    results={}
    for type_name in reporting_types:
        sqm_pp=types_def[type_name]['sqm_pperson']
        floors=0
        for gi, cell in enumerate(geogrid_data):
            if ((updatable[gi]) and (cell['name']==type_name)):
                height=cell['height']
                if isinstance(height, list):
                    height=height[-1]
                floors+=height
        results[type_name]= {'sqm_pp': sqm_pp, 'sqm': floors*cell_area, 
               'capacity':floors*cell_area/sqm_pp }
    return results



def get_all_indicators(geogrid_data, future_mobility):
    all_ind=[]
    print('Mobility')
    all_ind.extend(M.return_indicator(geogrid_data, future_mobility=future_mobility))

    print('Innovation')
    all_ind.extend(I.return_indicator(geogrid_data))

    print('Economic')
    all_ind.extend(E.return_indicator(geogrid_data))

    print('Proximity')
    all_ind.extend(P.return_indicator(geogrid_data))

    print('Diversity')
    all_ind.extend(D.return_indicator(geogrid_data))

    print('Buildings')
    all_ind.extend(B.return_indicator(geogrid_data))
    return all_ind

def create_scenario_row(all_ind, stats, scenario_name):
    all_cols={'Scenario': scenario_name}
    for ind in all_ind:
        all_cols[ind['name']+' norm']=ind['value']
        raw_name=ind['name']+' raw'
        if not ind['units']==None:
            raw_name+= ' ['+ind['units']+']'
        all_cols[raw_name]=ind['raw_value']
    for type_name in stats:
        all_cols[type_name + ' sqm']=stats[type_name]['sqm']
        all_cols[type_name + ' capacity']=stats[type_name]['capacity']
    return all_cols

base_indicators=get_all_indicators(geogrid_data_base, False)
base_stats=get_type_stats(geogrid_data_base, reporting_types, updatable,cell_area)

campus_indicators=get_all_indicators(geogrid_data_campus, False)
campus_stats=get_type_stats(geogrid_data_campus, reporting_types, updatable,cell_area)

campus_mobility_indicators=get_all_indicators(geogrid_data_campus, True)
campus_mobility_stats=campus_stats

housing_indicators=get_all_indicators(geogrid_data_housing, False)
housing_stats=get_type_stats(geogrid_data_housing, reporting_types, updatable,cell_area)

inno_com_indicators=get_all_indicators(geogrid_data_inno_com, True)
inno_com_stats=get_type_stats(geogrid_data_inno_com, reporting_types, updatable,cell_area)

all_scenarios=[]
all_scenarios.append(create_scenario_row(base_indicators, base_stats, scenario_name='BAU'))
all_scenarios.append(create_scenario_row(campus_indicators, campus_stats, scenario_name='Campus Only'))
all_scenarios.append(create_scenario_row(campus_mobility_indicators, campus_mobility_stats, scenario_name='Future Mobility'))
all_scenarios.append(create_scenario_row(housing_indicators, housing_stats, scenario_name='Housing'))
all_scenarios.append(create_scenario_row(inno_com_indicators, inno_com_stats, scenario_name='Innovation Community'))

col_order = ['Scenario']+[col for col in all_scenarios[0] if 'norm' in col]+[
        col for col in all_scenarios[0] if 'raw' in col]
for type_name in reporting_types:
    col_order.append(type_name + ' sqm')
    col_order.append(type_name + ' capacity')

output=pd.DataFrame(all_scenarios)
output=output[col_order]

output.to_csv('{}scenario_outputs.csv'.format(folder))

import requests
host='https://cityio.media.mit.edu/'
table_name='corktown'
cityIO_output_path=host+'api/table/update/'+table_name    
r = requests.post(cityIO_output_path+'/GEOGRIDDATA', data = json.dumps(geogrid_data_inno_com))
print(r)