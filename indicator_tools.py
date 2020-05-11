#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Mar  2 11:23:12 2020

@author: doorleyr
"""
import math
import pandas as pd
import geopandas as gpd
import requests
import os
from bs4 import BeautifulSoup
from APICalls import ACSCall,patentsViewDownload,load_zipped_excel
from download_shapeData import SHAPES_PATH
from toolbox import Handler, Indicator
import pandas as pd

############
# Classes  #
############

class EconomicIndicatorBase(Indicator):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.IO_data = None
        self.output_per_employee_by_naics = None
        self.employees_by_naics = None
        self.wac_cns_to_naics={
            'CNS01' : '11',
            'CNS02' : '21', 
            'CNS03' : '22',
            'CNS04' : '23',
            'CNS05' : '31-33',
            'CNS06' : '42',
            'CNS07' : '44-45',
            'CNS08' : '48-49',
            'CNS09' : '51',
            'CNS10' : '52',
            'CNS11' : '53',
            'CNS12' : '54',
            'CNS13' : '55',
            'CNS14' : '56' ,
            'CNS15' : '61',
            'CNS16' : '62',
            'CNS17' : '71',
            'CNS18' : '72',
            'CNS19' : '81',
            'CNS20' : '92' 
        }

    def load_IO_data(self):
        '''
        Loads data on employment by industry and by occupation. 
        '''
        if self.IO_data is None:
            self.IO_data = DataLoader().load_IO_data(return_data=True)

    def grid_to_industries(self,geogrid_data):
        '''
        THIS FUNCTION SHOULD TRANSLATE BETWEEN GEOGRIDDATA TO NAICS
        '''
        industry_composition = {'424':100,'813':10,'518':30,'313':50}
        return industry_composition

    def industries_to_occupations(self,industry_composition,naicsLevel = None):
        '''
        Calculates the worker composition of the given industries.

        Parameters
        ----------
        industry_composition : dict
          NAICS codes (as strings) and number of workers per code. For example:
          industry_composition = {
                                  '424':100,
                                  '813':10,
                                  '518':30,
                                  '313':50
                                  }
        naicsLevel : int 
          NAICS level used. If not provided it will try to infer it from the data.
            
        Returns
        -------
        worker_composition : dict
          Codes of occupations (at the selected level) and number of workers working in each.
          worker_composition = {
                                '11-1': 5.482638676590663,
                                '11-2': 2.618783841892787,
                                '11-3': 4.172466727284003,
                                '11-9': 1.0466603476986416,
                                '13-1': 8.153575049183983,
                                '13-2': 2.4813093308593723,
                                '15-1': 13.41354293652867,
                                ...
                               }
        '''
        if naicsLevel is None:
            levels = list(set([len(k) for k in industry_composition]))
            if len(levels)==1:
                naicsLevel = levels[0]
            else:
                raise NameError('Unrecognized NAICS level')

        self.load_IO_data()

        IO_data = self.IO_data[self.IO_data.columns]
        IO_data['SELECTED_NAICS'] = IO_data['NAICS'].str[:naicsLevel]

        worker_composition = IO_data.groupby(['SELECTED_NAICS','SELECTED_LEVEL']).sum()[['TOT_EMP']].reset_index()
        worker_composition = worker_composition.set_index(['SELECTED_NAICS','SELECTED_LEVEL'])/worker_composition.groupby('SELECTED_NAICS').sum()[['TOT_EMP']]
        worker_composition = worker_composition.reset_index()

        industry_composition_df = pd.DataFrame(industry_composition.items(),columns=['SELECTED_NAICS','number'])
        industry_composition_df['SELECTED_NAICS'] = ('000000'+industry_composition_df['SELECTED_NAICS'].astype(str)).str[-1*naicsLevel:]

        worker_composition = pd.merge(worker_composition,industry_composition_df)
        worker_composition['TOT_EMP'] = worker_composition['TOT_EMP']*worker_composition['number']
        worker_composition = worker_composition.groupby('SELECTED_LEVEL').sum()[['TOT_EMP']].reset_index()
        worker_composition = dict(worker_composition.values)
        return worker_composition

    def get_baseline_employees_by_naics(self,table_name, table_geoids,return_data=False):
        if self.employees_by_naics is None:
            employees_by_naics={}
            wac=pd.read_csv('./tables/{}/mi_wac_S000_JT00_2017.csv.gz'.format(table_name))
            wac['block_group']=wac.apply(lambda row: str(row['w_geocode'])[:12], axis=1)
            wac=wac.loc[wac['block_group'].isin(table_geoids)]
            wac_data_full_table=wac.sum(axis=0)
            for col in wac:
                if 'CNS' in col:
                    naics=self.wac_cns_to_naics[col]
                    if '-' in naics:
                        naics=naics.split('-')[0]
                    employees_by_naics[naics]=wac_data_full_table[col]
            self.employees_by_naics = employees_by_naics
        if return_data:
            return self.employees_by_naics

    def load_output_per_employee(self,return_data=False):
        if self.output_per_employee_by_naics is None:
            industry_ouput=pd.read_csv('./tables/innovation_data/USA_industry_ouput.csv', skiprows=1)
            industry_ouput=industry_ouput.set_index('2017 NAICS code')
            output_per_employee_by_naics={}
            for ind_row, row in industry_ouput.iterrows():
                output_per_emp=row['Sales, value of shipments, or revenue ($1,000)']/row['Number of employees']
                if '-' in ind_row:
                    from_code, to_code=ind_row.split('-')
                    if '(' in to_code:
                        to_code=to_code.split('(')[0]
                    for code in range(int(from_code), int(to_code)+1):
                        output_per_employee_by_naics[str(code)]=output_per_emp
                else:
                    output_per_employee_by_naics[ind_row]=output_per_emp
            #        if '(' in ind_row:
            #            ind_row=ind_row.split('(')[0]
            #        output_per_employee_by_naics[ind_row]=output_per_emp
            self.output_per_employee_by_naics = output_per_employee_by_naics
        if return_data:
            return self.output_per_employee_by_naics



class DataLoader:
    def __init__(self,occLevel=3,saveData=True,data_path='tables/innovation_data',quietly=True):
        '''
        Class that contains multiple data loading functions. 
        Most of these functions need each other, which is why it makes sense to put this in a class.
        When given a data_path, it will save files in memory for future use. 
        '''
        self.occLevel   = (occLevel if occLevel<=2 else occLevel+1) 
        self.data_path  = data_path
        self.saveData   = saveData
        self.quietly    = quietly

        # Tables used for model training:
        self.pop_msa = None
        self.emp_msa = None
        self.emp_zip = None
        self.emp_zip_ind = None
        self.emp_occ = None
        self.msas  = None
        self.nPats = None
        self.RECPI = None
        self.RnD   = None
        self.IO_data = None

        self.skills          = None
        self.knowledge       = None
        self.msa_skills      = None
        self.zip_knowledge   = None
        self.skill_names     = None
        self.knowledge_names = None

    def load_RECPI(self,return_data=False):
        '''
        Loads entrepreneruship data from local directory (set in data_path=tables/innovation_data)

        Does not download data, but raises error if not found.

        Download the file Entrepreneurship_by_ZIP_Code_policy.tab from:
        `https://www.startupcartography.com`
        and save in data_path
        '''
        if self.RECPI is None:
            file_path = os.path.join(self.data_path,'Entrepreneurship_by_ZIP_Code_policy.tab')
            if not os.path.isfile(file_path):
                raise NameError('Entrepreneurship data not found. Please download from \nhttps://www.startupcartography.com/\nand save to '+self.data_path)
            RECPI = pd.read_csv(file_path,delimiter='\t',dtype={'zipcode':str},low_memory=False)
            self.RECPI = RECPI[RECPI['year'].isin([2014,2015,2016])].groupby(['zipcode','state']).agg({'EQI':'mean','SFR':'sum','RECPI':'sum'}).reset_index()[['zipcode','state','EQI','SFR','RECPI']]
        if return_data:
            return self.RECPI

    def load_IO_data(self,return_data=False):
        '''
        Loads employment by industry and occupation. 
        '''
        if self.IO_data is None:
            if not os.path.isfile(os.path.join(self.data_path,'nat4d_M2018_dl.csv')):
                url = 'https://www.bls.gov/oes/special.requests/oesm18in4.zip'
                fname = 'oesm18in4/nat4d_M2018_dl.xlsx'
                if not self.quietly:
                    print('Loading IO data')
                IO_dataRaw = load_zipped_excel(url,fname)
                IO_dataRaw.to_csv(os.path.join(self.data_path,'nat4d_M2018_dl.csv'),index=False)
            else:
                IO_dataRaw = pd.read_csv(os.path.join(self.data_path,'nat4d_M2018_dl.csv'),low_memory=False)
            IO_data = IO_dataRaw[(IO_dataRaw['OCC_GROUP']=='detailed')&(IO_dataRaw['TOT_EMP']!='**')]
            IO_data = IO_data.astype({'TOT_EMP': 'float'})
            IO_data = IO_data.assign(NAICS=('00'+IO_data['NAICS'].astype(str)).str[-6:])
            IO_data = IO_data.assign(SELECTED_LEVEL=IO_data['OCC_CODE'].str[:self.occLevel])
            self.IO_data = IO_data.groupby(['NAICS','SELECTED_LEVEL']).sum()[['TOT_EMP']].reset_index()
        if return_data:
            return self.IO_data

    def load_onet_data(self):
        '''
        Loads skills and knowledge datasets from ONET.
        For more information see:
        https://www.onetcenter.org/database.html#all-files

        '''
        onet_url = 'https://www.onetcenter.org/dl_files/database/db_24_2_excel/'
        if (self.skills is None)|(self.knowledge is None):
            if os.path.isfile(os.path.join(self.data_path,'Skills.xlsx')):
                skillsRaw = pd.read_excel(os.path.join(self.data_path,'Skills.xlsx'))
            else:
                skillsRaw = pd.read_excel(onet_url+'Skills.xlsx')
                if self.saveData:
                    skillsRaw.to_excel(os.path.join(self.data_path,'Skills.xlsx'),index=False)
            skills = self.group_up_skills(skillsRaw)
            skills = skills[['SELECTED_LEVEL','Element ID','Data Value']].drop_duplicates()
            self.skills = skills
            self.skill_names = skillsRaw[['Element ID','Element Name']].drop_duplicates()
            self.msa_skills     = self._aggregate_to_GEO(skills,geoType='MSA')
            
            
            if os.path.isfile(os.path.join(self.data_path,'Knowledge.xlsx')):
                knowledgeRaw = pd.read_excel(os.path.join(self.data_path,'Knowledge.xlsx'))
            else:
                knowledgeRaw = pd.read_excel(onet_url+'Knowledge.xlsx')
                if self.saveData:
                    knowledgeRaw.to_excel(os.path.join(self.data_path,'Knowledge.xlsx'),index=False)
            knowledge = self.group_up_skills(knowledgeRaw)
            knowledge = knowledge[['SELECTED_LEVEL','Element ID','Data Value']].drop_duplicates()               
            self.knowledge = knowledge
            self.knowledge_names = knowledgeRaw[['Element ID','Element Name']].drop_duplicates()
            self.zip_knowledge   = self._aggregate_to_GEO(knowledge,geoType='ZIP')


    def _aggregate_to_GEO(self,skills,geoType='MSA',pivot=True):
        '''
        Aggregates the skills to the MSA area based on employment by occupation in each MSA.
        It works with any dataframe with the colmns: SELECTED_LEVEL,Element ID,Data Value
        Where SELECTED_LEVEL corresponds to occupation codes and Element ID to the codes to aggregate.

        Parameters
        ----------
        skills: pandas.dataframe
            Dataframe with skill level (Data Value) per skill (Element ID) per occupation (SELECTED_LEVEL)
        geoType: str
            'MSA' or 'ZIP'
        pivot: boolean
            If true, it will return the data in a wide format, as opposed to a long format

        Returns
        -------
        msa_skills: pandas.DataFrame
            Skill level per GEOID.
            If pivot=True, each column correponds to on Element ID, if pivot=False, then there are three columns: GEOID, Element ID, Data Value. 
        '''
        if geoType=='MSA':
            self.load_MSA_data()
            geoCol = 'GEOID'
        elif geoType=='ZIP':
            self.load_ZIP_data()
            geoCol = 'ZCTA5CE10'
        else:
            raise NameError('Unrecognized geoType:'+geoType)
        emp = (self.emp_msa if geoType=='MSA' else self.emp_zip)
        msa_skills = pd.merge(emp,skills)
        msa_skills = pd.merge(msa_skills,emp.groupby(geoCol).sum()[['TOT_EMP']].rename(columns={'TOT_EMP':'TOT_EMP_MSA'}).reset_index())
        msa_skills['w'] = msa_skills['TOT_EMP']/msa_skills['TOT_EMP_MSA']
        msa_skills['Data Value'] = msa_skills['Data Value']*msa_skills['w']
        msa_skills = msa_skills.groupby([geoCol,'Element ID']).sum()[['Data Value']].reset_index()
        if pivot:
            msa_skills = msa_skills.pivot_table(values='Data Value',index=geoCol,columns='Element ID').reset_index().fillna(0)
            msa_skills.columns = msa_skills.columns.values.tolist()
        return msa_skills

    def group_up_skills(self,skillsRaw,normalize=False):
        '''
        Skills data comes at the lowest level of the occupation classification (SOC Codes).
        This function aggregates it up to the desired level defined in the occLevel parameter when initializing the object.
        Each skill for the new level is the weighted average of the lower level occupations (each occupation weighted by the share of workers at the national level).

        For example, occupation code 11-1 disaggregates into three 6-digit categories, 11-1011 (200k), 11-1021 (2300k), and 11-1031 (50k).
        Because category 11-1021 has most of the employees, the average worker in 11-1 has the same skills as a worker in 11-1021.

        Parameters
        ----------
        normalize : boolean (default=False)
            If True, the skill weights all sum up to one. 
        '''

        if self.emp_occ is None:
            self.load_OCC_data()
        empOcc = self.emp_occ

        skills = skillsRaw[['O*NET-SOC Code','Element ID','Element Name','Data Value','Recommend Suppress','Not Relevant']]
        skills = skills[(skills['Not Relevant']!='Yes')&(skills['Recommend Suppress']!='Y')]
        skills['SELECTED_LEVEL'] = skills['O*NET-SOC Code'].str[:self.occLevel]
        skills['OCC_CODE'] = skills['O*NET-SOC Code'].str[:7]
        skills = pd.merge(skills,empOcc[['OCC_CODE','TOT_EMP']])
        skills = pd.merge(skills,empOcc.groupby('SELECTED_LEVEL').sum()[['TOT_EMP']].reset_index().rename(columns={'TOT_EMP':'TOT_EMP_3'}))
        skills['w'] = skills['TOT_EMP']/skills['TOT_EMP_3']
        skills['Data Value'] = skills['Data Value']*skills['w']
        skills = skills.groupby(['SELECTED_LEVEL','Element ID','Element Name']).sum()[['Data Value']].reset_index()
        if normalize:
            skills = pd.merge(skills,skills.groupby('SELECTED_LEVEL').sum()[['Data Value']].rename(columns={'Data Value':'Normalization'}).reset_index())
            skills['Data Value'] = skills['Data Value']/skills['Normalization']
        return skills

    def load_MSA_data(self):
        '''
        Loads MSA shapefiles, population, and employment by occupation. 
        Both datasets are used to fit the Skill indicator.
        '''
        if self.msas is None:
            msas = gpd.read_file(os.path.join(SHAPES_PATH,'2019_cbsa/tl_2019_us_cbsa/tl_2019_us_cbsa.shp'))
            msas = msas[msas['LSAD']=='M1'] # Select only metro areas
            self.msas = msas

        if self.pop_msa is None:
            if os.path.isfile(os.path.join(self.data_path,'B01003_001E.csv')):
                pop_msa = pd.read_csv(os.path.join(self.data_path,'B01003_001E.csv'),dtype={'GEOID':str},low_memory=False)
            else:
                pop_msa = ACSCall(['B01003_001E'],level='metropolitan statistical area/micropolitan statistical area',year=2018).rename(columns={'metropolitan statistical area/micropolitan statistical area':'GEOID'})
                if self.saveData:
                    pop_msa.to_csv(os.path.join(self.data_path,'B01003_001E.csv'),index=False)
            pop_msa = pop_msa[pop_msa['GEOID'].isin(set(msas['GEOID']))]
            self.pop_msa = pop_msa

        if self.emp_msa is None:
            if not os.path.isfile(os.path.join(self.data_path,'MSA_M2018_dl.csv')):
                url = 'https://www.bls.gov/oes/special.requests/oesm18ma.zip'
                empRaw = load_zipped_excel(url,'oesm18ma/MSA_M2018_dl.xlsx')
                if self.saveData:
                    empRaw.to_csv(os.path.join(self.data_path,'MSA_M2018_dl.csv'),index=False)
            else:
                empRaw = pd.read_csv(os.path.join(self.data_path,'MSA_M2018_dl.csv'),low_memory=False)
            emp = empRaw[(empRaw['OCC_GROUP']=='detailed')&(empRaw['TOT_EMP']!='**')]
            emp = emp.astype({'TOT_EMP': 'float'})
            emp = emp[['AREA','OCC_CODE','TOT_EMP']].rename(columns={'AREA':'GEOID'})
            emp['GEOID'] = emp['GEOID'].astype(str)
            emp['SELECTED_LEVEL'] = emp['OCC_CODE'].str[:self.occLevel]
            emp = emp.groupby(['GEOID','SELECTED_LEVEL']).sum()[['TOT_EMP']].reset_index()
            emp = emp[emp['GEOID'].isin(set(msas['GEOID']))]
            self.emp_msa = emp


    def load_ZIP_data_byInd(self,year = '2016'):

        if self.emp_zip_ind is None:
            if os.path.isfile(os.path.join(self.data_path,'us_wak_S00_JT00_{}_ZIPCODE.csv'.format(year))):
                emp_zip = pd.read_csv(os.path.join(self.data_path,'us_wak_S00_JT00_{}_ZIPCODE.csv'.format(year)))
            else:
                year_version='2019'
                if not os.path.isfile(os.path.join(SHAPES_PATH,'ZIP_BG_matched_{}.csv'.format(year_version))):
                    raise NameError('Missing crosswalk between ZIPCODES and CENSUS BLOCKS.')
                zip_bg = pd.read_csv(os.path.join(SHAPES_PATH,'ZIP_BG_matched_{}.csv'.format(year_version)),dtype={'GEOID':str})

                fname = '{}_wac_S000_JT00_{}.csv.gz'
                base_url = 'https://lehd.ces.census.gov/data/lodes/LODES7/'

                r = requests.get(base_url)
                soup = BeautifulSoup(r.content, 'html.parser')
                states = [a[:-1] for a in [t.find('a')['href'] for t in soup.find_all('td') if t.find('a') is not None] if len(a.replace('/',''))==2]

                emp_zip = []
                for state in states:
                    fpath = os.path.join(base_url,'{}/wac',fname)
                    fpath = fpath.format(state,state,year)
                    for i in range(3):
                        try:
                            if not self.quietly:
                                print(fpath,i)
                            df = pd.read_csv(fpath,compression='gzip',dtype={'w_geocode':str})
                            break
                        except:
                            df = None
                    if df is not None:
                        df = df[['w_geocode']+[c for c in df.columns if c[:2]=='CN']]
                        df['GEOID'] = df['w_geocode'].str[:-3]
                        df = df.drop('w_geocode',1).groupby('GEOID').sum().reset_index()
                        df_matched = pd.merge(df,zip_bg)
                        for c in [c for c in df_matched.columns if c[:2]=='CN']:
                            df_matched[c] = df_matched[c]*df_matched['weight']
                        df_matched = df_matched.groupby('ZCTA5CE10').sum().drop(['weight','STATE_FIPS'],1).reset_index()
                        emp_zip.append(df_matched)
                emp_zip = pd.concat(emp_zip)
                if self.saveData:
                    emp_zip.to_csv(os.path.join(self.data_path,'us_wak_S00_JT00_{}_ZIPCODE.csv'.format(year)),index=False)
            emp_zip = emp_zip.assign(ZCTA5CE10 = ('000'+emp_zip['ZCTA5CE10'].astype(str)).str[-5:])
            self.emp_zip_ind = emp_zip


    def load_ZIP_data(self):
        '''
        Loads employment data for each zip code from the LODES data. 
        It uses a self generated crosswalk between census blocks and zipcodes.
        '''
        year = '2016'

        if self.emp_zip is None:
            if os.path.isfile(os.path.join(self.data_path,'us_wak_S00_JT00_{}_ZIPCODE_OCC.csv'.format(year))):
                emp_zip = pd.read_csv(os.path.join(self.data_path,'us_wak_S00_JT00_{}_ZIPCODE_OCC.csv'.format(year)))
            else:
                self.load_ZIP_data_byInd(year = year)
                cw = [('CNS01','11'),('CNS02','21'),('CNS03','22'),('CNS04','23'),('CNS05','31-33'),('CNS06','42'),
                      ('CNS07','44-45'),('CNS08','48-49'),('CNS09','51'),('CNS10','52'),('CNS11','53'),('CNS12','54'),
                      ('CNS13','55'),('CNS14','56'),('CNS15','61'),('CNS16','62'),('CNS17','71'),('CNS18','72'),('CNS19','81'),
                      ('CNS20','92')]

                emp_zip = pd.melt(self.emp_zip_ind,id_vars='ZCTA5CE10',value_name='TOT_EMP')
                emp_zip = pd.merge(emp_zip,pd.DataFrame(cw,columns=['variable','NAICS'])).drop('variable',1)
                emp_zip = emp_zip[emp_zip['TOT_EMP']!=0]

                match = pd.read_csv(os.path.join(SHAPES_PATH,'ZIP_MSA_matched_2019.csv'),dtype={'ZCTA5CE10':str})
                emp_zip = emp_zip[emp_zip['ZCTA5CE10'].isin(set(match['ZCTA5CE10']))]

                IO_data = self.IO_data.assign(NAICS = self.IO_data['NAICS'].str[:-4])
                IO_data.loc[IO_data['NAICS'].isin(['31','32','33']),'NAICS'] = '31-33'
                IO_data.loc[IO_data['NAICS'].isin(['44','45']),'NAICS'] = '44-45'
                IO_data.loc[IO_data['NAICS'].isin(['48','49']),'NAICS'] = '48-49'
                IO_data = pd.merge(IO_data,IO_data.groupby('NAICS').sum().reset_index().rename(columns={'TOT_EMP':'TOT_EMP_NAICS'}))
                IO_data = IO_data.assign(weight=IO_data['TOT_EMP']/IO_data['TOT_EMP_NAICS'])
                IO_data = IO_data[['NAICS','SELECTED_LEVEL','weight']]

                emp_zip = pd.merge(emp_zip,IO_data)
                emp_zip = emp_zip.assign(TOT_EMP=emp_zip['TOT_EMP']*emp_zip['weight']).groupby(['ZCTA5CE10','SELECTED_LEVEL']).sum()
                emp_zip = emp_zip[['TOT_EMP']].reset_index()
                emp_zip = pd.merge(emp_zip,match)
                if self.saveData:
                    emp_zip.to_csv(os.path.join(self.data_path,'us_wak_S00_JT00_{}_ZIPCODE_OCC.csv'.format(year)),index=False)
            self.emp_zip = emp_zip

                
    def load_OCC_data(self):
        '''
        Loads employment by occupation.
        This data is used to aggregate the occupation codes one level up.
        '''
        if self.emp_occ is None:
            if not os.path.isfile(os.path.join(self.data_path,'national_M2018_dl.csv')):
                url = 'https://www.bls.gov/oes/special.requests/oesm18nat.zip'
                empOccRaw = load_zipped_excel(url,'oesm18nat/national_M2018_dl.xlsx')
                if self.saveData:
                    empOccRaw.to_csv(os.path.join(self.data_path,'national_M2018_dl.csv'),index=False)
            else:
                empOccRaw = pd.read_csv(os.path.join(self.data_path,'national_M2018_dl.csv'),low_memory=False)
            empOcc = empOccRaw[empOccRaw['OCC_GROUP']=='detailed']
            empOcc = empOcc[['OCC_CODE','TOT_EMP','OCC_GROUP']]
            empOcc['SELECTED_LEVEL'] = empOcc['OCC_CODE'].str[:self.occLevel]
            self.emp_occ = empOcc
    
    def load_RnD_data(self):
        '''
        Load data on RnD by industry.
        This data will be relevant for the innovation intensity of the industries in the area.
        '''
        if not os.path.isfile(os.path.join(self.data_path,'nsf20311-tab002.csv')):
            url = 'https://ncses.nsf.gov/pubs/nsf20311/assets/data-tables/tables/nsf20311-tab002.xlsx'
            nsf = pd.read_excel(url)
            if self.saveData:
                nsf.to_csv(os.path.join(self.data_path,'nsf20311-tab002.csv'),index=False)
        else:
            nsf = pd.read_csv(os.path.join(self.data_path,'nsf20311-tab002.csv'),low_memory=False)
        colnames = [nsf.iloc[:4][c].fillna('').astype(str).sum() for c in nsf.columns]
        nsf = nsf.iloc[4:]
        nsf.columns = colnames
        self.RnD = nsf[['NAICS code','Domestic R&D performanceTotal']]


    def load_patent_data(self,pop_th=100000):
        '''
        Loads Patent Data from patentsView for each MSA.
        Only consideres MSAs above pop_th
        '''
        if (self.msas is None)|(self.pop_msa is None):
            self.load_MSA_data()

        msas = self.msas
        pop_msa = self.pop_msa

        if self.nPats is None:
            if not os.path.isfile(os.path.join(self.data_path,'nPats.csv')):
                application = patentsViewDownload('application')
                application['year'] = application['date'].str[:4].astype(float)
                application = application[(application['year']>=2010)&
                                          (application['year']<=2020)&
                                          (application['country']=='US')]
                patentSet = set(application['patent_id'])

                patent_inventor = patentsViewDownload('patent_inventor')
                patent_inventor = patent_inventor[patent_inventor['patent_id'].isin(patentSet)]
                inventorSet = set(patent_inventor['inventor_id'])

                location_inventor = patentsViewDownload('location_inventor')
                location_inventor = location_inventor[location_inventor['inventor_id'].isin(inventorSet)]
                locationSet = set(location_inventor['location_id'])

                location = patentsViewDownload('location')
                location = location[location['id'].isin(locationSet)]

                location = gpd.GeoDataFrame(location,geometry=gpd.points_from_xy(location.longitude, location.latitude),crs={'init': 'epsg:4269'})
                matched = gpd.sjoin(location,msas)
                matched = matched[['id','GEOID']].drop_duplicates().rename(columns={'id':'location_id'})

                nPats = pd.merge(location_inventor,matched)[['inventor_id','GEOID']].drop_duplicates()
                nPats = pd.merge(patent_inventor,nPats)[['patent_id','GEOID']].drop_duplicates()
                nPats = nPats.groupby('GEOID').count().rename(columns={'patent_id':'nPats'}).reset_index()
                nPats = pd.merge(pop_msa,nPats).rename(columns={'B01003_001E':'pop'})
                nPats = nPats[nPats['pop']>pop_th]
                self.nPats = nPats

                if self.saveData:
                    nPats.to_csv(os.path.join(self.data_path,'nPats.csv'),index=False)
            else:
                self.nPats = pd.read_csv(os.path.join(self.data_path,'nPats.csv'),dtype={'GEOID':str},low_memory=False)


#############
# Functions #
#############

def shannon_equitability_score(species_counts):
    diversity=0
    pop_size=sum(species_counts)
    if ((len(species_counts)>1) and (pop_size>0)):        
        for count in species_counts:
            pj=count/pop_size
            if not pj==0:
                diversity+= -pj*math.log(pj)
        equitability=diversity/math.log(len(species_counts))
        return equitability
    else:
        return None

def parse_CityScopeCategories(fpath,CS_column='CS Amenities ',NAICS_column='Unnamed: 5'):
    '''
    Useful function to parse the cityscope categories excel located at:
    fpath = tables/200405_CityScope.categories.xlsx
    
    '''
    CS_cats = pd.read_excel(fpath).iloc[1:]
    CS_cats = CS_cats[[CS_column,NAICS_column]]
    CS_cats['shifted'] = CS_cats[CS_column]
    while any(CS_cats[CS_column].isna()):
        CS_cats['shifted'] = CS_cats['shifted'].shift(1)
        CS_cats.loc[CS_cats[CS_column].isna(),CS_column] = CS_cats[CS_cats[CS_column].isna()]['shifted']
    CS_cats = CS_cats.drop('shifted',1)
    CS_cats = CS_cats.dropna().drop_duplicates()
    CS_cats['NAICS'] = CS_cats[NAICS_column].str.strip().str.split(' ').apply(lambda x:x[0])
    CS_cats['NAICS_name'] = [n.replace(c,'').replace('-','').strip() for n,c in CS_cats[[NAICS_column,'NAICS']].values]
    CS_cats = CS_cats.drop(NAICS_column,1)
    return CS_cats