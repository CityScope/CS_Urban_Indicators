#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Mar 18 10:30:53 2020

@author: doorleyr
"""

from osm_amenity_tools import *
import pandas as pd
import networkx as nx
import json
import urllib
import numpy as np
from scipy import spatial
import pyproj
import random
from toolbox import Handler, Indicator


class ProxIndicator(Indicator):
    def setup(self):
        self.table_name='corktown'
        self.osm_config_file_path='./osm_amenities.json'
        self.table_config_file_path='./tables/{}/table_configs.json'.format(self.table_name)
        self.ua_nodes_path='./tables/{}/geometry/access_network_nodes.csv'.format(self.table_name)
        self.ua_edges_path='./tables/{}/geometry/access_network_edges.csv'.format(self.table_name)
        self.zones_path='./tables/{}/geometry/model_area.geojson'.format(self.table_name)
        self.params_path='./tables/{}/accessibility_params.json'.format(self.table_name)
        self.table_configs=json.load(open(self.table_config_file_path))
        self.radius=15 # minutes
        self.dummy_link_speed_met_min=2*1000/60
        self.host='https://cityio.media.mit.edu/'
        self.pois_per_lu={
                  'Residential': {'housing': 200},
                  'Office Tower': {'employment': 200},
                  'Plaza': {'parks': 1},
                  'Park': {'parks': 1},
                  'Mix-use': {'food': 1, 'shopping': 1, 'nightlife': 1, 'groceries': 1},
                  'Service': {'parking': 100}}
        
    def prepare_model(self):
        self.get_spatial_data()
        self.get_base_pois()
        self.create_transport_network()
        self.create_sampling_grid()
        self.estimate_baseline_accessibility()
        self.prepare_interatve_analysis()
        self.save_model_params()
    
    def get_spatial_data(self):
        local_epsg = self.table_configs['local_epsg']
        self.projection=pyproj.Proj("+init=EPSG:"+local_epsg)
        self.wgs=pyproj.Proj("+init=EPSG:4326")
        cityIO_get_url=self.host+'api/table/'+self.table_name
        with urllib.request.urlopen(cityIO_get_url+'/GEOGRID') as url:
            self.geogrid=json.loads(url.read().decode())
        self.geogrid_header=self.geogrid['properties']['header']
        self.geogrid_ll=[self.geogrid['features'][i][
                'geometry']['coordinates'][0][0
                ] for i in range(len(self.geogrid['features']))]        
        self.geogrid_x, self.geogrid_y=pyproj.transform(self.wgs, self.projection,
              [self.geogrid_ll[p][0] for p in range(len(self.geogrid_ll))], 
              [self.geogrid_ll[p][1] for p in range(len(self.geogrid_ll))])
        self.geogrid_xy=[[self.geogrid_x[i], self.geogrid_y[i]] for i in range(len(self.geogrid_x))]
        
    def get_base_pois(self):
        print('Getting OSM data')

        osm_amenities=json.load(open(self.osm_config_file_path))['osm_pois']
        tags_to_include=self.table_configs['access_osm_pois']
        
        tags={t: osm_amenities[t] for t in tags_to_include}
        # To get all amenity data
        bounds_all=self.table_configs['bboxes']['amenities']
        self.base_amenities=get_osm_amenies(bounds_all, tags, self.wgs, self.projection)
        
        self.scalers=self.table_configs['scalers']
        
        # get zonal POI data (eg. housing per census tract)
        if self.table_configs['access_zonal_pois']:
            self.zones = json.load(open(self.zones_path))
            
    def create_transport_network(self):
        print('Building the base transport network')
        self.edges=pd.read_csv(self.ua_edges_path)
        self.nodes=pd.read_csv(self.ua_nodes_path)   
        
        nodes_lon=self.nodes['x'].values
        nodes_lat=self.nodes['y'].values
        self.nodes_x, self.nodes_y= pyproj.transform(self.wgs, self.projection,nodes_lon, nodes_lat)
        kdtree_base_nodes=spatial.KDTree(np.column_stack((self.nodes_x, self.nodes_y)))
        
        self.graph=nx.DiGraph()
        for i, row in self.edges.iterrows():
            self.graph.add_edge(row['from_int'], row['to_int'], weight=row['weight'])
          
        self.all_poi_types=[tag for tag in self.base_amenities] + self.table_configs['access_zonal_pois']
        assert(all(poi in self.scalers for poi in self.all_poi_types))
        self.pois_at_base_nodes={n: {t:0 for t in self.all_poi_types} for n in self.graph.nodes} 
        
        print('Finding closest node to each base POI')            
        # associate each amenity with its closest node in the base network
        for tag in self.base_amenities:
            for ai in range(len(self.base_amenities[tag]['x'])):
                nearest_node=self.nodes.iloc[kdtree_base_nodes.query(
                        [self.base_amenities[tag]['x'][ai],
                        self.base_amenities[tag]['y'][ai]])[1]]['id_int']
                self.pois_at_base_nodes[nearest_node][tag]+=1
        if self.table_configs['access_zonal_pois']:
            for f in self.zones['features']:
                centroid_xy=pyproj.transform(self.wgs, self.projection,f['properties']['centroid'][0], 
                                             f['properties']['centroid'][1])
                distance, nearest_node_ind=kdtree_base_nodes.query(centroid_xy)
                nearest_node=self.nodes.iloc[nearest_node_ind]['id_int']
                if distance<1000: #(because some zones are outside the network area)
                    for poi_type in self.table_configs['access_zonal_pois']:
                        if poi_type in f['properties']:
                            self.pois_at_base_nodes[nearest_node][poi_type]+=f['properties'][poi_type]        
        # Add links for the new network defined by the interactive area  
        #print('Adding dummy links for the grid network') 
        interactive_meta_cells={i:i for i in range(len(self.geogrid['features']))}
        
        self.createGridGraphs(interactive_meta_cells, 
                               kdtree_base_nodes)
        
    def createGridGraphs(self, interactive_meta_cells,
                         kd_tree_nodes, dist_thresh=100):
        """
        returns new networks including roads around the cells
        """
    #    create graph internal to the grid
    #    graph.add_nodes_from('g'+str(n) for n in range(len(grid_coords_xy)))
        n_links_to_real_net=0
        nrows, ncols=self.geogrid_header['nrows'], self.geogrid_header['ncols']
        cell_size=self.geogrid_header['cellSize']
        for c in range(ncols):
            for r in range(nrows):
                cell_num=r*ncols+c
                if cell_num in interactive_meta_cells: # if this is an interactive cell
                    # if close to any real nodes, make a link
                    dist_to_closest, closest_ind=kd_tree_nodes.query(self.geogrid_xy[cell_num], k=1)
                    if dist_to_closest<dist_thresh:
                        n_links_to_real_net+=1
                        closest_node_id=self.nodes.iloc[closest_ind]['id_int']
                        self.graph.add_edge('g'+str(cell_num), closest_node_id, weight=dist_to_closest/self.dummy_link_speed_met_min)
                        self.graph.add_edge(closest_node_id, 'g'+str(cell_num), weight=dist_to_closest/self.dummy_link_speed_met_min)                   
                    # if not at the end of a row, add h link
                    if not c==self.geogrid_header['ncols']-1:
                        self.graph.add_edge('g'+str(r*ncols+c), 'g'+str(r*ncols+c+1), weight=cell_size/self.dummy_link_speed_met_min)
                        self.graph.add_edge('g'+str(r*ncols+c+1), 'g'+str(r*ncols+c), weight=cell_size/self.dummy_link_speed_met_min)
                    # if not at the end of a column, add v link
                    if not r==nrows-1:
                        self.graph.add_edge('g'+str(r*ncols+c), 'g'+str((r+1)*ncols+c), weight=cell_size/self.dummy_link_speed_met_min)
                        self.graph.add_edge('g'+str((r+1)*ncols+c), 'g'+str(r*ncols+c), weight=cell_size/self.dummy_link_speed_met_min)
                            
       
    def create_sampling_grid(self):
        col_margin_left=self.table_configs['sampling_grid']['col_margin_left']
        row_margin_top=self.table_configs['sampling_grid']['row_margin_top']
        cell_width=self.table_configs['sampling_grid']['cell_width']
        cell_height=self.table_configs['sampling_grid']['cell_height']
        stride=self.table_configs['sampling_grid']['stride']
        dXdCol=np.array([self.geogrid_x[1]-self.geogrid_x[0], self.geogrid_y[1]-self.geogrid_y[0]])
        dXdRow=np.array([dXdCol[1], -dXdCol[0]]) # rotate the vector 90 degrees
        grid_origin=np.array([self.geogrid_x[0], self.geogrid_y[0]])
        sample_points_origin=grid_origin-row_margin_top*dXdRow-col_margin_left*dXdCol
        sample_points=np.array([sample_points_origin+stride*j*dXdCol+stride*i*dXdRow for i in range(
            int(cell_height/stride)) for j in range(int(cell_width/stride))])            
        self.sample_x, self.sample_y= list(sample_points[:,0]), list(sample_points[:,1])
        self.sample_lons, self.sample_lats=pyproj.transform(self.projection,self.wgs, 
                                                            self.sample_x, self.sample_y)
        
    def estimate_baseline_accessibility(self):
        print('Baseline Accessibility for sample nodes and grid nodes') 
        all_nodes_ids, all_nodes_xy=[], []
        for ind_node in range(len(self.nodes_x)):
            all_nodes_ids.append(self.nodes.iloc[ind_node]['id_int'])
            all_nodes_xy.append([self.nodes_x[ind_node], self.nodes_y[ind_node]])
        for ind_grid_cell in range(len(self.geogrid_xy)):
            all_nodes_ids.append('g'+str(ind_grid_cell))
            all_nodes_xy.append(self.geogrid_xy[ind_grid_cell])
        
        kdtree_all_nodes=spatial.KDTree(np.array(all_nodes_xy))
        
        # add the virtual links between sample points and closest nodes
        MAX_DIST_VIRTUAL=30
        all_sample_node_ids=[]
        for p in range(len(self.sample_x)):
            all_sample_node_ids.append('s'+str(p))
            self.graph.add_node('s'+str(p))
            distance_to_closest, closest_nodes=kdtree_all_nodes.query([self.sample_x[p], self.sample_y[p]], 5)
            for candidate in zip(distance_to_closest, closest_nodes):
                if candidate[0]<MAX_DIST_VIRTUAL:
                    close_node_id=all_nodes_ids[candidate[1]]
                    self.graph.add_edge('s'+str(p), close_node_id, 
                                        weight=candidate[0]/(self.dummy_link_speed_met_min))
        
        
        # for each sample node, create an isochrone and count the amenities of each type        
        self.sample_nodes_acc_base={str(n): {poi_type:0 for poi_type in self.all_poi_types} for n in range(len(self.sample_x))} 
        for sn in self.sample_nodes_acc_base:
            if sn%200==0:
                print('{} of {} sample nodes'.format(sn, len(self.sample_nodes_acc_base)))
            isochrone_graph=nx.ego_graph(self.graph, 's'+str(sn), radius=self.radius, center=True, 
                                         undirected=False, distance='weight')
            reachable_real_nodes=[n for n in isochrone_graph.nodes if n in self.pois_at_base_nodes]
            for poi_type in self.all_poi_types:
                self.sample_nodes_acc_base[sn][poi_type]=sum([self.pois_at_base_nodes[reachable_node][poi_type] 
                                                    for reachable_node in reachable_real_nodes])   
            
            
        # same for geogrid nodes
        self.grid_nodes_acc_base={str(n): {poi_type:0 for poi_type in self.all_poi_types} for n in range(len(self.geogrid_xy))} 
        for gn in self.grid_nodes_acc_base:
            if gn%200==0:
                print('{} of {} geogrid nodes'.format(gn, len(self.grid_nodes_acc_base)))
            isochrone_graph=nx.ego_graph(self.graph, 'g'+str(gn), radius=self.radius, center=True, 
                                         undirected=False, distance='weight')
            reachable_real_nodes=[n for n in isochrone_graph.nodes if n in self.pois_at_base_nodes]
            for poi_type in self.all_poi_types:
                self.grid_nodes_acc_base[gn][poi_type]=sum([self.pois_at_base_nodes[reachable_node][poi_type] 
                                                    for reachable_node in reachable_real_nodes]) 
    def prepare_interatve_analysis(self):
        print('Preparing for interactve updates. May take a few minutes.') 
        rev_graph=self.graph.reverse()
        # find the sample nodes affected by each interactive grid cell
        self.affected_sample_nodes={} # to create the geojson
        self.affected_grid_nodes={} # to get the average accessibility. eg. from all housing cells
        for gi in range(len(self.geogrid_xy)):
            if gi%200==0:
                print('{} of {} geogrid nodes'.format(gi, len(self.geogrid_xy)))
            a_node='g'+str(gi)
            affected_nodes=nx.ego_graph(rev_graph, a_node, radius=self.radius, center=True, 
                                        undirected=False, distance='weight').nodes
            self.affected_grid_nodes[gi]=[n for n in affected_nodes if 'g' in str(n)]
            self.affected_sample_nodes[gi]=[n for n in affected_nodes if 's' in str(n)]
        self.from_employ_pois=['housing']
        self.from_housing_pois=[poi for poi in self.all_poi_types if not poi=='housing']
            
    def save_model_params(self):       
        output={'sample_nodes_acc_base': self.sample_nodes_acc_base,
                'grid_nodes_acc_base': self.grid_nodes_acc_base,
                'pois_per_lu': self.pois_per_lu,
                'all_poi_types': self.all_poi_types,
                'from_employ_pois': self.from_employ_pois,
                'from_housing_pois': self.from_housing_pois,
                'sample_lons': self.sample_lons,
                'sample_lats': self.sample_lats,
                'scalers': self.scalers,
                'affected_grid_nodes': self.affected_grid_nodes,
                'affected_sample_nodes': self.affected_sample_nodes}        
        json.dump(output, open(self.params_path, 'w'))
        
    def load_module(self):
        try:
            params=json.load(open(self.params_path))
            self.sample_nodes_acc_base=params['sample_nodes_acc_base']
            self.grid_nodes_acc_base=params['grid_nodes_acc_base']
            self.pois_per_lu=params['pois_per_lu']
            self.all_poi_types=params['all_poi_types']
            self.from_employ_pois=params['from_employ_pois']
            self.from_housing_pois=params['from_housing_pois']
            self.sample_lons=params['sample_lons']
            self.sample_lats=params['sample_lats']
            self.scalers=params['scalers']
            self.affected_grid_nodes=params['affected_grid_nodes']
            self.affected_sample_nodes=params['affected_sample_nodes']
        except:
            print('Parameters have not yet been saved. Preparing the model')
            self.prepare_model()
            
    def create_access_geojson(self, grids):
        """
        takes lists of x and y coordinates and a list containing the accessibility 
        score for each point and tag category
        """
           
        output_geojson={
         "type": "FeatureCollection",
         "features": []
        }    
        for i in range(len(self.sample_lons)):
            geom={"type": "Point","coordinates": [self.sample_lons[i],self.sample_lats[i]]}
            props={t: np.power(grids[i][t]/self.scalers[t], 1) for t in self.all_poi_types}
            feat={
             "type": "Feature",
             "properties": props,
             "geometry": geom
            }
            output_geojson["features"].append(feat) 
        return output_geojson
    
    def return_indicator(self, geogrid_data):
        sample_nodes_acc={n: {t:self.sample_nodes_acc_base[n][t] for t in self.all_poi_types
                              } for n in self.sample_nodes_acc_base}
        grid_nodes_acc={n: {t:self.grid_nodes_acc_base[n][t] for t in self.all_poi_types
                              } for n in self.grid_nodes_acc_base}
        for gi, cell_data in enumerate(geogrid_data):
#            if not type(usage)==list:
#                print('Usage value is not a list: '+str(usage))
#                usage=[-1,-1]
            this_grid_lu=cell_data['name']
            if this_grid_lu in self.pois_per_lu:
                sample_nodes_to_update=self.affected_sample_nodes[str(gi)]
                grid_nodes_to_update=self.affected_grid_nodes[str(gi)]
                for poi in self.pois_per_lu[this_grid_lu]:
                    if poi in self.all_poi_types:
                        n_to_add=self.pois_per_lu[this_grid_lu][poi]
                        if n_to_add<1:
                            if random.uniform(0,1)<=n_to_add:
                                n_to_add=1
                            else:
                                n_to_add=0
                        for n in sample_nodes_to_update:
                            sample_nodes_acc[n.split('s')[1]][poi]+=n_to_add
                        for n in grid_nodes_to_update:
                            grid_nodes_acc[n.split('g')[1]][poi]+=n_to_add
        result=[]
        # TODO: should use baseline land uses as well as added ones
        for poi in self.from_employ_pois:
            this_indicator_value=np.mean([grid_nodes_acc[str(g)][poi
                       ] for g in range(len(geogrid_data)
                        ) if geogrid_data[g]['name'] in ['Office Tower', 'Mix-use']])/self.scalers[poi]
            result.append({'name': 'Access to {}'.format(poi), 'value': this_indicator_value})
        for poi in self.from_housing_pois:
            this_indicator_value=np.mean([grid_nodes_acc[str(g)][poi
                       ] for g in range(len(geogrid_data)
                        ) if geogrid_data[g]['name'] in ['Residential', 'Mix-use']])/self.scalers[poi]
            result.append({'name': 'Access to {}'.format(poi), 'value': this_indicator_value})  
        for r in result:
            r['value']=min(1, r['value'])              
#        grid_geojson=self.create_access_geojson(sample_nodes_acc)
        return result
    
        
        
def main():
    P= ProxIndicator(name='proximity')
    H = Handler('corktown', quietly=False)
    H.add_indicator(P)
    
    print(H.geogrid_data())

    print(H.list_indicators())
    print(H.update_package())

    H.listen()


if __name__ == '__main__':
	main()        

        