#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Mar  2 11:23:12 2020

@author: doorleyr
"""
import math
import pandas as pd

def shannon_equitability_score(species_counts):
    diversity=0
    pop_size=sum(species_counts)
    if ((len(species_counts)>1) and (pop_size>0)):        
        for count in species_counts:
            pj=count/pop_size
            if not pj==0:
                diversity+= -pj*math.log(pj)
        equitability=diversity/math.log(len(species_counts))
        return equitability
    else:
        return None

def parse_CityScopeCategories(fpath,CS_column='CS Amenities ',NAICS_column='Unnamed: 5'):
    '''
    Useful function to parse the cityscope categories excel located at:
    fpath = tables/200405_CityScope.categories.xlsx
    
    '''
    CS_cats = pd.read_excel(fpath).iloc[1:]
    CS_cats = CS_cats[[CS_column,NAICS_column]]
    CS_cats['shifted'] = CS_cats[CS_column]
    while any(CS_cats[CS_column].isna()):
        CS_cats['shifted'] = CS_cats['shifted'].shift(1)
        CS_cats.loc[CS_cats[CS_column].isna(),CS_column] = CS_cats[CS_cats[CS_column].isna()]['shifted']
    CS_cats = CS_cats.drop('shifted',1)
    CS_cats = CS_cats.dropna().drop_duplicates()
    CS_cats['NAICS'] = CS_cats[NAICS_column].str.strip().str.split(' ').apply(lambda x:x[0])
    CS_cats['NAICS_name'] = [n.replace(c,'').replace('-','').strip() for n,c in CS_cats[[NAICS_column,'NAICS']].values]
    CS_cats = CS_cats.drop(NAICS_column,1)
    return CS_cats