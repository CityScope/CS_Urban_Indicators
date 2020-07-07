#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Apr  3 12:11:11 2020
Prediction model Based on microdata from 
https://www.eia.gov/consumption/


Usage codes
'01' = 'Vacant'
'02' = 'Office'
'04' = 'Laboratory'
'05' = 'Nonrefrigerated warehouse'
'06' = 'Food sales'
'07' = 'Public order and safety'
'08' = 'Outpatient health care'
'11' = 'Refrigerated warehouse'
'12' = 'Religious worship'
'13' = 'Public assembly'
'14' = 'Education'
'15' = 'Food service'
'16' = 'Inpatient health care'
'17' = 'Nursing'
'18' = 'Lodging'
'23' = 'Strip shopping mall'
'24' = 'Enclosed mall'
'25' = 'Retail other than mall'
'26' = 'Service'
'91' = 'Other'

@author: doorleyr
"""

from toolbox import Handler, Indicator
#from sklearn.ensemble import RandomForestRegressor
#from sklearn.model_selection import train_test_split, RandomizedSearchCV
import numpy as np
import json
import pandas as pd
from pprint import pprint
import pickle
import urllib
import matplotlib.pyplot as plt
from indicator_tools import fit_rf_regressor, flatten_grid_cell_attributes
import operator

pba_to_lbcs={
        1: '9000',
        2: '2300',
        4: '3100',
        5: '3100',
        6: '2500',
        7: '4200',
        8: '4500',
        11: '3100',
        12: '6600',
        13: '6600',
        14: '4100',
        15: '2200',
        16: '4500',
        17: '4500',
        18: '1200',
        23: '2100',
        24: '2100',
        25: '2100',
        26: '4300', # service = utilities?
        91: '9000'
        }
def year_con_to_age(year_con, base_year):
    if year_con==995:
        return 100
    else:
        return base_year-year_con
#def fit_rf_regressor(df, cat_cols, numerical_cols, y_col):
#    features=[c for c in numerical_cols]
#    for col in cat_cols:        
#        new_dummies=pd.get_dummies(df[col], prefix=col, drop_first=True)
#        df=pd.concat([df, new_dummies], axis=1)
#        features.extend(new_dummies.columns.tolist())   
#    X=np.array(df[features])
#    y=np.array(df[y_col])
#    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=1)
#    rfr = RandomForestRegressor(random_state = 0, n_estimators=100)    
##    pprint(rfr.get_params())
#    
## =============================================================================
##     Randomised Grid Search for best hyper-parameters
## =============================================================================
## Number of features to consider at every split
#    max_features = ['auto', 'sqrt']
#    # Maximum number of levels in tree
#    max_depth = [int(x) for x in np.linspace(10, 110, num = 11)]
#    max_depth.append(None)
#    # Minimum number of samples required to split a node
#    min_samples_split = [2, 5, 10]
#    # Minimum number of samples required at each leaf node
#    min_samples_leaf = [1, 2, 4]
#    # Method of selecting samples for training each tree
#    bootstrap = [True, False]
#    # Create the random grid
#    random_grid = {
#                   'max_features': max_features,
#                   'max_depth': max_depth,
#                   'min_samples_split': min_samples_split,
#                   'min_samples_leaf': min_samples_leaf,
#                   'bootstrap': bootstrap}
#
#    # Create the random search object
#    rfr_random_search = RandomizedSearchCV(estimator = rfr, param_distributions = random_grid,
#                                   n_iter = 200, cv = 5, verbose=1, random_state=0, 
#                                   refit=True)
#    
#    rfr_random_search.fit(X_train, y_train)
#    rfr_winner=rfr_random_search.best_estimator_
#    best_params=rfr_random_search.best_params_
#    importances = rfr_winner.feature_importances_
#    std = np.std([tree.feature_importances_ for tree in rfr_winner.estimators_],
#                 axis=0)
#    indices = np.argsort(importances)[::-1]
#    print("Feature ranking:")
#    
#    for f in range(len(features)):
#        print("%d. %s (%f)" % (f + 1, features[indices[f]], importances[indices[f]]))
#    
#    # Plot the feature importances of the forest
#    plt.figure(figsize=(16, 9))
#    plt.title("Feature importances")
#    plt.bar(range(len(features)), importances[indices],
#           color="r", yerr=std[indices], align="center")
#    plt.xticks(range(len(features)), [features[i] for i in indices], rotation=90, fontsize=15)
#    plt.xlim([-1, len(features)])
#    plt.show()
#    
#    pred_test=rfr_winner.predict(X_test)
#    plt.figure(figsize=(16, 9))
#    plt.scatter(y_test, pred_test)
#    plt.xlabel("Actual")
#    plt.ylabel("Predicted")
#    plt.show()
    
    
class BuildingsIndicator(Indicator):
    def setup(self,host='https://cityio.media.mit.edu/', *args,**kwargs):
        self.category='numeric'
        self.table_name=kwargs['table_name']
        self.fitted_model_object_loc='./tables/buildings_data/fitted_comm_model.p'
        self.train_data_loc='./tables/buildings_data'
        GEOGRID_loc='{}api/table/{}/GEOGRID'.format(host, self.table_name)
        with urllib.request.urlopen(GEOGRID_loc) as url:
            geogrid=json.loads(url.read().decode())
        self.cell_size=geogrid['properties']['header']['cellSize']
        self.max_result_per_worker=100000
        self.min_result_per_worker=50000
                
    def train(self):
        comm_data=pd.read_csv(self.train_data_loc+'/2012_public_use_data_aug2016.csv')
        resi_data=pd.read_csv(self.train_data_loc+'/recs2015_public_v4.csv')
        # fit a model to predict energy/sqft/year based on floors, num people, usage, year
        # NFLOOR: 994 = 15-25, 995 = >25
        # NWKER: num employees
        # PBA: principal building activity.
        # SQFT
        # MFBTU: major fuel consumption (thous btus) = sum of all consumptions
        # ELBTU: electricity consumption (thous btus)
        comm_data.loc[comm_data['NFLOOR']==994, 'NFLOOR']=20
        comm_data.loc[comm_data['NFLOOR']==995, 'NFLOOR']=30
        comm_data['AGE']=comm_data.apply(lambda row: row['YRCONC'])
        comm_data['LBCS']=comm_data.apply(lambda row: 
            pba_to_lbcs[row['PBA']], axis=1)
        comm_data['SQM']=0.092*comm_data['SQFT']
            
        # build training dataset
        comm_model_df=comm_data[['NFLOOR','LBCS','NWKER', 'SQM', 'MFBTU', 'AGE']]
        comm_model_df=comm_model_df.loc[~comm_model_df['MFBTU'].isnull()]
        self.comm_model, self.comm_model_features=fit_rf_regressor(df=comm_model_df, numerical_cols=['NFLOOR', 'SQM', 'AGE'],
                                    cat_cols=['LBCS'], y_col='MFBTU') 
        # get max and min, nimalised by num workers
        comm_model_df=comm_model_df.loc[comm_model_df['NWKER']>0]
#        self.max_result_per_worker=max(comm_model_df['MFBTU']/comm_model_df['NWKER'])
#        self.min_result_per_worker=min(comm_model_df['MFBTU']/comm_model_df['NWKER'])
        model_object={'model': self.comm_model, 'features': self.comm_model_features,
                      'max': self.max_result_per_worker, 'min': self.min_result_per_worker}
        pickle.dump(model_object, open(self.fitted_model_object_loc, 'wb'))
               
        
    def load_module(self):
        print('loading')
        try:
            fitted_comm_model=pickle.load(open(self.fitted_model_object_loc, 'rb'))
            self.comm_model=fitted_comm_model['model']
            self.comm_model_features=fitted_comm_model['features']  
#            self.max_result_per_worker=fitted_comm_model['max'] 
#            self.min_result_per_worker=fitted_comm_model['min'] 
        except:
            print('Model not yet trained. Training now')
            self.train()
                   
    def return_indicator(self, geogrid_data):
        comm_blds_list=[]
        comm_model_lbcs=[feat.split('_')[1] for feat in self.comm_model_features if 'LBCS' in feat]
        for grid_cell in geogrid_data:
            height=grid_cell['height']
            if isinstance(height, list):
                height=height[-1]
            if ((height>0) and (grid_cell['name'] in self.types_def) and (not grid_cell['name'] =='Park')):
                # if there is actually a building here
                this_bld={feat:0 for feat in self.comm_model_features}
    #            if grid_cell["name"] in ['Office', 'Office Tower', 'Mix-Use', 'Retail']:                
    #                this_bld['LBCS_2300']=1
                all_lbcs=flatten_grid_cell_attributes(
                            type_def=self.types_def[grid_cell['name']], height=grid_cell['height'],
                            attribute_name='LBCS', area_per_floor=self.geogrid_header['cellSize']**2)
                all_people=sum(all_lbcs[c] for c in all_lbcs)
                if len(all_lbcs)>0:
                    # if there is any LBCS code
                    main_lbcs=max(all_lbcs.items(), key=operator.itemgetter(1))[0]
                    main_lbcs_2_digit=main_lbcs[:2]+'00'
                    this_bld['LBCS_{}'.format(str(main_lbcs_2_digit))]=1
                    this_bld['NFLOOR']=height
                    this_bld['SQM']=self.cell_size*self.cell_size*this_bld['NFLOOR']
                    if main_lbcs_2_digit in comm_model_lbcs:  
                        # if the main use is commercial
                        this_bld['NWKER']=all_people
                        comm_blds_list.append(this_bld)
        if len(comm_blds_list)>0:
            X_df=pd.DataFrame.from_dict(comm_blds_list)
            X=X_df[self.comm_model_features]
            X_df['pred']=self.comm_model.predict(X)
#            X_df['energy_per_worker']=X_df['pred']/X_df['NWKER']
            avg_energy_per_worker=sum(X_df['pred'])/sum(X_df['NWKER'])
            norm_avg_energy_per_worker=(avg_energy_per_worker-self.min_result_per_worker
                                        )/(self.max_result_per_worker-self.min_result_per_worker)
            norm_avg_energy_per_worker=1-max(0, min(1, norm_avg_energy_per_worker)) 
        else:
            norm_avg_energy_per_worker=0
            avg_energy_per_worker=0
        self.value_indicators=[{'name': 'Buildings Energy Performance', 'value': norm_avg_energy_per_worker,
                                'raw_value': avg_energy_per_worker, 'units': '\'000 Btu/person year',
                'viz_type': self.viz_type},
#                {'name': 'Residential Energy Performance', 'value': comm_energy_score,
#                'viz_type': self.viz_type}
                ]
        return self.value_indicators

def main():
#if True:
    B= BuildingsIndicator(name='buildings',  table_name='corktown')
    H = Handler('corktown', quietly=False)
    H.add_indicator(B)
#    
#    print(H.geogrid_data())
#
#    print(H.list_indicators())
#    print(H.update_package())
#
    H.listen()


if __name__ == '__main__':
	main()        
