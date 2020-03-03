#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Mar  2 12:20:41 2020

@author: doorleyr
"""
import json
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
    global geogrid, amenity_scores, basic_stats, baseline_indicators
    with urllib.request.urlopen(cityIO_get_url+'/GEOGRID') as url:
    #get the GEOGRID from cityI/O
        geogrid=json.loads(url.read().decode())
    amenity_scores=pd.read_csv(AMENITY_SCORES_PATH)
    baseline_indicators=json.load(open(BASELINE_INDICATORS_PATH))
    basic_stats=json.load(open(BASIC_STATS_PATH))
    
        

def perform_updates(output_name, geogrid_data):
    """
    Steps that take place every time a change is detected in the 
    city_io grid data
    """
    print('Performing updates')
    
    residents=basic_stats['residents']
    employees=basic_stats['employees']
    indicators=baseline_indicators.copy()
    
    for cell in geogrid_data:
        if 'Residential' in cell['name']:
            residents+=PEOPLE_PER_RESI_BLD
        elif 'Office' in cell['name']:
            employees+=PEOPLE_PER_OFFICE_BLD
        
    residential_density_score=residents/basic_stats['max_residents']
    employment_density_score=employees/basic_stats['max_employees']
    
    for ind in indicators:
        if ind['name']=='Residential Density':
            ind['value']=residential_density_score
        elif ind['name']=='Employment Density':
            ind['value']=employment_density_score  
        elif ind['name']=='Residential/Employment Ratio':
            ind['value']=min(residents, employees)/max(residents, employees) 
    r = requests.post(cityIO_post_url+'/'+output_name, data = json.dumps(indicators))
    print(r)
    
    
# INPUTS
AMENITY_SCORES_PATH='tables/{}/amenity_scores.csv'.format(table_name)
BASIC_STATS_PATH='tables/{}/basic_stats.json'.format(table_name)
BASELINE_INDICATORS_PATH='tables/{}/baseline_indicators.json'.format(table_name)

# CITY I/O
host='https://cityio.media.mit.edu/'
table_name='corktown'
cityIO_get_url=host+'api/table/'+table_name
cityIO_post_url=host+'api/table/update/'+table_name


SLEEP_TIME=0.1 # seconds to sleep between checkinh cityI/O

PEOPLE_PER_RESI_BLD=200
PEOPLE_PER_OFFICE_BLD=200


initialise()

# =============================================================================
# Update Loop
# =============================================================================
lastId=0
while True:
#check if grid data changed
    try:
        with urllib.request.urlopen(cityIO_get_url+'/meta/hashes/GEOGRIDDATA') as url:
            hash_id=json.loads(url.read().decode())
    except:
        print('Cant access cityIO GEOGRIDDATA hash')
        hash_id=1
    if hash_id==lastId:
        sleep(SLEEP_TIME)
    else:
        try:
            with urllib.request.urlopen(cityIO_get_url+'/GEOGRIDDATA') as url:
                geogrid_data=json.loads(url.read().decode())
            perform_updates('indicators', geogrid_data)
            lastId=hash_id
        except:
            print('Got city_IO GEOGRIDDATA hash but couldnt get data')
            sleep(SLEEP_TIME) 

