#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Mar 31 17:48:36 2020

@author: doorleyr
"""
from statistics import mean

from toolbox import Handler, Indicator
from proximity_indicator import ProxIndicator
from random_indicator import RandomIndicator

class AggregateIndicator(Indicator):
    def setup(self,*args,**kwargs):
        self.name=kwargs['name']
        self.indicators_to_aggregate=kwargs['indicators_to_aggregate']
        self.agg_fun=kwargs["agg_fun"]
    
    def return_indicator(self, geogrid_data):
        values_to_agg=[]
        for agg_obj in self.indicators_to_aggregate:
            for indicator_value in agg_obj['indicator'].value_indicators:
                if indicator_value['name'] in agg_obj['names']:
                    values_to_agg.extend([indicator_value['value']])
        return [{'name': self.name, 'value': self.agg_fun(values_to_agg)}]
    

def main():
    placeholder=RandomIndicator()
    P= ProxIndicator(name='proximity',  category_in='access', table_name='corktown')
    aggregation=[{'indicator': P, 'names': ['Access to education', 'Access to parks']}]
    Social=AggregateIndicator(name='Social Well-Being',
                              indicators_to_aggregate=aggregation, 
                              agg_fun=mean)    
    H = Handler('corktown', quietly=False)
    H.add_indicator(placeholder)
    H.add_indicator(P)
    H.add_indicator(Social)
    
    print(H.geogrid_data())

    print(H.list_indicators())
    print(H.update_package())

    H.listen()
    
if __name__ == '__main__':
	main()