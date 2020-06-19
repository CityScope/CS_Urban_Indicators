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
import pandas as pd
import matplotlib.pyplot as plt
from indicator_tools import fit_rf_regressor
import pickle

class MobilityIndicator(Indicator):
    def setup(self,*args,**kwargs):
        self.fitted_co2_model_object_loc='./tables/corktown/fitted_co2_model.p'
        self.fitted_pa_model_object_loc='./tables/corktown/fitted_pa_model.p'
        self.category='numeric'
        self.table_name=kwargs['table_name']
        self.train_data_loc='./tables/{}/mobility_sim_output.json'.format(self.table_name)
        
        
    def train(self):
        data=json.load(open(self.train_data_loc))
        X_df=pd.DataFrame(data['X'])
        Y_df=pd.DataFrame(data['Y'])
        all_df=pd.concat([X_df, Y_df], axis=1)
#        numerical_cols=[col for col in X_df.columns]
        static_types=[k for k in self.types_def if k not in self.int_types_def]
        numerical_cols=[col for col in X_df.columns if col not in static_types]
#        neigh = LinearRegression(n_neighbors=3)
        self.co2_model, self.co2_model_features= fit_rf_regressor(
                all_df, cat_cols=[], 
                numerical_cols=numerical_cols, 
                y_col='avg_co2', n_estimators=50)
        self.pa_model, self.pa_model_features= fit_rf_regressor(
                all_df, cat_cols=[], 
                numerical_cols=numerical_cols, 
                y_col='delta_f_physical_activity_pp', n_estimators=50)
        co2_model_object={'model': self.co2_model, 'features': self.co2_model_features,
#              'max': self.max_co2, 'min': self.min_co2
              }
        pa_model_object={'model': self.pa_model, 'features': self.pa_model_features,
#              'max': self.max_pa, 'min': self.min_pa
              }
        pickle.dump(co2_model_object, open(self.fitted_co2_model_object_loc, 'wb'))
        pickle.dump(pa_model_object, open(self.fitted_pa_model_object_loc, 'wb'))
       
    def normalised_prediction(self, model, X_in, y_max, y_min):
        y_pred=model.predict(X_in)[0]
#        print(y_pred)
        return {'raw':y_pred, 'norm': max(0, min(1,(y_pred-y_min)/(y_max-y_min)))}
        
    def load_module(self):
        print('loading')
        try:
            fitted_co2_model=pickle.load(open(self.fitted_co2_model_object_loc, 'rb'))
            self.co2_model=fitted_co2_model['model']
            self.co2_model_features=fitted_co2_model['features']  
#            self.max_co2=fitted_co2_model['max'] 
#            self.min_co2=fitted_co2_model['min'] 
            fitted_pa_model=pickle.load(open(self.fitted_pa_model_object_loc, 'rb'))
            self.pa_model=fitted_pa_model['model']
            self.pa_model_features=fitted_pa_model['features']  
#            self.max_pa=fitted_pa_model['max'] 
#            self.min_pa=fitted_pa_model['min'] 
        except:
            print('Model not yet trained. Training now')
            self.train()            
        self.min_co2=5
        self.max_co2=12
        self.min_pa=0
        self.max_pa=0.004
        
            
    def return_indicator(self, geogrid_data, future_mobility=1):
        X_co2, X_pa=[], []
        floor_counts={}
        for cell in geogrid_data:
            height=cell['height']
            if isinstance(height, list):
                height=height[-1]
            if cell['name'] in floor_counts:                
                floor_counts[cell['name']]+=height
            else:
                floor_counts[cell['name']]=height
        for feat in self.co2_model_features:
            if feat=='future_mobility':
                x=future_mobility
            elif feat in floor_counts:
                x=floor_counts[feat]
            else:
                x=0               
            X_co2.append(x)
        for feat in self.pa_model_features:
            if feat=='future_mobility':
                x=future_mobility
            elif feat in floor_counts:
                x=floor_counts[feat]
            else:
                x=0               
            X_pa.append(x)
#        print(self.co2_model_features)
        co2=self.normalised_prediction(self.co2_model, np.array(X_co2).reshape(1, -1), 
                                            self.max_co2, self.min_co2)
        pa=self.normalised_prediction(self.pa_model, np.array(X_pa).reshape(1, -1), 
                                           self.max_pa, self.min_pa)
        self.value_indicators=[{'name': 'Mobility CO2 Performance', 'value': 1-co2['norm'], 
                 'raw_value':co2['raw'],'viz_type': self.viz_type, 'units': 'kg/day'},
                {'name': 'Mobility Health Impacts', 'value': pa['norm'], 
                 'raw_value':pa['raw'], 'viz_type': self.viz_type, 'units': 'mortality/year'}]
        return self.value_indicators
        
    
def main():
    M= MobilityIndicator(name='mobility',  table_name='corktown')
    H = Handler('corktown', quietly=False)
    H.add_indicator(M)
    
    geogrid_data=H.get_geogrid_data()
    
    M.return_indicator(geogrid_data)

#    print(H.list_indicators())
#    print(H.update_package())

    H.listen()


if __name__ == '__main__':
	main()        
