#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Mar 31 17:48:36 2020

@author: doorleyr
"""
import pandas as pd

from toolbox import Handler, Indicator
from innovation_indicator import InnoIndicator

class EconomicIndicator(Indicator):
    def setup(self,*args,**kwargs):
        self.innovation_indicator=kwargs['innovation_indicator']
        salary_data=pd.read_excel('./tables/innovation_data/national_M2019_dl.xlsx')
#        salary_data=salary_data.set_index('occ_code')
        self.code_to_salary={salary_data.iloc[i]['occ_code']: salary_data.iloc[i]['a_mean']
            for i in range(len(salary_data))}
    def return_indicator(self, geogrid_data):
        industry_composition = self.innovation_indicator.grid_to_industries(geogrid_data)
        worker_composition   = self.innovation_indicator.industries_to_occupations(industry_composition)
        for occ_code in worker_composition:
            total_salary=0
            denom=0            
            padded_occ_code=occ_code.ljust(7, '0')
            if padded_occ_code in self.code_to_salary:
                salary=self.code_to_salary[padded_occ_code]
            else:
                padded_occ_code=occ_code[:-1].ljust(7, '0')
                salary=self.code_to_salary[padded_occ_code]
            weight=worker_composition[occ_code]
            total_salary+=salary*weight
            denom+=weight
#            print('{} : {}'.format(padded_occ_code,self.code_to_salary[padded_occ_code]))
        avg_salary=total_salary/denom
        return min(1, avg_salary/100000)

def main():
    I = InnoIndicator()
    E = EconomicIndicator(innovation_indicator=I)
    
    H = Handler('corktown', quietly=False)
    H.add_indicator(I)
    H.add_indicator(E)
    
    coefs = I.train()
    print(coefs)
    print(E.return_indicator(H.geogrid_data()))
    
if __name__ == '__main__':
	main()