#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Mar  2 11:16:01 2020

@author: doorleyr
"""
import urllib
import json
import pyproj

def get_lon_lat_of_way(way_nodes, nodes_to_lonlat):
    """
    When OSM is queried for both nodes and ways in the same bounding box,
    ways may include some nodes which were not returned in the nodes query.
    This function chcks each node in the way until it finds one and gets the coordinates
    """
    found_node=False
    node_ind=0
    while not found_node:
        next_node=way_nodes[node_ind]
        if next_node in nodes_to_lonlat:
            found_node=True
        else:
            node_ind+=1
    lon, lat=nodes_to_lonlat[next_node]
    return lon, lat
    

def get_osm_amenies(bounds_all, amenity_types, wgs, projection):
    """
    takes a list representing the bounds of the area of interest and
    a dictionary defining tag categories and the associated OSM tags 
    Returns a list of amenity locations by category
    """
    OSM_NODES_URL_ROOT='https://lz4.overpass-api.de/api/interpreter?data=[out:json][bbox];node;out;&bbox='
    OSM_WAYS_URL_ROOT='https://lz4.overpass-api.de/api/interpreter?data=[out:json][bbox];way;out;&bbox='
    
    amenities={at:{'lon': [], 'lat': [], 'x':[], 'y': [], 'count':0} for at in amenity_types}
    
    str_bounds=str(bounds_all[0])+','+str(bounds_all[1])+','+str(bounds_all[2])+','+str(bounds_all[3])
    osm_node_url_bbox=OSM_NODES_URL_ROOT+str_bounds
    osm_way_url_bbox=OSM_WAYS_URL_ROOT+str_bounds
    with urllib.request.urlopen(osm_node_url_bbox) as url:
        node_data=json.loads(url.read().decode())
    with urllib.request.urlopen(osm_way_url_bbox) as url:
        way_data=json.loads(url.read().decode())
    # create lookup of nodes to lat,lons so that we can look up the positions of ways
    nodes_to_lonlat={}
    for record in node_data['elements']:
        nodes_to_lonlat[record['id']]=[record['lon'], record['lat']]
    for record in node_data['elements'] + way_data['elements']:
        for at in amenity_types:
            # for each amenity type we're interested in: eg. restaurant, school
            if 'tags' in record:
                for record_tag in list(record['tags'].items()):
                    # check each tag in this osm record
                    record_tag_key, record_tag_value= record_tag[0], record_tag[1]
                    for osm_tag in amenity_types[at]:
                        # against each osm tag associated with this amenity type
                        osm_tag_key, osm_tag_value=osm_tag.split('=')
                        if (((osm_tag_value=='*') or (osm_tag_value==record_tag_value)) 
                                and (osm_tag_key==record_tag_key)):
                            # this is a relevant amenity: add it to the list
                            # if it's a node, get the latlon directly, if its a way: lookup the first node
                            if record['type']=='node':
                                lon, lat=record['lon'], record['lat']
                            else:
                                lon, lat=get_lon_lat_of_way(record['nodes'], nodes_to_lonlat)
                            x,y=pyproj.transform(wgs, projection,lon, lat)
                            amenities[at]['lon'].append(lon)
                            amenities[at]['lat'].append(lat)
                            amenities[at]['x'].append(x)
                            amenities[at]['y'].append(y)
                            amenities[at]['count']+=1
    return amenities 