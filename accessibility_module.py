#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Sep  6 12:04:07 2019

@author: doorleyr
"""
from osm_amenity_tools import *
import pandas as pd
import networkx as nx
from time import sleep
import json
import urllib
import random
import requests
import numpy as np
from scipy import spatial
import pyproj
import sys

if len(sys.argv)>1:
    table_name=sys.argv[1]
else:
    table_name='corktown'

# =============================================================================
# Functions

#def get_lon_lat_of_way(way_nodes, nodes_to_lonlat):
#    """
#    When OSM is queried for both nodes and ways in the same bounding box,
#    ways may include some nodes which were not returned in the nodes query.
#    This function chcks each node in the way until it finds one and gets the coordinates
#    """
#    found_node=False
#    node_ind=0
#    while not found_node:
#        next_node=way_nodes[node_ind]
#        if next_node in nodes_to_lonlat:
#            found_node=True
#        else:
#            node_ind+=1
#    lon, lat=nodes_to_lonlat[next_node]
#    return lon, lat
#
#def get_osm_amenies(bounds_all, amenity_types, wgs, projection):
#    """
#    takes a list representing the bounds of the area of interest and
#    a dictionary defining tag categories and the associated OSM tags 
#    Returns a list of amenity locations by category
#    """
#    OSM_NODES_URL_ROOT='https://lz4.overpass-api.de/api/interpreter?data=[out:json][bbox];node;out;&bbox='
#    OSM_WAYS_URL_ROOT='https://lz4.overpass-api.de/api/interpreter?data=[out:json][bbox];way;out;&bbox='
#    
#    amenities={at:{'lon': [], 'lat': [], 'x':[], 'y': [], 'count':0} for at in amenity_types}
#    
#    str_bounds=str(bounds_all[0])+','+str(bounds_all[1])+','+str(bounds_all[2])+','+str(bounds_all[3])
#    osm_node_url_bbox=OSM_NODES_URL_ROOT+str_bounds
#    osm_way_url_bbox=OSM_WAYS_URL_ROOT+str_bounds
#    with urllib.request.urlopen(osm_node_url_bbox) as url:
#        node_data=json.loads(url.read().decode())
#    with urllib.request.urlopen(osm_way_url_bbox) as url:
#        way_data=json.loads(url.read().decode())
#    # create lookup of nodes to lat,lons so that we can look up the positions of ways
#    nodes_to_lonlat={}
#    for record in node_data['elements']:
#        nodes_to_lonlat[record['id']]=[record['lon'], record['lat']]
#    for record in node_data['elements'] + way_data['elements']:
#        for at in amenity_types:
#            # for each amenity type we're interested in: eg. restaurant, school
#            if 'tags' in record:
#                for record_tag in list(record['tags'].items()):
#                    # check each tag in this osm record
#                    record_tag_key, record_tag_value= record_tag[0], record_tag[1]
#                    for osm_tag in amenity_types[at]:
#                        # against each osm tag associated with this amenity type
#                        osm_tag_key, osm_tag_value=osm_tag.split('=')
#                        if (((osm_tag_value=='*') or (osm_tag_value==record_tag_value)) 
#                                and (osm_tag_key==record_tag_key)):
#                            # this is a relevant amenity: add it to the list
#                            # if it's a node, get the latlon directly, if its a way: lookup the first node
#                            if record['type']=='node':
#                                lon, lat=record['lon'], record['lat']
#                            else:
#                                lon, lat=get_lon_lat_of_way(record['nodes'], nodes_to_lonlat)
#                            x,y=pyproj.transform(wgs, projection,lon, lat)
#                            amenities[at]['lon'].append(lon)
#                            amenities[at]['lat'].append(lat)
#                            amenities[at]['x'].append(x)
#                            amenities[at]['y'].append(y)
#                            amenities[at]['count']+=1
#    return amenities

def create_sample_points(grid_x, grid_y, col_margin_left, row_margin_top, 
                         cell_width, cell_height,stride):
    """
    X denotes a coodrinate [x,y]
    dXdRow denotes the change in the coordinates when the row index increases by 1
    """
    dXdCol=np.array([grid_x[1]-grid_x[0], grid_y[1]-grid_y[0]])
    dXdRow=np.array([dXdCol[1], -dXdCol[0]]) # rotate the vector 90 degrees
    grid_origin=np.array([grid_x[0], grid_y[0]])
    sample_points_origin=grid_origin-row_margin_top*dXdRow-col_margin_left*dXdCol
    sample_points=np.array([sample_points_origin+stride*j*dXdCol+stride*i*dXdRow for i in range(
            int(cell_height/stride)) for j in range(int(cell_width/stride))])
    return list(sample_points[:,0]), list(sample_points[:,1])
    
        
def create_access_geojson(xs, ys, grids, scalers):
    """
    takes lists of x and y coordinates and a list containing the accessibility 
    score for each point and tag category
    """
       
    output_geojson={
     "type": "FeatureCollection",
     "features": []
    }    
    for i in range(len(xs)):
        geom={"type": "Point","coordinates": [xs[i],ys[i]]}
        props={t: np.power(grids[i][t]/scalers[t], 1) for t in all_poi_types}
        feat={
         "type": "Feature",
         "properties": props,
         "geometry": geom
        }
        output_geojson["features"].append(feat) 
    return output_geojson

def createGridGraphs(geogrid_xy, interactive_meta_cells, graph, nrows, ncols, 
                     cell_size, kd_tree_nodes, dist_thresh):
    """
    returns new networks including roads around the cells
    """
#    create graph internal to the grid
#    graph.add_nodes_from('g'+str(n) for n in range(len(grid_coords_xy)))
    n_links_to_real_net=0
    for c in range(ncols):
        for r in range(nrows):
            cell_num=r*ncols+c
            if cell_num in interactive_meta_cells: # if this is an interactive cell
                # if close to any real nodes, make a link
                dist_to_closest, closest_ind=kd_tree_nodes.query(geogrid_xy[cell_num], k=1)
                if dist_to_closest<dist_thresh:
                    n_links_to_real_net+=1
                    closest_node_id=nodes.iloc[closest_ind]['id_int']
                    graph.add_edge('g'+str(cell_num), closest_node_id, weight=dist_to_closest/dummy_link_speed_met_min)
                    graph.add_edge(closest_node_id, 'g'+str(cell_num), weight=dist_to_closest/dummy_link_speed_met_min)                   
                # if not at the end of a row, add h link
                if not c==ncols-1:
                    graph.add_edge('g'+str(r*ncols+c), 'g'+str(r*ncols+c+1), weight=cell_size/dummy_link_speed_met_min)
                    graph.add_edge('g'+str(r*ncols+c+1), 'g'+str(r*ncols+c), weight=cell_size/dummy_link_speed_met_min)
                # if not at the end of a column, add v link
                if not r==nrows-1:
                    graph.add_edge('g'+str(r*ncols+c), 'g'+str((r+1)*ncols+c), weight=cell_size/dummy_link_speed_met_min)
                    graph.add_edge('g'+str((r+1)*ncols+c), 'g'+str(r*ncols+c), weight=cell_size/dummy_link_speed_met_min)
    return graph 

# =============================================================================
# CONFIGURATION
# =============================================================================
# INPUTS
OSM_CONFIG_FILE_PATH='./osm_amenities.json'
TABLE_CONFIG_FILE_PATH='./tables/{}/table_configs.json'.format(table_name)
UA_NODES_PATH='./tables/{}/geometry/access_network_nodes.csv'.format(table_name)
UA_EDGES_PATH='./tables/{}/geometry/access_network_edges.csv'.format(table_name)
ZONES_PATH='./tables/{}/geometry/model_area.geojson'.format(table_name)

table_configs=json.load(open(TABLE_CONFIG_FILE_PATH))

host='https://cityio.media.mit.edu/'

# TODO: below is temporary solution. Should be handled by the config file for each table
simple_pois_per_lu={
                  'Residential': {'housing': 200},
                  'Office Tower': {'employment': 200},
                  'Plaza': {'parks': 1},
                  'Park': {'parks': 1},
                  'Mix-use': {'food': 1, 'shopping': 1, 'nightlife': 1, 'groceries': 1},
                  'Service': {'parking': 100}}

RADIUS=15

local_epsg = table_configs['local_epsg']
projection=pyproj.Proj("+init=EPSG:"+local_epsg)
wgs=pyproj.Proj("+init=EPSG:4326")

cityIO_get_url=host+'api/table/'+table_name
cityIO_post_url=host+'api/table/update/{}/'.format(table_name)
access_post_url=cityIO_post_url+'access'
indicator_post_url=cityIO_post_url+'ind_access'

dummy_link_speed_met_min=2*1000/60 
# for adding slow links between grid nodes 
# and between real nodes, sample nodes and grid nodes


# =============================================================================
# Get initial city_IO data
# =============================================================================


with urllib.request.urlopen(cityIO_get_url+'/GEOGRID') as url:
#get the geogrid from cityI/O
    geogrid=json.loads(url.read().decode())
    geogrid_header=geogrid['properties']['header']
    
     
geogrid_ll=[geogrid['features'][i][
        'geometry']['coordinates'][0][0
        ] for i in range(len(geogrid['features']))]

geogrid_x, geogrid_y=pyproj.transform(wgs, projection,
                                              [geogrid_ll[p][0] for p in range(len(geogrid_ll))], 
                                              [geogrid_ll[p][1] for p in range(len(geogrid_ll))])

geogrid_xy=[[geogrid_x[i], geogrid_y[i]] for i in range(len(geogrid_x))]

# =============================================================================
# get baseline POIS of study area
# =============================================================================
print('Getting OSM data')

osm_amenities=json.load(open(OSM_CONFIG_FILE_PATH))['osm_pois']
tags_to_include=table_configs['access_osm_pois']

tags={t: osm_amenities[t] for t in tags_to_include}
# To get all amenity data
bounds_all=table_configs['bboxes']['amenities']
base_amenities=get_osm_amenies(bounds_all, tags, wgs, projection)

scalers=table_configs['scalers']

# get zonal POI data (eg. housing per census tract)
if table_configs['access_zonal_pois']:
    zones = json.load(open(ZONES_PATH))

# =============================================================================
# Create the transport network
# =============================================================================
# Baseline network from urbanaccess results
print('Building the base transport network')
edges=pd.read_csv(UA_EDGES_PATH)
nodes=pd.read_csv(UA_NODES_PATH)   

nodes_lon=nodes['x'].values
nodes_lat=nodes['y'].values
nodes_x, nodes_y= pyproj.transform(wgs, projection,nodes_lon, nodes_lat)
kdtree_base_nodes=spatial.KDTree(np.column_stack((nodes_x, nodes_y)))

graph=nx.DiGraph()
for i, row in edges.iterrows():
    graph.add_edge(row['from_int'], row['to_int'], weight=row['weight'])
  
all_poi_types=[tag for tag in base_amenities] + table_configs['access_zonal_pois']
assert(all(poi in scalers for poi in all_poi_types))
pois_at_base_nodes={n: {t:0 for t in all_poi_types} for n in graph.nodes} 

print('Finding closest node to each base POI')            
# associate each amenity with its closest node in the base network
for tag in base_amenities:
    for ai in range(len(base_amenities[tag]['x'])):
        nearest_node=nodes.iloc[kdtree_base_nodes.query(
                [base_amenities[tag]['x'][ai],
                base_amenities[tag]['y'][ai]])[1]]['id_int']
        pois_at_base_nodes[nearest_node][tag]+=1
if table_configs['access_zonal_pois']:
    for f in zones['features']:
        centroid_xy=pyproj.transform(wgs, projection,f['properties']['centroid'][0], 
                                     f['properties']['centroid'][1])
        distance, nearest_node_ind=kdtree_base_nodes.query(centroid_xy)
        nearest_node=nodes.iloc[nearest_node_ind]['id_int']
        if distance<1000: #(because some zones are outside the network area)
            for poi_type in table_configs['access_zonal_pois']:
                if poi_type in f['properties']:
                    pois_at_base_nodes[nearest_node][poi_type]+=f['properties'][poi_type]

# Add links for the new network defined by the interactive area  
#print('Adding dummy links for the grid network') 
                    
interactive_meta_cells={i:i for i in range(len(geogrid['features']))}

graph=createGridGraphs(geogrid_xy, interactive_meta_cells, graph, geogrid_header['nrows'], 
                       geogrid_header['ncols'], geogrid_header['cellSize'], 
                       kdtree_base_nodes, 100)

# =============================================================================
# Prepare the sample grid points for the output accessibility results
col_margin_left=table_configs['sampling_grid']['col_margin_left']
row_margin_top=table_configs['sampling_grid']['row_margin_top']
cell_width=table_configs['sampling_grid']['cell_width']
cell_height=table_configs['sampling_grid']['cell_height']
stride=table_configs['sampling_grid']['stride']
sample_x, sample_y= create_sample_points(geogrid_x, geogrid_y, col_margin_left, 
                                         row_margin_top, cell_width, 
                                         cell_height,stride)
sample_lons, sample_lats=pyproj.transform(projection,wgs, sample_x, sample_y)

# =============================================================================
# Baseline Accessibility
# =============================================================================
# add virtual links joining each sample point to its closest nodes within a tolerance
# include both baseline links and new links

# first create new kdTree including the baseline nodes and the new grid nodes

print('Baseline Accessibility') 

all_nodes_ids, all_nodes_xy=[], []
for ind_node in range(len(nodes_x)):
    all_nodes_ids.append(nodes.iloc[ind_node]['id_int'])
    all_nodes_xy.append([nodes_x[ind_node], nodes_y[ind_node]])
for ind_grid_cell in range(len(geogrid_xy)):
    all_nodes_ids.append('g'+str(ind_grid_cell))
    all_nodes_xy.append(geogrid_xy[ind_grid_cell])

kdtree_all_nodes=spatial.KDTree(np.array(all_nodes_xy))

# add the virtual links between sample points and closest nodes
MAX_DIST_VIRTUAL=30
all_sample_node_ids=[]
for p in range(len(sample_x)):
    all_sample_node_ids.append('s'+str(p))
    graph.add_node('s'+str(p))
    distance_to_closest, closest_nodes=kdtree_all_nodes.query([sample_x[p], sample_y[p]], 5)
    for candidate in zip(distance_to_closest, closest_nodes):
        if candidate[0]<MAX_DIST_VIRTUAL:
            close_node_id=all_nodes_ids[candidate[1]]
            graph.add_edge('s'+str(p), close_node_id, weight=candidate[0]/(dummy_link_speed_met_min))


# for each sample node, create an isochrone and count the amenities of each type        
sample_nodes_acc_base={n: {poi_type:0 for poi_type in all_poi_types} for n in range(len(sample_x))} 
for sn in sample_nodes_acc_base:
    if sn%200==0:
        print('{} of {} sample nodes'.format(sn, len(sample_nodes_acc_base)))
    isochrone_graph=nx.ego_graph(graph, 's'+str(sn), radius=RADIUS, center=True, 
                                 undirected=False, distance='weight')
    reachable_real_nodes=[n for n in isochrone_graph.nodes if n in pois_at_base_nodes]
    for poi_type in all_poi_types:
        sample_nodes_acc_base[sn][poi_type]=sum([pois_at_base_nodes[reachable_node][poi_type] 
                                            for reachable_node in reachable_real_nodes])   
    
    
# same for geogrid nodes
grid_nodes_acc_base={n: {poi_type:0 for poi_type in all_poi_types} for n in range(len(geogrid_xy))} 
for gn in grid_nodes_acc_base:
    if gn%200==0:
        print('{} of {} geogrid nodes'.format(gn, len(grid_nodes_acc_base)))
    isochrone_graph=nx.ego_graph(graph, 'g'+str(gn), radius=RADIUS, center=True, 
                                 undirected=False, distance='weight')
    reachable_real_nodes=[n for n in isochrone_graph.nodes if n in pois_at_base_nodes]
    for poi_type in all_poi_types:
        grid_nodes_acc_base[gn][poi_type]=sum([pois_at_base_nodes[reachable_node][poi_type] 
                                            for reachable_node in reachable_real_nodes]) 

# Create initial geojson results
grid_geojson=create_access_geojson(sample_lons, sample_lats, 
                                   sample_nodes_acc_base, scalers)

r = requests.post(access_post_url, data = json.dumps(grid_geojson))
print('Base geojson: {}'.format(r))
#r = requests.post(indicator_post_url, data = json.dumps(avg_access))
#print('Base indicators: {}'.format(r))

# =============================================================================
# Interactive Accessibility Analysis
# =============================================================================
# instead of recomputing the isochrone for every sample point, we will reverse 
# the graph and compute the isochrone around each new amenity
print('Preparing for interactve updates. May take a few minutes.') 
rev_graph=graph.reverse()
# find the sample nodes affected by each interactive grid cell
affected_sample_nodes={} # to create the geojson
affected_grid_nodes={} # to get the average accessibility. eg. from all housing cells
for gi in range(len(geogrid_xy)):
    if gi%200==0:
        print('{} of {} geogrid nodes'.format(gi, len(geogrid_xy)))
    a_node='g'+str(gi)
    affected_nodes=nx.ego_graph(rev_graph, a_node, radius=RADIUS, center=True, 
     undirected=False, distance='weight').nodes
    affected_grid_nodes[gi]=[n for n in affected_nodes if 'g' in str(n)]
    affected_sample_nodes[gi]=[n for n in affected_nodes if 's' in str(n)]


from_employ_pois=['housing']
from_housing_pois=[poi for poi in all_poi_types if not poi=='housing']

 
lastId=0
pois_per_lu=simple_pois_per_lu
print('Listening for grid updates') 
while True:   
# =============================================================================
#     check if grid data changed
# =============================================================================
    try:
        with urllib.request.urlopen(cityIO_get_url+'/meta/hashes/GEOGRIDDATA') as url:
            hash_id=json.loads(url.read().decode())
    except:
        print('Cant access city_IO grid hash')
        hash_id=1
    if hash_id==lastId:
        sleep(0.2)
    else:
        try:
            with urllib.request.urlopen(cityIO_get_url+'/GEOGRIDDATA') as url:
                cityIO_grid_data=json.loads(url.read().decode())
        except:
            print('Cant access city_IO grid data')
# =============================================================================
# UPDATES
# =============================================================================
        lastId=hash_id
        sample_nodes_acc={n: {t:sample_nodes_acc_base[n][t] for t in all_poi_types
                              } for n in range(len(sample_x))}
        grid_nodes_acc={n: {t:grid_nodes_acc_base[n][t] for t in all_poi_types
                              } for n in range(len(geogrid_xy))}
        for gi, cell_data in enumerate(cityIO_grid_data):
#            if not type(usage)==list:
#                print('Usage value is not a list: '+str(usage))
#                usage=[-1,-1]
            this_grid_lu=cell_data['name']
            if this_grid_lu in pois_per_lu:
                sample_nodes_to_update=affected_sample_nodes[gi]
                grid_nodes_to_update=affected_grid_nodes[gi]
                for poi in pois_per_lu[this_grid_lu]:
                    if poi in all_poi_types:
                        n_to_add=pois_per_lu[this_grid_lu][poi]
                        if n_to_add<1:
                            if random.uniform(0,1)<=n_to_add:
                                n_to_add=1
                            else:
                                n_to_add=0
                        for n in sample_nodes_to_update:
                            sample_nodes_acc[int(n.split('s')[1])][poi]+=n_to_add
                        for n in grid_nodes_to_update:
                            grid_nodes_acc[int(n.split('g')[1])][poi]+=n_to_add
# =============================================================================
# OUTPUTS
# =============================================================================
        avg_access={}
        # TODO: should use baseline land uses as well as added ones
        for poi in from_employ_pois:
            avg_access[poi]=np.mean([grid_nodes_acc[g][poi
                       ] for g in range(len(cityIO_grid_data)
                        ) if cityIO_grid_data[g]['name'] in ['Residential', 'Mix-use']])/scalers[poi]
        for poi in from_housing_pois:
            avg_access[poi]=np.mean([grid_nodes_acc[g][poi
                       ] for g in range(len(cityIO_grid_data)
                        ) if cityIO_grid_data[g]['name'] in ['Office Tower', 'Mix-use']])/scalers[poi]
                            
        grid_geojson=create_access_geojson(sample_lons, sample_lats, 
                                           sample_nodes_acc, scalers)
        r = requests.post(access_post_url, data = json.dumps(grid_geojson))
        print('Geojson: {}'.format(r))
        r = requests.post(indicator_post_url, data = json.dumps(avg_access))
        print('Indicators: {}'.format(r))
        sleep(0.5) 

# =============================================================================
