import pandas as pd
import geopandas as gpd
import requests
import os
import numpy as np
from geopandas import sjoin
from APICalls import ACSCall,patentsViewDownload,load_zipped_excel
from download_shapeData import SHAPES_PATH
from sklearn.linear_model import Lasso, Ridge, LinearRegression
from collections import defaultdict
from toolbox import Indicator

class InnoIndicator(Indicator):
	def setup(self,occLevel=3,saveData=True,modelPath='tables/innovation_data',quietly=True):

		self.name       = 'Innovation-Potential'
		self.occLevel   = (occLevel if occLevel<=2 else occLevel+1) 
		self.modelPath  = modelPath

		self.sks_coefs_path = os.path.join(modelPath,'sks_coefs.csv')
		self.kno_coefs_path = os.path.join(modelPath,'kno_coefs.csv')
		self.saveData   = saveData
		self.quietly    = quietly

		# Tables used for model training:
		self.pop_msa = None
		self.emp_msa = None
		self.emp_occ = None
		self.msas  = None
		self.nPats = None
		self.RECPI = None
		self.RnD   = None

		self.train_data_sks = None
		self.train_data_kno = None
		

		self.coefs_sks      = None
		self.norm_coefs_sks = None
		self.coefs_kno      = None
		self.coefs_rnd      = None

		self.IO_data = None

		self.skills          = None
		self.knowledge       = None
		self.msa_skills      = None
		self.msa_knowledge   = None
		self.skill_names     = None
		self.knowledge_names = None

	def return_indicator(self, geogrid_data):
		industry_composition = self.grid_to_industries(geogrid_data)
		worker_composition   = self.industries_to_occupations(industry_composition)
		skill_composition    = self.occupations_to_skills(worker_composition)
		skills = self.SKSindicator(skill_composition)
		skills = self.normalize(skills)
		out = [
				{'name':'District-knowledge','value':0.5,'category':'innovation'},
				{'name':'City-skills','value':skills,'category':'innovation'},
				{'name':'Region-funding','value':0.3,'category':'innovation'}
			  ]
		return out
		

	def normalize(self,value):
		'''
		Normalize indicator to keep between zero and one
		'''
		return value/4.

	def grid_to_industries(self,geogrid_data):
		'''
		THIS FUNCTION SHOULD TRANSLATE BETWEEN GEOGRIDDATA TO NAICS
		'''
		industry_composition = {'424':100,'813':10,'518':30,'313':50}
		return industry_composition

	def KNOindicator(self,industry_composition):
		pass

	def INDindicator(self,industry_composition):
		'''
		Returns the innovation intensity of the industries in the area.
		The intensity of each industry is inferred based on their RnD investement at the national level.

		Parameters
		----------
		industry_composition : dict
			Number of companies in each industry.
		'''
		self.load_RnD_data()

	def SKSindicator(self,skill_composition):
		'''
		Innovation indicator basedd on skill composition of the surrounding areas. 
		The Skill Composition is the composition of skills and knowledge of the average worker in the vecinity.
		Values should sum up to 1. 
		This indicator uses the number of patents per capita as an organizing variable to fit the relative importance of the skills.

		Parameters
		----------
		skill_composition : dict
			Values for skills and knowledge:
			 '2.C.1.b': 0.00027776434263997884,
			 '2.C.1.c': 0.0007550480378548599,
			 '2.C.1.d': 0.0052332454511384565,
			 '2.C.1.e': 0.05254535680693754,
			 '2.C.10': 0.03276481572064952,
			 '2.C.2.b': 0.043292938229292977,
			 '2.C.3.b': 0.06381380135912351,
			 '2.C.3.d': 0.056718692091353703,
			 ...
		'''
		if (self.coefs_sks is None)|(self.norm_coefs_sks is None):
			self.load_fitted_model()

		normalization = float(sum(skill_composition.values()))
		if normalization != 1:
			skill_composition = {k:skill_composition[k]/normalization for k in skill_composition}
		values = defaultdict(int,skill_composition)

		return_value = self.coefs['intercept']
		for k in [k for k in self.coefs if k!='intercept']:
			if k[-2:]=='_2':
				return_value+= self.coefs[k]*((values[k[:-2]]-self.norm_coefs_sks[k[:-2]]['mean'])/self.norm_coefs_sks[k[:-2]]/['std'])**2
			else:
				return_value+= self.coefs[k]*(values[k]-self.norm_coefs_sks[k]['mean'])/self.norm_coefs_sks[k]/['std']
		return return_value
		return np.exp(return_value)

	def occupations_to_skills(self,worker_composition):
		'''
		Uses the ONET skills and knowledge data to calculate the skill composition of the given worker composition.

		Parameters
		----------
		worker_composition : dict
			Worker composition in numbers:
			 '21-1': 15.262277812601601,
			 '47-4': 93.92368069312724,
			 '43-4': 3.672814568184372,
			 '39-6': 56.79273947481439,
			 '19-4': 72.39516945281179,
			 '19-2': 71.90943435016996,
			 '17-2': 8.900504545936089,
			 '39-5': 9.798808535026307,
			 '51-2': 30.385813540925056,
			 ...
		'''
		if self.combinedSkills is None:
			self.load_onet_data()
		totalWorkers = sum(worker_composition.values())
		nWorkers = pd.DataFrame(worker_composition.items(),columns=['SELECTED_LEVEL','N'])
		workers_by_skill = pd.merge(self.combinedSkills,nWorkers)
		workers_by_skill['w'] = workers_by_skill['N']/totalWorkers
		workers_by_skill['Data Value'] = workers_by_skill['Data Value']*workers_by_skill['w']
		skill_composition = workers_by_skill.groupby('Element ID').sum()[['Data Value']].reset_index()
		skill_composition['Data Value'] = skill_composition['Data Value']/skill_composition['Data Value'].sum()
		skill_composition = dict(skill_composition.values)
		return skill_composition

	def load_module(self,coefs_path=None):
		'''
		Loads the coefficients for the fitted model found in coefs_path.
		'''
		if coefs_path is None:
			coefs_path = self.sks_coefs_path
		if os.path.isfile(coefs_path):
			coefs_df = pd.read_csv(coefs_path,low_memory=False)
			self.coefs = dict(coefs_df[['Element ID','coef']].values)
		else:
			print('No fitted model found, please run train function.')
		self.load_IO_data()

	def train_citySKS(self,coefs_path=None):
		'''
		Trains the model: finds the relative importance of each skill using positive Lasso regression with number of patents by US-metro area as the organizing variable.

		Returns
		-------
		coefs_df : pandas.DataFrame
			Table with coefficients for each skill category.
		'''
		self.load_OCC_data()
		self.load_MSA_data()
		self.load_patent_data()
		self.load_onet_data()

		msa_skills = self.msa_skills
		skills_columns = msa_skills.drop('GEOID',1).columns.tolist()

		df = msa_skills
		df = df.assign(TOT_SKS=df[skills_columns].sum(1))
		for c in skills_columns:
			df[c] = df[c]/df['TOT_SKS']

		df = pd.merge(df,self.nPats,how='inner')
		df = pd.merge(df,self.emp_msa.groupby('GEOID').sum().reset_index())
		df = df.assign(pats_pc = df['nPats']/df['pop'])

		self.train_data_sks = df

		Xdf = df.drop(['GEOID','nPats','pop','pats_pc','TOT_EMP','TOT_SKS'],1)

		norm_coefs = {}
		for c in Xdf.columns:
			norm_coefs[c] = {'std':Xdf[c].std(),'mean':Xdf[c].mean()}
			Xdf[c] = (Xdf[c]-Xdf[c].mean())/Xdf[c].std()
			Xdf[c+'_2'] = Xdf[c]**2
		X = Xdf.values
		Y = np.log(df['pats_pc'].values)

		model = Ridge(alpha=1.)
		model.fit(X,Y)

		train_score=model.score(X,Y)
		coeff_used = np.sum(model.coef_!=0)
		print("training score:", train_score )
		print("number of features used: ", coeff_used,'out of',np.shape(X)[-1])

		variables = Xdf.columns.values[np.where(model.coef_!=0)[0]]
		print(len(variables),variables)
		coefs = dict(zip(variables,model.coef_[model.coef_!=0]))
		coefs['intercept'] = model.intercept_
		coefs_df = pd.DataFrame(coefs.items(),columns=['Element ID','coef'])

		if coefs_path is None:
			coefs_path = self.sks_coefs_path
		if self.saveData:
			coefs_df.to_csv(coefs_path,index=False)
		self.coefs_sks = coefs
		self.norm_coefs_sks = norm_coefs

		return pd.merge(coefs_df,self.skill_names,how='left').sort_values(by='coef',ascending=False)

	def load_RECPI(self):
		'''
		Loads entrepreneruship data from local directory (set in modelPath=tables/innovation_data)

		Does not download data, but raises error if not found.

		Download the file Entrepreneurship_by_ZIP_Code_policy.tab from:
		`https://www.startupcartography.com`
		and save in modelPath
		'''
		file_path = os.path.join(self.modelPath,'Entrepreneurship_by_ZIP_Code_policy.tab')
		if not os.path.isfile(file_path):
			raise NameError('Entrepreneurship data not found. Please download from \nhttps://www.startupcartography.com/\nand save to '+self.modelPath)
		RECPI = pd.read_csv(file_path,delimiter='\t',dtype={'zipcode':str},low_memory=False)
		self.RECPI = RECPI[RECPI['year']==2016][['zipcode','state','EQI','SFR','RECPI','REAI']]

	def load_IO_data(self):
		'''
		Loads employment by industry and occupation. 
		'''
		if not os.path.isfile(os.path.join(self.modelPath,'nat4d_M2018_dl.csv')):
			url = 'https://www.bls.gov/oes/special.requests/oesm18in4.zip'
			fname = 'oesm18in4/nat4d_M2018_dl.xlsx'
			if not self.quietly:
				print('Loading IO data')
			IO_dataRaw = load_zipped_excel(url,fname)
			IO_dataRaw.to_csv(os.path.join(self.modelPath,'nat4d_M2018_dl.csv'),index=False)
		else:
			IO_dataRaw = pd.read_csv(os.path.join(self.modelPath,'nat4d_M2018_dl.csv'),low_memory=False)
		IO_data = IO_dataRaw[(IO_dataRaw['OCC_GROUP']=='detailed')&(IO_dataRaw['TOT_EMP']!='**')]
		IO_data = IO_data.astype({'TOT_EMP': 'float'})
		IO_data = IO_data.assign(NAICS=('00'+IO_data['NAICS'].astype(str)).str[-6:])
		IO_data = IO_data.assign(SELECTED_LEVEL=IO_data['OCC_CODE'].str[:self.occLevel])
		self.IO_data = IO_data.groupby(['NAICS','SELECTED_LEVEL']).sum()[['TOT_EMP']].reset_index()

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
		if self.IO_data is None:
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

	def load_onet_data(self):
		'''
		Loads skills and knowledge datasets from ONET.
		For more information see:
		https://www.onetcenter.org/database.html#all-files

		'''
		onet_url = 'https://www.onetcenter.org/dl_files/database/db_24_2_excel/'
		if (self.skills is None)|(self.knowledge is None):
			if os.path.isfile(os.path.join(self.modelPath,'Skills.xlsx')):
				skillsRaw = pd.read_excel(os.path.join(self.modelPath,'Skills.xlsx'))
			else:
				skillsRaw = pd.read_excel(onet_url+'Skills.xlsx')
				if self.saveData:
					skillsRaw.to_excel(os.path.join(self.modelPath,'Skills.xlsx'),index=False)
			skills = self.group_up_skills(skillsRaw)
			skills = skills[['SELECTED_LEVEL','Element ID','Data Value']].drop_duplicates()
			self.skills = skills
			self.skill_names = skillsRaw[['Element ID','Element Name']].drop_duplicates()
			self.msa_skills     = self._aggregate_to_MSA(skills)
			
			
			if os.path.isfile(os.path.join(self.modelPath,'Knowledge.xlsx')):
				knowledgeRaw = pd.read_excel(os.path.join(self.modelPath,'Knowledge.xlsx'))
			else:
				knowledgeRaw = pd.read_excel(onet_url+'Knowledge.xlsx')
				if self.saveData:
					knowledgeRaw.to_excel(os.path.join(self.modelPath,'Knowledge.xlsx'),index=False)
			knowledge = self.group_up_skills(knowledgeRaw)
			knowledge = knowledge[['SELECTED_LEVEL','Element ID','Data Value']].drop_duplicates()				
			self.knowledge = knowledge
			self.knowledge_names = knowledgeRaw[['Element ID','Element Name']].drop_duplicates()
			self.msa_knowledge   = self._aggregate_to_MSA(knowledge)


	def _aggregate_to_MSA(self,skills,pivot=True):
		'''
		Aggregates the skills to the MSA area based on employment by occupation in each MSA.
		It works with any dataframe with the colmns: SELECTED_LEVEL,Element ID,Data Value
		Where SELECTED_LEVEL corresponds to occupation codes and Element ID to the codes to aggregate.

		Parameters
		----------
		skills: pandas.dataframe
			Dataframe with skill level (Data Value) per skill (Element ID) per occupation (SELECTED_LEVEL)
		pivot: boolean
			If true, it will return the data in a wide format, as opposed to a long format

		Returns
		-------
		msa_skills: pandas.DataFrame
			Skill level per GEOID.
			If pivot=True, each column correponds to on Element ID, if pivot=False, then there are three columns: GEOID, Element ID, Data Value. 
		'''
		if self.emp_msa is None:
			self.load_MSA_data()
		emp = self.emp_msa
		msa_skills = pd.merge(emp,skills)
		msa_skills = pd.merge(msa_skills,emp.groupby('GEOID').sum()[['TOT_EMP']].rename(columns={'TOT_EMP':'TOT_EMP_MSA'}).reset_index())
		msa_skills['w'] = msa_skills['TOT_EMP']/msa_skills['TOT_EMP_MSA']
		msa_skills['Data Value'] = msa_skills['Data Value']*msa_skills['w']
		msa_skills = msa_skills.groupby(['GEOID','Element ID']).sum()[['Data Value']].reset_index()
		if pivot:
			msa_skills = msa_skills.pivot_table(values='Data Value',index='GEOID',columns='Element ID').reset_index().fillna(0)
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
			if os.path.isfile(os.path.join(self.modelPath,'B01003_001E.csv')):
				pop_msa = pd.read_csv(os.path.join(self.modelPath,'B01003_001E.csv'),dtype={'GEOID':str},low_memory=False)
			else:
				pop_msa = ACSCall(['B01003_001E'],level='metropolitan statistical area/micropolitan statistical area',year=2018).rename(columns={'metropolitan statistical area/micropolitan statistical area':'GEOID'})
				if self.saveData:
					pop_msa.to_csv(os.path.join(self.modelPath,'B01003_001E.csv'),index=False)
			pop_msa = pop_msa[pop_msa['GEOID'].isin(set(msas['GEOID']))]
			self.pop_msa = pop_msa

		if self.emp_msa is None:
			if not os.path.isfile(os.path.join(self.modelPath,'MSA_M2018_dl.csv')):
				url = 'https://www.bls.gov/oes/special.requests/oesm18ma.zip'
				empRaw = load_zipped_excel(url,'oesm18ma/MSA_M2018_dl.xlsx')
				if self.saveData:
					empRaw.to_csv(os.path.join(self.modelPath,'MSA_M2018_dl.csv'),index=False)
			else:
				empRaw = pd.read_csv(os.path.join(self.modelPath,'MSA_M2018_dl.csv'),low_memory=False)
			emp = empRaw[(empRaw['OCC_GROUP']=='detailed')&(empRaw['TOT_EMP']!='**')]
			emp = emp.astype({'TOT_EMP': 'float'})
			emp = emp[['AREA','OCC_CODE','TOT_EMP']].rename(columns={'AREA':'GEOID'})
			emp['GEOID'] = emp['GEOID'].astype(str)
			emp['SELECTED_LEVEL'] = emp['OCC_CODE'].str[:self.occLevel]
			emp = emp.groupby(['GEOID','SELECTED_LEVEL']).sum()[['TOT_EMP']].reset_index()
			emp = emp[emp['GEOID'].isin(set(msas['GEOID']))]
			self.emp_msa = emp
				
	def load_OCC_data(self):
		'''
		Loads employment by occupation.
		This data is used to aggregate the occupation codes one level up.
		'''
		if self.emp_occ is None:
			if not os.path.isfile(os.path.join(self.modelPath,'national_M2018_dl.csv')):
				url = 'https://www.bls.gov/oes/special.requests/oesm18nat.zip'
				empOccRaw = load_zipped_excel(url,'oesm18nat/national_M2018_dl.xlsx')
				if self.saveData:
					empOccRaw.to_csv(os.path.join(self.modelPath,'national_M2018_dl.csv'),index=False)
			else:
				empOccRaw = pd.read_csv(os.path.join(self.modelPath,'national_M2018_dl.csv'),low_memory=False)
			empOcc = empOccRaw[empOccRaw['OCC_GROUP']=='detailed']
			empOcc = empOcc[['OCC_CODE','TOT_EMP','OCC_GROUP']]
			empOcc['SELECTED_LEVEL'] = empOcc['OCC_CODE'].str[:self.occLevel]
			self.emp_occ = empOcc
	
	def load_RnD_data(self):
		'''
		Load data on RnD by industry.
		This data will be relevant for the innovation intensity of the industries in the area.
		'''
		if not os.path.isfile(os.path.join(self.modelPath,'nsf20311-tab002.csv')):
			url = 'https://ncses.nsf.gov/pubs/nsf20311/assets/data-tables/tables/nsf20311-tab002.xlsx'
			nsf = pd.read_excel(url)
			if self.saveData:
				nsf.to_csv(os.path.join(self.modelPath,'nsf20311-tab002.csv'),index=False)
		else:
			nsf = pd.read_csv(os.path.join(self.modelPath,'nsf20311-tab002.csv'),low_memory=False)
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
			if not os.path.isfile(os.path.join(self.modelPath,'nPats.csv')):
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
				matched = sjoin(location,msas)
				matched = matched[['id','GEOID']].drop_duplicates().rename(columns={'id':'location_id'})

				nPats = pd.merge(location_inventor,matched)[['inventor_id','GEOID']].drop_duplicates()
				nPats = pd.merge(patent_inventor,nPats)[['patent_id','GEOID']].drop_duplicates()
				nPats = nPats.groupby('GEOID').count().rename(columns={'patent_id':'nPats'}).reset_index()
				nPats = pd.merge(pop_msa,nPats).rename(columns={'B01003_001E':'pop'})
				nPats = nPats[nPats['pop']>pop_th]
				self.nPats = nPats

				if self.saveData:
					nPats.to_csv(os.path.join(self.modelPath,'nPats.csv'),index=False)
			else:
				self.nPats = pd.read_csv(os.path.join(self.modelPath,'nPats.csv'),dtype={'GEOID':str},low_memory=False)

import random
def main():
	I = InnoIndicator()
	coefs = I.train()
	print(coefs)
	skill_composition = {k:random.random()**2 for k in I.coefs if (k[-1]!='a')&(k!='intercept')}
	print(skill_composition)
	print(I.SKSindicator(skill_composition))

if __name__ == '__main__':
	main()