#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Mar  2 12:20:41 2020

@author: doorleyr
"""
import json
import datetime
#import copy
from osm_amenity_tools import *
from indicator_tools import *
import pandas as pd
import urllib
from time import sleep
import requests

# Which table?
import sys

if len(sys.argv)>1:
    table_name=sys.argv[1]
else:
    table_name='corktown'
    
    
# =============================================================================
# Define Functions
# =============================================================================
def initialise():
    """
    Steps that only need to be performed once when the model starts running
    """
    print('Initialising')
    global geogrid, baseline_amenity_scores, amenity_scores, basic_stats 
    global indicators, indicator_name_order
    with urllib.request.urlopen(cityIO_get_url+'/GEOGRID') as url:
    #get the GEOGRID from cityI/O
        geogrid=json.loads(url.read().decode())
    baseline_amenity_scores=pd.read_csv(AMENITY_SCORES_PATH)
    amenity_scores=baseline_amenity_scores.copy()
#    baseline_indicators=json.load(open(BASELINE_INDICATORS_PATH))
#    indicators=copy.deepcopy(baseline_indicators)
    indicators=json.load(open(BASELINE_INDICATORS_PATH))
    indicator_name_order=[ind['name'] for ind in indicators]
    basic_stats=json.load(open(BASIC_STATS_PATH))
    
        

def perform_grid_updates(geogrid_data):
    """
    Steps that take place every time a change is detected in the 
    city_io grid data
    """
    print('Performing updates')
    a = datetime.datetime.now()
    global indicators, amenity_scores
    
    amenity_scores=baseline_amenity_scores.copy()
    
    residents=basic_stats['residents']
    employees=basic_stats['employees']
    
#    density_indicators=indicators['density']
#    diversity_indicators=indicators['diversity']
    
    mixed_use_pois= ['restaurants', 'pharmacies', 'gyms', 'hotels', 'nightlife']
    
    # update numbers of employees, residents and amenities
    for cell in geogrid_data:
        if cell['name']=='Residential':
            residents+=PEOPLE_PER_RESI_BLD
        elif cell['name'] == ['Office Tower']:
            employees+=PEOPLE_PER_OFFICE_BLD
        elif cell['name']=='Mix-use':
            amenity_scores.loc[amenity_scores['sub_sub_cat'].isin(mixed_use_pois), 'num_present']+=1

    # Update the residential and employment density scores    
    residential_density_score=residents/basic_stats['max_residents']
    employment_density_score=employees/basic_stats['max_employees']
    
    indicators[indicator_name_order.index('Residential Density')]['value'
               ]=residential_density_score
    indicators[indicator_name_order.index('Employment Density')]['value'
               ]=employment_density_score
    indicators[indicator_name_order.index('Residential/Employment Ratio')]['value'
               ]=min(residents, employees)/max(residents, employees) 

    # Update the amenity density scores                     
    total_people=residents+employees
    amenity_scores['quota']=total_people*amenity_scores['quota_per_k_people']/1e6
    amenity_scores['score']=amenity_scores.apply(lambda row: min(1,row['num_present']/row['quota']), axis=1)

    # TODO: aggregation should be a helper function as it's use in two scripts
    sub_cat_scores=amenity_scores.groupby('sub_cat').agg({'num_present': 'sum',
                                     'score': 'mean',
                                     'category': 'first'})
    # category density scores    
    cat_scores=sub_cat_scores.groupby('category').agg({'num_present': 'sum',
                                 'score': 'mean'}) 
    for ind, row in cat_scores.iterrows():
        indicators[indicator_name_order.index('{} Density'.format(ind))]['value'
                   ]=row['score']
    b = datetime.datetime.now()  
    print('Density and Diversity computations took {} seconds'.format((b-a).microseconds/1e6))
     
    r = requests.post(cityIO_post_url+'/indicators', data = json.dumps(indicators))
    print('Density Indicators: {}'.format(r))
    c = datetime.datetime.now()
    print('Sending Density and Diversity data took {} seconds'.format((c-b).microseconds/1e6))

    
#    density_indicators['Residential Density']=residential_density_score
#    density_indicators['Employment Density']=employment_density_score
#    diversity_indicators['Residential/Employment Ratio']=min(residents, employees)/max(residents, employees)
    
#    r = requests.post(cityIO_post_url+'/indicators2/density', data = json.dumps(density_indicators))
#    print('Density Indicators: {}'.format(r))
#    r = requests.post(cityIO_post_url+'/indicators2/diversity', data = json.dumps(diversity_indicators))
#    print('DiversityIndicators: {}'.format(r))
    
def perform_access_updates(ind_access):
    global indicators
    for poi in ind_access:
        for ind in indicators:
            if ind['name']=='Proximity to {}'.format(poi):
                ind['value']=min(1, ind_access[poi])
    r = requests.post(cityIO_post_url+'/indicators', data = json.dumps(indicators))
    print('Accessibility: {}'.format(r))
    
# INPUTS
AMENITY_SCORES_PATH='tables/{}/amenity_scores.csv'.format(table_name)
BASIC_STATS_PATH='tables/{}/basic_stats.json'.format(table_name)
BASELINE_INDICATORS_PATH='tables/{}/baseline_indicators.json'.format(table_name)

# CITY I/O
host='https://cityio.media.mit.edu/'
table_name='corktown'
cityIO_get_url=host+'api/table/'+table_name
cityIO_post_url=host+'api/table/update/'+table_name


SLEEP_TIME=0.1 # seconds to sleep between checking cityI/O

PEOPLE_PER_RESI_BLD=200
PEOPLE_PER_OFFICE_BLD=200


initialise()

# =============================================================================
# Update Loop
# =============================================================================
last_grid_hash_Id=0
last_access_hash_id=0
while True:
    sleep(SLEEP_TIME)
# =============================================================================
# check if grid data changed and perform updates if so
# =============================================================================
    try:
        with urllib.request.urlopen(cityIO_get_url+'/meta/hashes') as url:
            hashes=json.loads(url.read().decode())
        grid_hash_id=hashes['GEOGRIDDATA']
        access_hash_id=hashes['ind_access']
    except:
        print('Cant access cityIO hashes')
        grid_hash_id=1
        access_hash_id=1
        sleep(1)
    if grid_hash_id==last_grid_hash_Id:
        pass
    else:
        try:
            a = datetime.datetime.now()
            with urllib.request.urlopen(cityIO_get_url+'/GEOGRIDDATA') as url:
                geogrid_data=json.loads(url.read().decode())
            b = datetime.datetime.now()
            print('Getting GEOGRID data took {} seconds'.format((b-a).microseconds/1e6))
            perform_grid_updates(geogrid_data)
            last_grid_hash_Id=grid_hash_id
        except:
            print('Cant access GEOGRID data')
            sleep(1) 
# =============================================================================
# check if accessibility data changed and perform updates if so
# =============================================================================
    if access_hash_id==last_access_hash_id:
        pass
    else:
        try:
            with urllib.request.urlopen(cityIO_get_url+'/ind_access') as url:
                ind_access_data=json.loads(url.read().decode())
            perform_access_updates(ind_access_data)
            last_access_hash_id=access_hash_id
        except:
            print('Cant access ind_access data')
            sleep(1) 