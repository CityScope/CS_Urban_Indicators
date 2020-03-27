import requests
import webbrowser
import json
import Geohash
from warnings import warn
from time import sleep

class Handler:
	'''
	Class to handle the connection for indicators built based on data from the GEOGRID.

	The simplest usage is:
	> I = Indicator()
	> H = Handler('table_name')
	> H.add_indicator(I)
	> H.listen()

	Parameters
	----------
	table_name : str
		Table name to lisen to.
		https://cityio.media.mit.edu/api/table/table_name
	GEOGRIDDATA_varname : str (default='GEOGRIDDATA')
		Name of geogrid-data variable in the table API.
		The object located at:
		https://cityio.media.mit.edu/api/table/table_name/GEOGRIDDATA_varname
		will be used as input for the return_indicator function in each indicator class.
	GEOGRID_varname : str (default='GEOGRID')
		Name of variable with geometries.
	quietly : boolean (default=True)
		If True, it will show the status of every API call.
	'''
	def __init__(self, table_name, GEOGRIDDATA_varname = 'GEOGRIDDATA', GEOGRID_varname = 'GEOGRID', quietly=True):

		self.host = 'https://cityio.media.mit.edu/'
		self.table_name = table_name
		self.quietly = quietly

		self.sleep_time = 0.1
		self.nAttempts = 5

		self.front_end_url   = 'https://cityscope.media.mit.edu/CS_cityscopeJS/?cityscope='+self.table_name
		self.cityIO_get_url  = self.host+'api/table/'+self.table_name
		self.cityIO_post_url = self.host+'api/table/update/'+self.table_name
		
		self.GEOGRID_varname = GEOGRID_varname
		self.GEOGRIDDATA_varname = GEOGRIDDATA_varname

		self.indicators = {}
		self.grid_hash_id = None
		self.grid_hash_id = self.get_hash()

		self.previous_indicators = None
		self.previous_access = None

	def check_table(self):
		'''
		Prints the front end url for the table.
		'''
		print(self.front_end_url)

	def see_current(self,category='numeric'):
		'''
		Returns the current values of the indicators posted for the table.

		Parameters
		----------
		category : str (default='numeric')
			Category of the indicators.
			Choose either 'numeric', 'indicators', 'access', or 'heatmap'
			('access' and 'heatmap' refer to the same type)
		'''
		if category in ['numeric','indicators']:
			r = self._get_url(self.cityIO_get_url+'/indicators')
		elif category in ['heatmap','access']:
			r = self._get_url(self.cityIO_get_url+'/access')
		else:
			raise NameError('Indicator category should either be numeric, indicators, heatmap, or access. Current type: '+str(category))
		if r.status_code==200:
			return r.json()
		else:
			warn('Cant access cityIO hashes')
			return {}

	def list_indicators(self):
		'''
		Returns list of all indicator names.
		'''
		return [name for name in self.indicators]

	def indicator(self,name):
		'''
		Returns the indicator with the given name.

		Parameters
		----------
		name : str
			Name of the indicator
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
			if I.category not in set(['indicators','numeric','heatmap','access']):
				raise NameError('Indicator category should either be numeric, indicators, heatmap, or access. Current type: '+str(I.category))
			try:
				self._new_value(geogrid_data,indicatorName)
			except:
				warn('Indicator not working: '+indicatorName)

	def _new_value(self,geogrid_data,indicator_name):
		'''
		Formats the result of the indicator's return_indicator function.

		If indicator is numeric, the result is formatted as:
			[
				{
					'name':xxx, 
					'category':yyy, 
					'viz_type':zzz, 
					'value':value
				},
				{
					...
				},
				...
			]
		If indicator is access or heatmap, the result is formatted as a list of features:
			[
				feature1,
				feature2,
				...
			]
		with each feature formatted as:
			{
				'geometry':{
								...
							},
				'properties':{
								name: value,
								...
				}
			}
		'''
		I = self.indicators[indicator_name]

		if I.category in ['access','heatmap']:
			new_value = I.return_indicator(geogrid_data)
			if isinstance(new_value,list)|isinstance(new_value,tuple):
				if any(['geometry' not in v.keys() for v in new_value]):
					print('List returned by return_indicator function must be a valid list of features or a geojson: '+indicator_name)
				return new_value
			else:
				if ('features' in new_value.keys()):
					return new_value['features']
				else:
					raise NameError('Indicator returned invalid geojson:'+indicator_name)
		elif I.category in ['numeric','indicators']:
			new_value = I.return_indicator(geogrid_data)
			if isinstance(new_value,list)|isinstance(new_value,tuple):
				for i in range(len(new_value)):
					val = new_value[i]
					if not isinstance(val,dict):
						try:
							json.dumps(val)
							new_value[i] = {'value':val}
						except:
							warn('Indicator return invalid type:'+str(indicator_name))
				return list(new_value)
			else:
				if not isinstance(new_value,dict):
					try:
						json.dumps(new_value)
						new_value = {'value':new_value}
					except:
						warn('Indicator return invalid type:'+str(indicator_name))
				if ('name' not in new_value.keys()):
					new_value['name'] = indicator_name
				if ('category' not in new_value.keys())&(I.category is not None):
					new_value['category'] = I.category
				if ('viz_type' not in new_value.keys())&(I.viz_type is not None):
					new_value['viz_type'] = I.viz_type
				return [new_value]

	def update_package(self,geogrid_data=None,append=False):
		'''
		Returns the package that will be posted in CityIO.

		Parameters
		----------
		geogrid_data : dict (optional)
			Result of self.geogrid_data(). If not provided, it will be retrieved. 
		append : boolean (dafault=False)
			If True, it will append the new indicators to whatever is already there.

		Returns
		-------
		new_values : list
			Note that all heatmat indicators have been grouped into just one value.
		'''
		if geogrid_data is None:
			geogrid_data = self._get_grid_data()
		new_values = []
		new_features = []

		for indicator_name in self.indicators:
			try:
				if self.indicators[indicator_name].category in ['access','heatmap']:
					new_features += self._new_value(geogrid_data,indicator_name)
				else:
					new_values += self._new_value(geogrid_data,indicator_name)
			except:
				warn('Indicator not working:'+str(indicator_name))
		
		if append:
			if len(new_values)!=0:
				current = self.see_current()
				self.previous_indicators = current
				current = [indicator for indicator in current if indicator['name'] not in self.indicators.keys()]
				new_values += current

			if len(new_features)!=0:
				current_access = self.see_current(category='access')
				self.previous_access = current_access
				current_features = current_access['features']

				combined_features = {'non-points':[],'points':{}}
				for f in current_features:
					if f['geometry']['type']=='Point':
						lat,lon = f['geometry']['coordinates']
						combined_features['points'][Geohash.encode(lat,lon)] = f
					else:
						warn('WARNING: There are some features that will be overwritten. Function only preserves points.')

				for f in new_features:
					if f['geometry']['type']=='Point':
						lat,lon = f['geometry']['coordinates']
						hashed = Geohash.encode(lat,lon)
						if hashed in combined_features['points'].keys():
							new_properties = f['properties']
							for k in new_properties:
								combined_features['points'][hashed]['properties'][k] = new_properties[k]
						else:
							combined_features['points'][hashed] = f
					else:
						combined_features['non-points'].append(f)

				new_features = combined_features['non-points']+list(combined_features['points'].values())

		return {'numeric':new_values,'heatmap':{'features':new_features,'type':'FeatureCollection'}}
		
	def test_indicators(self):
		geogrid_data = self._get_grid_data()
		for indicator_name in self.indicators:
			self._new_value(geogrid_data,indicator_name)

	def get_hash(self):
		'''
		Retreives the GEOGRID hash from:
		http://cityio.media.mit.edu/api/table/table_name/meta/hashes
		'''
		r = self._get_url(self.cityIO_get_url+'/meta/hashes')
		if r.status_code==200:
			hashes = r.json()
			try:
				grid_hash_id = hashes[self.GEOGRIDDATA_varname]
			except:
				warn('WARNING: Table does not have a '+self.GEOGRIDDATA_varname+' variable.')
				grid_hash_id = self.grid_hash_id
		else:
			warn('Cant access cityIO hashes')
			sleep(1)
			grid_hash_id=self.grid_hash_id
		return grid_hash_id

	def _get_grid_data(self,include_geometries=False):
		r = self._get_url(self.cityIO_get_url+'/'+self.GEOGRIDDATA_varname)
		if r.status_code==200:
			geogrid_data = r.json()
		else:
			warn('WARNING: Cant access GEOGRID data')
			sleep(1)
			geogrid_data = None
	
		if include_geometries|any([I.requires_geometry for I in self.indicators.values()]):
			r = self._get_url(self.cityIO_get_url+'/'+self.GEOGRID_varname)
			if r.status_code==200:
				geogrid = r.json()
				for i in range(len(geogrid_data)):
					geogrid_data[i]['geometry'] = geogrid['features'][i]['geometry']
			else:
				warn('WARNING: Cant access GEOGRID data')
		return geogrid_data

	def _get_url(self,url,params=None):
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
			warn('FAILED TO RETRIEVE URL: '+url)
		return r

	def geogrid_data(self,include_geometries=False):
		'''
		Returns the geogrid data from:
		http://cityio.media.mit.edu/api/table/table_name/GEOGRIDDATA

		Parameters
		----------
		include_geometries : boolean (dafault=False)
			If True it will also add the geometry information for each grid unit.
		'''
		return self._get_grid_data(include_geometries=include_geometries)

	def perform_update(self,grid_hash_id=None,append=True):
		'''
		Performs single table update.

		Parameters
		----------
		grid_hash_id : str (optional)
			Current grid hash id. If not provided, it will retrieve it.
		append : boolean (dafault=True)
			If True, it will append the new indicators to whatever is already there.
		'''
		if grid_hash_id is None: 
			grid_hash_id = self.get_hash()	
		geogrid_data = self._get_grid_data()
		if not self.quietly:
			print('Updating table with hash:',grid_hash_id)

		new_values = self.update_package(geogrid_data=geogrid_data,append=append)

		if len(new_values['numeric'])!=0:
			r = requests.post(self.cityIO_post_url+'/indicators', data = json.dumps(new_values['numeric']))

		if len(new_values['heatmap']['features'])!=0:
			r = requests.post(self.cityIO_post_url+'/access', data = json.dumps(new_values['heatmap']))

		self.grid_hash_id = grid_hash_id

	def rollback(self):
		'''
		Handler class keeps track of the previous value of the indicators and access values.
		This function rollsback the current values to whatever the locally stored values are.
		See:
			> self.previous_indicators
			> self.previous_access
		'''
		r = requests.post(self.cityIO_post_url+'/indicators', data = json.dumps(self.previous_indicators))
		r = requests.post(self.cityIO_post_url+'/access', data = json.dumps(self.previous_access))

	def listen(self,showFront=True,append=False):
		'''
		Listen for changes in the table's geogrid and update all indicators accordingly. 
		You can use the update_package method to see the object that will be posted to the table.
		This method starts with an update before listening.

		Parameters
		----------
		showFront : boolean (default=True)
			If True, it will open the front-end URL in a webbrowser at start.
		append : boolean (dafault=False)
			If True, it will append the new indicators to whatever is already there.
		'''
		if not self.quietly:
			print('Table URL:',self.front_end_url)
			print('Testing indicators')
		self.test_indicators()

		if not self.quietly:
			print('Performing initial update')
			print('Update package example:')
			print(self.update_package())
		self.perform_update(append=append)

		if showFront:
			webbrowser.open(self.front_end_url, new=2)
		while True:
			sleep(self.sleep_time)
			grid_hash_id = self.get_hash()
			if grid_hash_id!=self.grid_hash_id:
				self.perform_update(grid_hash_id=grid_hash_id,append=append)

class Indicator:
	def __init__(self,*args,name=None,requires_geometry=False,category='numeric',viz_type='default',**kwargs):
		self.name = name
		self.category = category
		self.viz_type = viz_type
		self.requires_geometry = requires_geometry

		self.setup(*args,**kwargs)
		self.load_module()
		if self.category in ['heatmap','access']:
			self.viz_type = None

	def return_indicator(self,geogrid_data):
		'''
		Function must return either a dictionary, a list, or a number.
		When returning a dict follow the format:
		{'name': 'Sea-Shell','value': 1.00}
		'''
		return {}

	def setup(self):
		pass

	def load_module(self):
		pass

	def train(self):
		self.load_train_data()

	def load_train_data(self):
		pass
