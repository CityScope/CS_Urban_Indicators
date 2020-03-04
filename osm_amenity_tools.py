#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Mar  2 11:16:01 2020

@author: doorleyr
"""
import urllib
import json

def get_osm_amenies(bounds_all, amenity_types):
    """
    takes a list representing the bounds of the area of interest and
    a dictionary defining tag categories and the associated OSM tags 
    Returns a list of amenities with their tag categories
    """
    OSM_URL_ROOT='https://lz4.overpass-api.de/api/interpreter?data=[out:json][bbox];node;way;out;&bbox='

    str_bounds=str(bounds_all[0])+','+str(bounds_all[1])+','+str(bounds_all[2])+','+str(bounds_all[3])
    osm_url_bbox=OSM_URL_ROOT+str_bounds
    with urllib.request.urlopen(osm_url_bbox) as url:
        data=json.loads(url.read().decode())
    amenities={at:0 for at in amenity_types}
    for ind_record in range(len(data['elements'])):
        for at in amenity_types:
            # for each amenity type we're interested in: eg. restaurant, school
            if 'tags' in data['elements'][ind_record]:
                for record_tag in list(data['elements'][ind_record]['tags'].items()):
                    # check each tag in this osm record
                    record_tag_key, record_tag_value= record_tag[0], record_tag[1]
                    for osm_tag in amenity_types[at]:
                        # against each osm tag associated with this amenity type
                        osm_tag_key, osm_tag_value=osm_tag.split('=')
                        if (((osm_tag_value=='*') or (osm_tag_value==record_tag_value)) 
                                and (osm_tag_key==record_tag_key)):
    #                        lon, lat=data['elements'][ind_record]['lon'], data['elements'][ind_record]['lat']
    #                        x,y=pyproj.transform(wgs, projection,lon, lat)
                            amenities[at]+=1
    return amenities 