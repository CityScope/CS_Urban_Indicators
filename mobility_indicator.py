#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Apr  3 12:11:11 2020

@author: doorleyr
"""

from toolbox import Handler, Indicator
#from sklearn.neighbors import KNeighborsRegressor
from sklearn.linear_model import LinearRegression
import numpy as np
import json

class MobilityIndicator(Indicator):
    def setup(self,*args,**kwargs):
        self.category='numeric'
        self.table_name=kwargs['table_name']
        self.train_data_loc='./tables/{}/mobility_sim_output.json'.format(self.table_name)
        
        
    def train(self):
        data=json.load(open(self.train_data_loc))
        x_off, x_resi, y_co2=data['x_off'], data['x_resi'], data['y_co2']
        X=np.array([(x_off[i]-x_resi[i]) for i in range(len(x_resi))]).reshape(-1, 1)
        y_co2=data['y_co2']
#        neigh = LinearRegression(n_neighbors=3)
        lm = LinearRegression()
        co2_model=lm.fit(X, y_co2)
        self.co2_model=co2_model
        self.co2_min=3.5
        self.co2_max=5
        
        
    def predict_co2(self, n_resi, n_office):
        co2=self.co2_model.predict(np.array(n_office-n_resi).reshape(1,-1))[0]
        return max(0, min(1,(co2-self.co2_min)/(self.co2_max-self.co2_min)))
        
    def load_module(self):
        print('loading')
        self.train()
            
    def return_indicator(self, geogrid_data):
        n_resi=sum([1 for g in geogrid_data if g['name'] =='Residential'])
        n_off=sum([1 for g in geogrid_data if 'Office' in g['name']])
        print(n_resi)
        print(n_off)
        co2_normalised=self.predict_co2(n_resi, n_off)
        print(co2_normalised)
        return [{'name': 'Sustainable Mobility', 'value': 1-co2_normalised}]
        
    
def main():
    M= MobilityIndicator(name='mobility',  table_name='corktown')
    H = Handler('corktown', quietly=False)
    H.add_indicator(M)
    
    print(H.geogrid_data())

    print(H.list_indicators())
    print(H.update_package())

    H.listen()


if __name__ == '__main__':
	main()        
