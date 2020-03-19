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

from numpy import log
from collections import Counter
class Diversity(Indicator):
	'''
	Example of a diversity of land use indicator
	'''
	def setup(self):
		self.name = 'Entropy'

	def load_module(self):
		pass

	def return_indicator(self, geogrid_data):
		uses = [cell['properties']['land_use'] for cell in geogrid_data['features']]
		uses = [use for use in uses if use != 'None']

		frequencies = Counter(uses)
		total = sum(frequencies.values(), 0.0)
		entropy = 0
		for key in frequencies:
			p = frequencies[key]/total
			entropy += -p*log(p)

		return entropy

def main():
	seashell = ShellIndicator(name='seashell')
	div = Diversity(name="land_use_diversity")

	H = Handler('corktown', quietly=False)
	H.add_indicator(seashell)
	H.add_indicator(div)

	print(H.geogrid_data())

	print(H.list_indicators())
	print(H.update_package())

	H.listen()

if __name__ == '__main__':
	main()
