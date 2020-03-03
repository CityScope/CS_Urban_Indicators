#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Feb 20 09:57:10 2020

@author: doorleyr
"""
import json
from osm_amenity_tools import *
from indicator_tools import *
import pandas as pd
import urllib
import pyproj
import math
from shapely.geometry import shape
import censusdata
import requests



table_name='corktown'

# INPUTS
OSM_CONFIG_FILE_PATH='./osm_amenities.json'
GROUPS_FILE_PATH='./amenity_groups.csv'
TABLE_CONFIG_FILE_PATH='./tables/corktown/table_configs.json'
SIM_AREA_GEOM_PATH='./tables/corktown/table_area.geojson'
SIM_ZONES_PATH='./tables/corktown/sim_zones.json'
WAC_PATH='./tables/corktown/mi_wac_S000_JT00_2017.csv.gz'

# OUTPUTS
AMENITY_SCORES_PATH='tables/{}/amenity_scores.csv'.format(table_name)
BASIC_STATS_PATH='tables/{}/basic_stats.json'.format(table_name)
BASELINE_INDICATORS_PATH='tables/{}/baseline_indicators.json'.format(table_name)

# =============================================================================
# Set-up area and configs
# =============================================================================
host='https://cityio.media.mit.edu/'

table_configs=json.load(open(TABLE_CONFIG_FILE_PATH))[table_name]
osm_amenities=json.load(open(OSM_CONFIG_FILE_PATH))
amenity_groups=pd.read_csv(GROUPS_FILE_PATH)
amenity_scores=amenity_groups.copy()


MAX_RESI_PER_KM=30000
# manhattan is 27k, Dhaka most dense at 45k
MAX_EMP_PER_KM=50000
# manhattan is 50k

AREA=4 #km^2

local_epsg= table_configs['local_epsg']

projection=pyproj.Proj("+init=EPSG:"+local_epsg)
wgs=pyproj.Proj("+init=EPSG:4326")

amenity_types=osm_amenities['osm_pois']

sim_area=json.load(open(SIM_AREA_GEOM_PATH))
sim_zones=json.load(open(SIM_ZONES_PATH))
wac_data=pd.read_csv(WAC_PATH)


full_area=[shape(f['geometry']) for f in sim_area['features']]
bounds=[shp.bounds for shp in full_area]
bounds_all=[min([b[0] for b in bounds]), #W
               min([b[1] for b in bounds]), #S
               max([b[2] for b in bounds]), #E
               max([b[3] for b in bounds])] #N

# =============================================================================
# Get OSM amenities and census data
# =============================================================================

amenities=get_osm_amenies(bounds_all, amenity_types)

# get the census data
# living, working, job types, housing types
table_geoids=[z.split('US')[1] for z in sim_zones]

census_data_columns={'B01003_001E': 'population'}
# add housing columns
#for i in range(4,27):
#    census_data_columns['B25063_' +str(i).zfill(3) +'E']= 'housing'+str(i)

acs_pop_data=censusdata.download('acs5', 2017,
    censusdata.censusgeo([('state', '26'), ('county', '163'),('block group', '*')]),list(census_data_columns.keys()))
acs_pop_data['geo']=acs_pop_data.apply(lambda row: dict(row.name.geo), axis=1)
acs_pop_data['geoid']=acs_pop_data.apply(lambda row: 
    str(row['geo']['state']).zfill(2)+ str(row['geo']['county']).zfill(3)+
    str(row['geo']['tract']).zfill(6)+str(row['geo']['block group']), axis=1)
acs_pop_data=acs_pop_data.set_index('geoid')
acs_pop_data=acs_pop_data.loc[table_geoids]

acs_pop_data=acs_pop_data.rename(columns=census_data_columns)
pop_data_full_table=acs_pop_data.sum(axis=0)
population_all=int(pop_data_full_table['population'])

wac_data['block_group']=wac_data.apply(lambda row: str(row['w_geocode'])[:12], axis=1)
wac_data=wac_data.loc[wac_data['block_group'].isin(table_geoids)]

wac_data_full_table=wac_data.sum(axis=0)
n_jobs_all=int(wac_data_full_table['C000'])

total_people=n_jobs_all+population_all

max_residents= MAX_RESI_PER_KM * AREA
max_employees= MAX_EMP_PER_KM * AREA

#save the basic stats for use in the resposive module
json.dump({'residents': population_all, 'employees': n_jobs_all,
           'max_residents':max_residents, 'max_employees': max_employees,
            'area': AREA}, open(BASIC_STATS_PATH, 'w'))
# =============================================================================
# Density 
# =============================================================================
# density of residential: census
# density of employment: Workplace Area Characteristics file

# 3rd day, 3rd night: cat scores
# education, cultural: sub-cat scores
amenity_scores['quota']=total_people*amenity_scores['quota_per_k_people']/1000

amenity_scores['num_present']=amenity_scores.apply(lambda row: 
    amenities[row['sub_sub_cat']], axis=1)

# individual density scores
amenity_scores['score']=amenity_scores.apply(lambda row: min(1,row['num_present']/row['quota']), axis=1)

# sub_cat density scores  
sub_cat_scores=amenity_scores.groupby('sub_cat').agg({'num_present': 'sum',
                                     'score': 'mean',
                                     'category': 'first'})
# category density scores    
cat_scores=sub_cat_scores.groupby('category').agg({'num_present': 'sum',
                                 'score': 'mean'})
    
residential_density_score=population_all/max_residents
employment_density_score=n_jobs_all/max_residents
resi_employ_ratio=min(population_all, n_jobs_all)/max(population_all, n_jobs_all)
    
# =============================================================================
# Diversity
# =============================================================================
# working pop income, employment sector from WAC
# live-work ratio
# cultural, education: diversity of sub-cats
sub_cat_diversity=amenity_scores.groupby('sub_cat').agg(
        {'num_present': shannon_equitability_score}).rename(columns={'num_present': 'diversity_score'})
# 3rd places: diversity of categories    
cat_diversity=sub_cat_scores.groupby('category').agg(
        {'num_present': shannon_equitability_score}).rename(columns={'num_present': 'diversity_score'})

job_type_cols=[col for col in wac_data if (('CNS' in col) and ('00' not in col))]
job_counts=wac_data_full_table[job_type_cols].values
job_type_diversity=shannon_equitability_score(job_counts)
# Corktown skewed towards CNS 72: (Accommodation and Food Services) 

income_level_cols=[col for col in wac_data if (('CA' in col) and ('00' not in col))]
income_level_counts=wac_data_full_table[income_level_cols].values
income_level_diversity=shannon_equitability_score(income_level_counts)

indicators=[{'name': 'Residential Density','category': 'Density', 'value': residential_density_score},
            {'name': 'Employment Density','category': 'Density', 'value': employment_density_score},
            {'name': '3rd Places Day Density','category': 'Density', 'value': cat_scores.loc['3rd places Day', 'score']},
            {'name': '3rd Places Night Density','category': 'Density', 'value': cat_scores.loc['3rd places Night', 'score']},
            {'name': 'Educational Inst Density','category': 'Density', 'value': cat_scores.loc['Educational', 'score']},
            {'name': 'Cultural Inst Density','category': 'Density', 'value': sub_cat_scores.loc['Culture', 'score']},
            {'name': 'Cultural Inst Diversity','category': 'Diversity', 'value': sub_cat_diversity.loc['Culture', 'diversity_score']},
            {'name': 'Residential/Employment Ratio','category': 'Diversity', 'value': resi_employ_ratio},
            {'name': 'Educational Inst Diversity','category': 'Diversity', 'value': sub_cat_diversity.loc['Educational', 'diversity_score']},
            {'name': '3rd Places Diversity','category': 'Diversity', 'value': cat_diversity.loc['3rd places Day', 'diversity_score']},
            {'name': 'Job Type Diversity','category': 'Diversity', 'value': job_type_diversity},
            {'name': 'Income Level Diversity','category': 'Diversity', 'value': income_level_diversity}]


# =============================================================================
# Random values
# =============================================================================
import random
for prox_ind in ['Employment','Education', 'Housing', '3rd Places', 'Parks', 'Healthcare']:
    indicators.append({'name': 'Proximity to {}'.format(prox_ind), 
                      'category': 'Proximity', 'value': random.random()})
for energy_ind in ['Buildings','Mobility']:
    indicators.append({'name': '{} Energy Efficiency'.format(energy_ind), 
                      'category': 'Energy', 'value': random.random()})
    indicators.append({'name': '{} Embodied Energy'.format(energy_ind), 
                      'category': 'Energy', 'value': random.random()})
# =============================================================================
# Save results
# =============================================================================
amenity_scores.to_csv('tables/corktown/amenity_scores.csv', index=False)


host='https://cityio.media.mit.edu/'
cityIO_output_path=host+'api/table/update/'+table_name
       
r = requests.post(cityIO_output_path+'/indicators', data = json.dumps(indicators))
print(r)

json.dump(indicators, open(BASELINE_INDICATORS_PATH, 'w'))