#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jun 12 11:21:39 2020

@author: doorleyr
"""

from proximity_indicator import ProxIndicator
from innovation_indicator import InnoIndicator
from economic_indicator import EconomicIndicator
from buildings_indicator import BuildingsIndicator
from diversity_indicator import DiversityIndicator

import json
import pandas as pd
import urllib


table_name='corktown'
host='https://cityio.media.mit.edu/'
cityIO_get_url=host+'api/table/'+table_name

# =============================================================================
# Initialise Indicators
# =============================================================================
I = InnoIndicator()    
P = ProxIndicator(name='proximity',   indicator_type_in='numeric', table_name='corktown')
B= BuildingsIndicator(name='buildings',  table_name='corktown')
D= DiversityIndicator(name='diversity',  table_name='corktown')
E = EconomicIndicator(name='Economic',
                      table_name='corktown')

# =============================================================================
# Load contextual data
# =============================================================================

with urllib.request.urlopen(cityIO_get_url+'/GEOGRID') as url:
    geogrid=json.loads(url.read().decode())
cell_area=geogrid['properties']['header']['cellSize']**2

updatable=[((feat['properties']['interactive'])or (feat['properties']['static_new'])
           ) for feat in geogrid['features']]

types=geogrid['properties']['types']

static_types=geogrid['properties']['static_types']

types.update(static_types)

reporting_types=[t for t in types if t not in ['None','Residential Low Density', 'Industrial']]

for ind in [I, P, 
#             P_hm, 
            B, D, E]:
    ind.types_def=types
    ind.geogrid_header=geogrid['properties']['header']

# =============================================================================
# Load the saved land use scenarios from city_IO
# =============================================================================
# Scenarios are saved as scenrio0, scenario1 etc. on cityIO
# scenario name is contained in the 'info' field
# try 0 to N and save all the results
# Additional scenarios can be created and saved to cityIO using the CityScope interactive front-end
all_scenarios={}
for i in range(10):
    try:
        with urllib.request.urlopen(cityIO_get_url+'/scenarios'+str(i)) as url:
            geogriddata=json.loads(url.read().decode())
        all_scenarios[geogriddata['info']['name']]=geogriddata['GEOGRIDDATA']
    except:
        pass
print('Downloaded {} land use scenarios'.format(len(all_scenarios)))

# =============================================================================
# Define some functions to calculate indicators and land use stats for each scenario
# =============================================================================
def get_type_stats(geogrid_data, reporting_types, updatable,cell_area, types_def=types):
    """
    calculates the square meters and capacity of each LU type added to the interactive area
    """
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



def get_all_indicators(geogrid_data):
    """
    calculates values of all the individual indicators for a given scenario
    """
    all_ind=[]
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
    """
    takes the indicators results, square meters and capacities for a given scenario
    and creates a row of data for the output csv
    """
    all_cols={'Scenario': scenario_name}
    for ind in all_ind:
        all_cols[ind['name']+' norm']=ind['value']
        raw_name=ind['name']+' raw'
        if not ind['units']==None:
            raw_name+= ' ['+ind['units']+']'
        all_cols[raw_name]=ind['raw_value']
    return all_cols

# =============================================================================
# Calculate indicators and land use stats for each scenario
# =============================================================================

base_indicators=get_all_indicators(all_scenarios['Baseline'])
base_stats=get_type_stats(all_scenarios['Baseline'], reporting_types, updatable,cell_area)

campus_indicators=get_all_indicators(all_scenarios['Campus_Only'])
campus_stats=get_type_stats(all_scenarios['Campus_Only'], reporting_types, updatable,cell_area)

campus_mobility_indicators=get_all_indicators(all_scenarios['Campus_Only'])
campus_mobility_stats=campus_stats

housing_indicators=get_all_indicators(all_scenarios['Campus_Housing'])
housing_stats=get_type_stats(all_scenarios['Campus_Housing'], reporting_types, updatable,cell_area)

inno_com_indicators=get_all_indicators(all_scenarios['Innovation_Community'])
inno_com_stats=get_type_stats(all_scenarios['Innovation_Community'], reporting_types, updatable,cell_area)

all_scenarios=[]
all_scenarios.append(create_scenario_row(base_indicators, base_stats, scenario_name='BAU'))
all_scenarios.append(create_scenario_row(campus_indicators, campus_stats, scenario_name='Campus Only'))
all_scenarios.append(create_scenario_row(campus_mobility_indicators, campus_mobility_stats, scenario_name='Future Mobility'))
all_scenarios.append(create_scenario_row(housing_indicators, housing_stats, scenario_name='Housing'))
all_scenarios.append(create_scenario_row(inno_com_indicators, inno_com_stats, scenario_name='Innovation Community'))

output=pd.DataFrame(all_scenarios)


# =============================================================================
# Crea and calculate aggregated indicators
# =============================================================================

aggregation={
        'Innovation Potential': ['Knowledge','Skills','R&D Funding'],
         'Economic Performance': ['Average Salary','Productivity','Employment Density', 'Diversity Jobs'],
         'Sustainable Buildings': ['Buildings Energy Performance'],
         'Community Benefits':  ['Access to housing', 'Access to education', 'Access to 3rd Places',
                                 'Access to parks', 'Access to employment', 'Diversity Jobs',
                                 'Diversity Third Places', 'Diversity Education']}
for comp_ind in aggregation:
    cols=[ind_name +' norm' for ind_name in aggregation[comp_ind]]
    output[comp_ind]=output[cols].mean(axis=1)

# =============================================================================
# Create and save output as csv file
# =============================================================================

col_order = ['Scenario']+[col for col in all_scenarios[0] if 'norm' in col]+[
        col for col in all_scenarios[0] if 'raw' in col]+ [
        comp_ind for comp_ind in aggregation]

output=output[col_order]

output.to_csv('scenario_outputs.csv')