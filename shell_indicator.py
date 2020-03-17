import pandas as pd
import json
from toolbox import Handler, Indicator

class ShellIndicator(Indicator):
	'''
	Example of an empty-shell indicator that always returns one.
	'''

	def setup(self):
		self.fitted_model = None

	def load_module(self):
		self.fitted_model = 1

	def return_indicator(self, geogrid_data):
		return self.fitted_model


class Density_Proximity(Indicator):
	'''
	Example of the same indicators implemented in indicator_tools.py
	'''
	def setup(self):
		self.table_name='corktown'
		self.AMENITY_SCORES_PATH='tables/{}/amenity_scores.csv'.format(self.table_name)
		self.BASIC_STATS_PATH='tables/{}/basic_stats.json'.format(self.table_name)
		self.BASELINE_INDICATORS_PATH='tables/{}/baseline_indicators.json'.format(self.table_name)
		self.PEOPLE_PER_RESI_BLD=200
		self.PEOPLE_PER_OFFICE_BLD=200

	def load_module(self):
		self.baseline_amenity_scores=pd.read_csv(self.AMENITY_SCORES_PATH)
		self.amenity_scores = self.baseline_amenity_scores.copy()
		self.basic_stats=json.load(open(self.BASIC_STATS_PATH))
		self.indicators=json.load(open(self.BASELINE_INDICATORS_PATH))
		self.indicator_name_order=[ind['name'] for ind in self.indicators]

	def return_indicator(self,geogrid_data):
		residents = self.basic_stats['residents']
		employees = self.basic_stats['employees']
		mixed_use_pois= ['restaurants', 'pharmacies', 'gyms', 'hotels', 'nightlife']

		# update numbers of employees, residents and amenities
		for cell in geogrid_data:
			if cell['name']=='Residential':
				residents+=self.PEOPLE_PER_RESI_BLD
			elif cell['name'] == 'Office Tower':
				employees+=self.PEOPLE_PER_OFFICE_BLD
			elif cell['name']=='Mix-use':
				self.amenity_scores.loc[self.amenity_scores['sub_sub_cat'].isin(mixed_use_pois), 'num_present']+=1

		# Update the residential and employment density scores    
		residential_density_score=residents/self.basic_stats['max_residents']
		employment_density_score=employees/self.basic_stats['max_employees']

		indicators = self.indicators

		indicators[self.indicator_name_order.index('Residential Density')]['value'
				   ]=residential_density_score
		indicators[self.indicator_name_order.index('Employment Density')]['value'
				   ]=employment_density_score
		indicators[self.indicator_name_order.index('Residential/Employment Ratio')]['value'
				   ]=min(residents, employees)/max(residents, employees) 

		# Update the amenity density scores                     
		total_people=residents+employees
		self.amenity_scores['quota']=total_people*self.amenity_scores['quota_per_k_people']/1e6
		self.amenity_scores['score']=self.amenity_scores.apply(lambda row: min(1,row['num_present']/row['quota']), axis=1)

		# TODO: aggregation should be a helper function as it's use in two scripts
		sub_cat_scores=self.amenity_scores.groupby('sub_cat').agg({'num_present': 'sum',
										 'score': 'mean',
										 'category': 'first'})
		# category density scores    
		cat_scores=sub_cat_scores.groupby('category').agg({'num_present': 'sum',
									 'score': 'mean'}) 
		for ind, row in cat_scores.iterrows():
			indicators[self.indicator_name_order.index('{} Density'.format(ind))]['value'
					   ]=row['score']  
		return indicators

def main():
	seashell = ShellIndicator(name='seashell')
	indicators = Density_Proximity(name="indicators")

	H = Handler('corktown', quietly=False)
	H.add_indicator(seashell)
	H.add_indicator(indicators)

	print(H.list_indicators())
	print(H.update_package())

	H.listen()

if __name__ == '__main__':
	main()
