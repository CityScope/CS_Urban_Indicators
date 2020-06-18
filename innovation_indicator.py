import pandas as pd
import os
import numpy as np
import joblib
from indicator_tools import DataLoader, EconomicIndicatorBase

class InnoIndicator(EconomicIndicatorBase):
	def setup(self,occLevel=3,saveData=True,modelPath='tables/innovation_data',quietly=True):

		self.name       = 'Innovation-Potential'
		self.occLevel   = (occLevel if occLevel<=2 else occLevel+1) 
		self.modelPath  = modelPath

		self.sks_model_path = os.path.join(modelPath,'sks_model.joblib')
		self.kno_model_path = os.path.join(modelPath,'kno_model.joblib')
		self.saveData   = saveData
		self.quietly    = quietly

		self.IO_data   = None
		self.skills    = None
		self.knowledge = None
		self.sks_model = None
		self.kno_model = None
		self.RnD_pc    = None

		self.kno_bounds = [-11,-7]
		self.rnd_bounds = [4,5]
		self.sks_bounds = [-16,-5]
		
	def return_indicator(self, geogrid_data):
		industry_composition  = self.grid_to_industries(geogrid_data)
		worker_composition    = self.industries_to_occupations(industry_composition)
		skill_composition     = self.occupations_to_skills(worker_composition)
		knowledge_composition = self.occupations_to_knowledge(worker_composition)


		skills    = self.SKSindicator(skill_composition)
		knowledge = self.KNOindicator(knowledge_composition)
		RnD       = self.RNDindicator(industry_composition)
		out = [
				{'name':'Knowledge','value':knowledge['norm'],'raw_value':knowledge['raw'],'category':'innovation','viz_type': self.viz_type, 'units': None},
				{'name':'Skills','value':skills['norm'],'raw_value':skills['raw'],'category':'innovation','viz_type': self.viz_type, 'units': None},
				{'name':'R&D Funding','value':RnD['norm'],'raw_value':RnD['raw'],'category':'innovation','viz_type': self.viz_type, 'units': 'Millions of US Dollars'}
			  ]
		return out

	def normalize_value(self, value,bounds):
		'''
		Normalizes the given value within the given bounds to ensure it stays between 0 and 1. 
		'''
		value = (value-bounds[0])/(bounds[1]-bounds[0])
		if isinstance(value,float):
			if value>1:
				value = 1
			elif value<0:
				value = 0
		else:
			value[value>1] = 1
			value[value<0] = 0
		return value

		
	def KNOindicator(self,knowledge_composition):
		'''
		Innovation indicator based on knowledge composition of the surrounding areas. 
		The Knowledge Composition is the composition of knowledge of the average worker in the vecinity.
		Values should sum up to 1. 
		This indicator uses the RECPI (from Startup Cartography Project) as an organizing variable to fit the relative importance of the knowledge variables.

		Parameters
		----------
		knowledge_composition : dict
			Values for skills and knowledge:
			 '2.C.1.a': 0.00027776434263997884,
			 '2.C.1.b': 0.0007550480378548599,
			 '2.C.1.c': 0.0052332454511384565,
			 '2.C.1.d': 0.05254535680693754,
			 '2.C.3.a': 0.03276481572064952,
			 '2.C.4.a': 0.043292938229292977,
			 '2.C.4.c': 0.06381380135912351,
			 '2.C.10': 0.056718692091353703,
			 ...
		normalize: boolean (default=True)
			If True, it will ensure the indicator returns values between 0 and 1. 
		'''
		self.load_module()
		knowledge_composition = pd.DataFrame([knowledge_composition])
		raw_value = self.kno_model.predict(knowledge_composition)[0]
		norm_value = self.normalize_value(raw_value,self.kno_bounds)
		return {'raw': raw_value, 'norm': norm_value}

	def RNDindicator(self,industry_composition):
		'''
		Returns the innovation intensity of the industries in the area.
		The intensity of each industry is inferred based on their RnD investement at the national level.

		Parameters
		----------
		industry_composition : dict
			Number of companies in each industry.
		normalize: boolean (default=True)
			If True, it will ensure the indicator returns values between 0 and 1. 
		'''
		inferred_NAICS_lvl = max([len(k) for k in industry_composition.keys()])

		industry_composition_df = pd.DataFrame(industry_composition.items(),columns=['NAICS','EMP'])
		industry_composition_df = industry_composition_df.assign(NAICS = self.standardize_NAICS_for_RnD(industry_composition_df))
		industry_composition_df = industry_composition_df.groupby('NAICS').sum().reset_index()

		RnD_pc = self.RnD_pc
		if inferred_NAICS_lvl==3:
			RnD_pc.loc[(RnD_pc['NAICS'].str[:2]=='54')|(RnD_pc['NAICS']=='other 54'),'NAICS']='541'
			RnD_pc = RnD_pc.groupby('NAICS').sum().reset_index()
			RnD_pc = RnD_pc.assign(RnD_pc=RnD_pc['RnD_investment']/RnD_pc['TOT_EMP'])

		industry_composition_df = pd.merge(industry_composition_df,RnD_pc)
		RnD = (industry_composition_df['TOT_EMP']*industry_composition_df['RnD_pc']).sum()/industry_composition_df['TOT_EMP'].sum()
		raw_value = RnD
		raw_value_log = np.log10(RnD+1)
		norm_value = self.normalize_value(raw_value_log,self.rnd_bounds)
		return {'raw': raw_value, 'norm': norm_value}


	def SKSindicator(self,skill_composition):
		'''
		Innovation indicator based on skill composition of the surrounding areas. 
		The Skill Composition is the composition of skills of the average worker in the vecinity.
		Values should sum up to 1. 
		This indicator uses the number of patents per capita as an organizing variable to fit the relative importance of the skills.

		Parameters
		----------
		skill_composition : dict
			Values for skills and knowledge:
			 '2.A.1.a': 0.00027776434263997884,
			 '2.A.1.c': 0.0007550480378548599,
			 '2.A.1.d': 0.0052332454511384565,
			 '2.A.1.e': 0.05254535680693754,
			 '2.A.1.f': 0.03276481572064952,
			 '2.B.1.a': 0.043292938229292977,
			 '2.B.3.k': 0.06381380135912351,
			 '2.B.5.d': 0.056718692091353703,
			 ...
		normalize: boolean (default=True)
			If True, it will ensure the indicator returns values between 0 and 1. 
		'''
		self.load_module()
		skill_composition = pd.DataFrame([skill_composition])
		raw_value = self.sks_model.predict(skill_composition)[0]
		norm_value = self.normalize_value(raw_value,self.sks_bounds)
		return {'raw': raw_value, 'norm': norm_value}

	def load_module(self):
		'''
		Loads the coefficients for the fitted model found in coefs_path.
		'''
		self.load_IO_data()
		self.load_onet_data()
		self.load_RnD_pc()
		if self.sks_model is None:
			self.sks_model = joblib.load(self.sks_model_path)
		if self.kno_model is None: 
			self.kno_model = joblib.load(self.kno_model_path)

	def load_RnD_pc(self):
		'''
		Loads data on RnD per capita
		'''
		self.load_IO_data()
		if self.RnD_pc is None:
			I_data = self.IO_data.groupby('NAICS').sum()[['TOT_EMP']].reset_index()
			I_data = I_data.assign(NAICS = I_data['NAICS'].str[:4]).groupby('NAICS').sum()[['TOT_EMP']].reset_index()
			I_data = I_data.assign(NAICS = self.standardize_NAICS_for_RnD(I_data))
			I_data = I_data.groupby('NAICS').sum()[['TOT_EMP']].reset_index()

			RnD = DataLoader().load_RnD_data(return_data=True).rename(columns={'NAICS code':'NAICS'})
			I_data = pd.merge(I_data,RnD)
			I_data['RnD_pc'] = I_data['RnD_investment']/I_data['TOT_EMP']
			self.RnD_pc = I_data
		

	def occupations_to_skills(self,worker_composition):
		'''
		Uses the ONET skills data to calculate the skill composition of the given worker composition.

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
		self.load_onet_data()
		totalWorkers = sum(worker_composition.values())
		nWorkers = pd.DataFrame(worker_composition.items(),columns=['SELECTED_LEVEL','N'])
		workers_by_skill = pd.merge(self.skills,nWorkers)
		workers_by_skill['w'] = workers_by_skill['N']/totalWorkers
		workers_by_skill['Data Value'] = workers_by_skill['Data Value']*workers_by_skill['w']
		skill_composition = workers_by_skill.groupby('Element ID').sum()[['Data Value']].reset_index()
		skill_composition['Data Value'] = skill_composition['Data Value']/skill_composition['Data Value'].sum()
		skill_composition = dict(skill_composition.values)
		return skill_composition

	def occupations_to_knowledge(self,worker_composition):
		'''
		Uses the ONET knowledge data to calculate the knowledge composition of the given worker composition.

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
		self.load_onet_data()
		totalWorkers = sum(worker_composition.values())
		nWorkers = pd.DataFrame(worker_composition.items(),columns=['SELECTED_LEVEL','N'])
		workers_by_knowledge = pd.merge(self.knowledge,nWorkers)
		workers_by_knowledge['w'] = workers_by_knowledge['N']/totalWorkers
		workers_by_knowledge['Data Value'] = workers_by_knowledge['Data Value']*workers_by_knowledge['w']
		knowledge_composition = workers_by_knowledge.groupby('Element ID').sum()[['Data Value']].reset_index()
		knowledge_composition['Data Value'] = knowledge_composition['Data Value']/knowledge_composition['Data Value'].sum()
		knowledge_composition = dict(knowledge_composition.values)
		return knowledge_composition

	def load_onet_data(self):
		if (self.skills is None)|(self.knowledge is None):
			loader = DataLoader()
			loader.load_onet_data(include_employment=False)
			self.skills    = loader.skills
			self.knowledge = loader.knowledge


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