import requests
import json
from warnings import warn
from time import sleep

class Handler:
	'''
	Class to handle the connection for indicators built based on data from the GEOGRID.

	'''
	def __init__(self, table_name, GEOGRID_varname = 'GEOGRIDDATA', quietly=True):

		self.host = 'https://cityio.media.mit.edu/'
		self.table_name = table_name
		self.quietly = quietly

		self.sleep_time = 0.1
		self.nAttempts = 5

		self.cityIO_get_url  = self.host+'api/table/'+self.table_name
		self.cityIO_post_url = self.host+'api/table/update/'+self.table_name
		self.GEOGRID_varname = GEOGRID_varname

		self.indicators = {}
		self.grid_hash_id = None
		self.grid_hash_id = self.get_hash()

	def list_indicators(self):
		'''
		Returns list of all indicator names.
		'''
		return [name for name in self.indicators]

	def indicator(self,name):
		'''
		Returns the indicator with the given name.
		See list_indicators()
		'''
		return self.indicators[name]

	def add_indicator(self,I,test=True):
		'''
		Adds indicator to handler object.

		Parameters
		----------
		I : Indicator object
			Indicator object to handle.
			If indicator has name, this will use as identifier. 
			If indicator has no name, it will generate identifier.
		'''
		if not isinstance(I,Indicator):
			raise NameError('Indicator must be instance of Indicator class')
		if I.name is not None:
			indicatorName = I.name
		else:
			indicatorName = ('0000'+str(len(self.indicators)+1))[-4:]
		self.indicators[indicatorName] = I
		if test:
			geogrid_data = self._get_grid_data()
			self._new_value(geogrid_data,indicatorName)

	def _new_value(self,geogrid_data,indicator_name):
		I = self.indicators[indicator_name]
		new_value = I.return_indicator(geogrid_data)
		if isinstance(new_value,list)|isinstance(new_value,tuple):
			for i in range(len(new_value)):
				val = new_value[i]
				if not isinstance(val,dict):
					try:
						json.dumps(val)
						new_value[i] = {'value':val}
					except:
						warnings.warn('Indicator return invalid type:'+str(indicator_name))
			return list(new_value)
		else:
			if not isinstance(new_value,dict):
				try:
					json.dumps(new_value)
					new_value = {'value':new_value}
				except:
					warnings.warn('Indicator return invalid type:'+str(indicator_name))
			if ('name' not in new_value.keys()):
				new_value['name'] = indicator_name
			if ('category' not in new_value.keys())&(I.category is not None):
				new_value['category'] = I.category
			return [new_value]

	def update_package(self,geogrid_data=None):
		'''
		Returns the package that will be posted in CityIO.

		'''
		if geogrid_data is None:
			geogrid_data = self._get_grid_data()
		new_values = []
		for indicator_name in self.indicators:
			new_values+= self._new_value(geogrid_data,indicator_name)
		return new_values

	def _update_indicators(self,geogrid_data):
		'''
		Updates the indicators according to the given geogrid_data.
		'''
		new_values = self.update_package(geogrid_data=geogrid_data)
		r = requests.post(self.cityIO_post_url+'/indicators', data = json.dumps(new_values))

	def test_indicators(self):
		geogrid_data = self._get_grid_data()
		for indicator_name in self.indicators:
			self._new_value(geogrid_data,indicator_name)

	def get_hash(self):
		'''
		Retreives the GEOGRID hash from:
		http://cityio.media.mit.edu/api/table/table_name/meta/hashes
		'''
		r = self.get_url(self.cityIO_get_url+'/meta/hashes')
		if r.status_code==200:
			hashes = r.json()
			try:
				grid_hash_id = hashes[self.GEOGRID_varname]
			except:
				warnings.warn('WARNING: Table does not have a GEOGRIDDATA variable.')
				grid_hash_id = self.grid_hash_id
		else:
			warnings.warn('Cant access cityIO hashes')
			sleep(1)
			grid_hash_id=self.grid_hash_id
		return grid_hash_id

	def _get_grid_data(self):
		r = self.get_url(self.cityIO_get_url+'/'+self.GEOGRID_varname)
		if r.status_code==200:
			geogrid_data = r.json()
		else:
			warnings.warn('WARNING: Cant access GEOGRID data')
			sleep(1)
			geogrid_data = None
		return geogrid_data

	def get_url(self,url,params=None):
		attempts = 0
		success = False
		while (attempts < self.nAttempts)&(not success):
			if not self.quietly:
				print(url,'Attempt:',attempts)
			r = requests.get(url,params=params)
			if r.status_code==200:
				success=True
			else:
				attempts+=1
		if not success:
			warnings.warn('FAILED TO RETRIEVE URL: '+url)
		return r

	def geogrid_data(self):
		'''
		Returns the geogrid data from:
		http://cityio.media.mit.edu/api/table/table_name/GEOGRIDDATA
		'''
		return self._get_grid_data()

	def listen(self):
		self.test_indicators()
		while True:
			sleep(self.sleep_time)
			grid_hash_id = self.get_hash()
			if grid_hash_id!=self.grid_hash_id:
				geogrid_data = self._get_grid_data()
				self._update_indicators(geogrid_data)
				self.grid_hash_id = grid_hash_id

class Indicator:
	def __init__(self,name=None,category=None):
		self.name = name
		self.category = category

		self.setup()
		self.load_module()

	def return_indicator(self,geogrid_data):
		'''MUST return either a dictionary, a list, or a number'''
		return None

	def setup(self):
		pass

	def load_module(self):
		pass

	def train(self):
		self.load_train_data()

	def load_train_data(self):
		pass
