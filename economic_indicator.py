#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Mar 31 17:48:36 2020

@author: doorleyr
"""
import pandas as pd
import json

from toolbox import Handler, Indicator
from indicator_tools import EconomicIndicatorBase

# def load_output_per_employee():
#     industry_ouput=pd.read_csv('./tables/innovation_data/USA_industry_ouput.csv', skiprows=1)
#     industry_ouput=industry_ouput.set_index('2017 NAICS code')
#     output_per_employee_by_naics={}
#     for ind_row, row in industry_ouput.iterrows():
#         output_per_emp=row['Sales, value of shipments, or revenue ($1,000)']/row['Number of employees']
#         if '-' in ind_row:
#             from_code, to_code=ind_row.split('-')
#             if '(' in to_code:
#                 to_code=to_code.split('(')[0]
#             for code in range(int(from_code), int(to_code)+1):
#                 output_per_employee_by_naics[str(code)]=output_per_emp
#         else:
#             output_per_employee_by_naics[ind_row]=output_per_emp
# #        if '(' in ind_row:
# #            ind_row=ind_row.split('(')[0]
# #        output_per_employee_by_naics[ind_row]=output_per_emp
#     return output_per_employee_by_naics

# def get_baseline_employees_by_naics(table_name, table_geoids):
#     employees_by_naics={}
#     wac=pd.read_csv('./tables/{}/mi_wac_S000_JT00_2017.csv.gz'.format(table_name))
#     wac['block_group']=wac.apply(lambda row: str(row['w_geocode'])[:12], axis=1)
#     wac=wac.loc[wac['block_group'].isin(table_geoids)]
#     wac_data_full_table=wac.sum(axis=0)
#     for col in wac:
#         if 'CNS' in col:
#             naics=wac_cns_to_naics[col]
#             if '-' in naics:
#                 naics=naics.split('-')[0]
#             employees_by_naics[naics]=wac_data_full_table[col]
#     return employees_by_naics

   
# wac_cns_to_naics={
#         'CNS01' : '11',
#         'CNS02' : '21', 
#         'CNS03' : '22',
#         'CNS04' : '23',
#         'CNS05' : '31-33',
#         'CNS06' : '42',
#         'CNS07' : '44-45',
#         'CNS08' : '48-49',
#         'CNS09' : '51',
#         'CNS10' : '52',
#         'CNS11' : '53',
#         'CNS12' : '54',
#         'CNS13' : '55',
#         'CNS14' : '56' ,
#         'CNS15' : '61',
#         'CNS16' : '62',
#         'CNS17' : '71',
#         'CNS18' : '72',
#         'CNS19' : '81',
#         'CNS20' : '92' }
            
class EconomicIndicator(EconomicIndicatorBase):
    def setup(self,*args,**kwargs):
        self.table_name= kwargs['table_name']
        # self.grid_to_industries=kwargs['grid_to_industries']
        # self.industries_to_occupations=kwargs['industries_to_occupations']
        self.name=kwargs['name']
#        sim_zones=json.load(open('./tables/{}/sim_zones.json'.format(self.table_name)))
#        table_geoids=[z.split('US')[1] for z in sim_zones]
#        # get the baseline num workers in district by industry NAICS code
#        self.base_industry_composition=self.get_baseline_employees_by_naics(self.table_name, table_geoids,return_data=True)
#        self.base_worker_composition=self.industries_to_occupations(self.base_industry_composition)
#
#        # self.output_per_employee_by_naics=self.load_output_per_employee(return_data=True)
        self.load_output_per_employee() #This function should load the df without the need of returning it 
        salary_data=pd.read_excel('./tables/innovation_data/national_M2019_dl.xlsx')
#        salary_data=salary_data.set_index('occ_code')
        self.code_to_salary={salary_data.iloc[i]['occ_code']: salary_data.iloc[i]['a_mean']
            for i in range(len(salary_data))}
        
    def return_indicator(self, geogrid_data):
        # add new workers to baseline workers
#        new_industry_composition = self.grid_to_industries(geogrid_data)
#        new_worker_composition   = self.industries_to_occupations(new_industry_composition)
#        all_worker_composition={k: v for k,v in self.base_worker_composition.items()}
#        for code in new_worker_composition:
#            if code in all_worker_composition:
#                all_worker_composition[code]+=new_worker_composition[code]
#            else:
#                all_worker_composition[code]=new_worker_composition[code]  
        industry_composition=self.grid_to_industries(geogrid_data)
        worker_composition   = self.industries_to_occupations(industry_composition)
        num_workers=sum([worker_composition[code] for code in worker_composition])
        num_workers_per_km_sq=num_workers/4
        avg_salary=self.get_avg_salary(worker_composition)
#        base_ouput=self.get_total_output(self.base_industry_composition)
        output=self.get_total_output(industry_composition)
        max_output=5e9
        max_workers_per_km_sq=7500
        print(output)
#        total_output=base_ouput+new_ouput
        self.value_indicators=[{'value': min(1, avg_salary/80000), 'raw_value': avg_salary, 'name': 'Average Salary', 
                 'viz_type': self.viz_type, 'units': 'USD'},
                {'value': min(1, output/(max_output)), 'name': 'Productivity', 
                 'viz_type': self.viz_type, 'raw_value': output, 'units': 'USD'},
                 {'value': min(1, num_workers_per_km_sq/max_workers_per_km_sq), 'raw_value': num_workers_per_km_sq,'name': 'Employment Density', 
                 'viz_type': self.viz_type, 'units': 'employees/sq_km'}]
        return self.value_indicators
        
#    def return_baseline(self):
#        base_ouput=self.get_total_output(self.base_industry_composition)
#        base_avg_salary=self.get_avg_salary(self.base_worker_composition)
#        return [{'value': min(1, base_avg_salary/100000), 'name': 'Average Earnings', 
#                 'viz_type': self.viz_type},
#                {'value': base_ouput, 'name': 'Industry Output', 
#                 'viz_type': self.viz_type}]
        
            
    def get_avg_salary(self, worker_composition):
        total_salary=0
        denom=0  
        for occ_code in worker_composition:          
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
        return avg_salary
    
    def get_total_output(self, industry_composition):
        total_ouput=0
        for naics in industry_composition:
            naics_2=naics[:2]
            if not naics_2 in ['11', '92']: # ignore agriculture and public order/safety
                total_ouput+=industry_composition[naics]*self.output_per_employee_by_naics[naics_2]
        return 1000*total_ouput
    
def main():
    E = EconomicIndicator(table_name='corktown',
                          name='Economic')
    
    H = Handler('corktown', quietly=False)
    H.add_indicator(E)
    
    print(E.return_baseline())
    print(E.return_indicator(H.get_geogrid_data()))
    
if __name__ == '__main__':
	main()