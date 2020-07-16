import requests
import webbrowser
import json
import Geohash
import joblib
import numpy as np
from warnings import warn
from time import sleep
from collections import defaultdict
from shapely.geometry import shape

def is_number(s):
	try:
		float(s)
		return True
	except:
		return False

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
	def __init__(self, table_name, GEOGRIDDATA_varname = 'GEOGRIDDATA', GEOGRID_varname = 'GEOGRID', quietly=True, host_mode ='remote' , reference=None):

		if host_mode=='local':
			self.host = 'http://127.0.0.1:5000/'
		else:
			self.host = 'https://cityio.media.mit.edu/'
		self.table_name = table_name
		self.quietly = quietly

		self.sleep_time = 0.5
		self.nAttempts = 5

		self.front_end_url   = 'https://cityscope.media.mit.edu/CS_cityscopeJS/?cityscope='+self.table_name
		self.cityIO_get_url  = self.host+'api/table/'+self.table_name
		self.cityIO_post_url = self.host+'api/table/update/'+self.table_name
		
		self.GEOGRID_varname = GEOGRID_varname
		self.GEOGRIDDATA_varname = GEOGRIDDATA_varname
		self.GEOGRID = None

		self.indicators = {}
		self.grid_hash_id = None
		self.grid_hash_id = self.get_hash()

		self.previous_indicators = None
		self.previous_access = None

		self.none_character = 0
        
		self.geogrid_props=None
		self.get_geogrid_props()

		self.reference =reference
        
	def check_table(self):
		'''
		Prints the front end url for the table.
		'''
		print(self.front_end_url)

	def see_current(self,indicator_type='numeric'):
		'''
		Returns the current values of the indicators posted for the table.

		Parameters
		----------
		indicator_type : str (default='numeric')
			Type of the indicator.
			Choose either 'numeric', 'access', or 'heatmap'
			('access' and 'heatmap' refer to the same type)
		'''
		if indicator_type in ['numeric']:
			r = self._get_url(self.cityIO_get_url+'/indicators')
		elif indicator_type in ['heatmap','access']:
			r = self._get_url(self.cityIO_get_url+'/access')
		else:
			raise NameError('Indicator type should either be numeric, heatmap, or access. Current type: '+str(indicator_type))
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

	def add_indicators(self,indicator_list,test=True):
		'''
		Same as add_indicator but it takes in a list of Indicator objects
		'''
		for I in indicator_list:
			self.add_indicator(I,test=test)


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
		I.link_table(self)
		if indicatorName in self.indicators.keys():
			warn('Indicator {} already exists and will be overwritten'.format(indicatorName))
		self.indicators[indicatorName] = I
		if test:
			geogrid_data = self._get_grid_data()
			if I.indicator_type not in set(['numeric','heatmap','access']):
				raise NameError('Indicator type should either be numeric, heatmap, or access. Current type: '+str(I.indicator_type))
			try:
				if I.is_composite:
					indicator_values = self.get_indicator_values(include_composite=False)
					self._new_value(indicator_values,indicatorName)
				else:
					self._new_value(geogrid_data,indicatorName)
			except:
				warn('Indicator not working: '+indicatorName)

	def return_indicator(self,indicator_name):
		'''
		Returns the value returned by return_indicator function of the selected indicator.

		Parameters
		----------
		indicator_name : str
			Name of the indicator. See:
			> self.list_indicators()
		'''
		geogrid_data = self._get_grid_data()
		I = self.indicators[indicator_name]
		if I.is_composite:
			indicator_values = self.get_indicator_values(include_composite=False)
			return I.return_indicator(indicator_values)
		else:
			return I.return_indicator(geogrid_data)

	def _format_geojson(self,new_value):
		'''
		Formats the result of the return_indicator function into a valid geojson (not a cityIO geojson)

		'''
		if isinstance(new_value,dict) and ('properties' in new_value.keys()) and ('features' in new_value.keys()):
			if (len(new_value['properties'])==1) and all([((not isinstance(f['properties'],dict))) and (is_number(f['properties'])) for f in new_value['features']]):
				# print('Type1B')
				for f in new_value['features']:
					f['properties'] = [f['properties']]
			else:
				# print('Type1')
				pass
			if all([(not isinstance(f['properties'],dict)) for f in new_value['features']]):
				for f in new_value['features']:
					feature_properties = f['properties']
					if len(feature_properties)<len(new_value['properties']):
						feature_properties+=[self.none_character]*(len(new_value['properties'])-len(feature_properties))
					elif len(feature_properties)>len(new_value['properties']):
						feature_properties = feature_properties[:new_value['properties']]
					f['properties'] = dict(zip(new_value['properties'],feature_properties))
			new_value.pop('properties')

		elif isinstance(new_value,dict) and ('features' in new_value.keys()):
			if all([(not isinstance(f['properties'],dict)) and isinstance(f['properties'],list) and (len(f['properties'])==1) for f in new_value['features']]):
				# print('Type2B')
				for f in new_value['features']:
					f['properties'] = {indicator_name:f['properties'][0]}
			elif all([(not isinstance(f['properties'],dict)) and is_number(f['properties']) for f in new_value['features']]):
				# print('Type2C')
				for f in new_value['features']:
					f['properties'] = {indicator_name:f['properties']}
			else:
				# print('Type2')
				pass

		elif isinstance(new_value,list) and all([(isinstance(f,dict) and 'geometry' in f.keys()) for f in new_value]):
			if all([is_number(f['properties']) for f in new_value]):
				# print('Type3B')
				for f in new_value:
					f['properties'] = {indicator_name:f['properties']}
			elif not all([isinstance(f['properties'],dict) for f in new_value]):
				raise NameError('Indicator returned invalid geojson or feature list:'+indicator_name)
			else:
				# print('Type3')
				pass
			new_value = {'features':new_value,'type':'FeatureCollection'}
		else:
			raise NameError('Indicator returned invalid geojson or feature list:'+indicator_name)

		for feature in new_value['features']:
			feature['properties'] = defaultdict(lambda: self.none_character,feature['properties'])
		return new_value

	def _new_value(self,geogrid_data,indicator_name):
		'''
		Formats the result of the indicator's return_indicator function.a

		If indicator is numeric, the result is formatted as:
			[
				{
					'name':xxx, 
					'indicator_type':yyy, 
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

		if I.indicator_type in ['access','heatmap']:
			new_value = I.return_indicator(geogrid_data)
			new_value = self._format_geojson(new_value)
			return [new_value]
		elif I.indicator_type in ['numeric']:
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
				if ('indicator_type' not in new_value.keys())&(I.indicator_type is not None):
					new_value['indicator_type'] = I.indicator_type
				if ('viz_type' not in new_value.keys())&(I.viz_type is not None):
					new_value['viz_type'] = I.viz_type
				return [new_value]


	def _combine_heatmap_values(self,new_values_heatmap):
		'''
		Combines a list of heatmap features (formatted as geojsons) into one cityIO GeoJson
		'''

		all_properties = set([])
		combined_features = {}
		for new_value in new_values_heatmap:
			for f in new_value['features']:
				if f['geometry']['type']=='Point':
					all_properties = all_properties|set(f['properties'].keys())
					lat,lon = f['geometry']['coordinates']
					hashed = Geohash.encode(lat,lon)
					
					if hashed in combined_features.keys():
						combined_features[hashed]['properties'] = {**combined_features[hashed]['properties'], **f['properties']} 
						combined_features[hashed]['properties'] = defaultdict(lambda: self.none_character,combined_features[hashed]['properties'])
					else:
						combined_features[Geohash.encode(lat,lon)] = f
				else:
					raise NameError('Only Points supported at this point')
		all_properties = list(all_properties)
		combined_features = list(combined_features.values())
		for f in combined_features:
			f['properties'] = [f['properties'][p] for p in all_properties]

		return {'type':'FeatureCollection','properties':all_properties,'features':combined_features}

	def get_indicator_values(self,include_composite=False):
		'''
		Calculates the current values of the indicators.
		Used for developing a composite indicator
		Only for numeric indicators
		'''
		geogrid_data = self.get_geogrid_data()
		new_values_numeric = []
		for indicator_name in self.indicators:
			I = self.indicators[indicator_name]
			if (I.indicator_type not in ['access','heatmap'])&(not I.is_composite):
				new_values_numeric += self._new_value(geogrid_data,indicator_name)
		indicator_values = {i['name']:i['value'] for i in new_values_numeric}
		if include_composite:
			for indicator_name in self.indicators:
				I = self.indicators[indicator_name]
				if (I.indicator_type not in ['access','heatmap'])&(I.is_composite):
					new_values_numeric += self._new_value(indicator_values,indicator_name)
		indicator_values = {i['name']:i['value'] for i in new_values_numeric}
		return indicator_values

	def update_package(self,geogrid_data=None,append=False):
		'''
		Returns the package that will be posted in CityIO.

		Parameters
		----------
		geogrid_data : dict (optional)
			Result of self.get_geogrid_data(). If not provided, it will be retrieved. 
		append : boolean (dafault=False)
			If True, it will append the new indicators to whatever is already there.

		Returns
		-------
		new_values : list
			Note that all heatmat indicators have been grouped into just one value.
		'''
		if geogrid_data is None:
			geogrid_data = self._get_grid_data()
		new_values_numeric = []
		new_values_heatmap = []

		for indicator_name in self.indicators:
			try:
				I = self.indicators[indicator_name]
				if I.indicator_type in ['access','heatmap']:
					new_values_heatmap += self._new_value(geogrid_data,indicator_name)
				elif not I.is_composite:
					new_values_numeric += self._new_value(geogrid_data,indicator_name)
			except:
				warn('Indicator not working:'+str(indicator_name))

		for indicator_name in self.indicators:
			I = self.indicators[indicator_name]
			if (I.is_composite)&(I.indicator_type not in ['access','heatmap']):
				indicator_values = {i['name']:i['value'] for i in new_values_numeric}
				new_values_numeric += self._new_value(indicator_values,indicator_name)

		# add ref values if they exist
		for new_value in new_values_numeric:
			if new_value['name'] in self.reference:
				new_value['ref_value']=self.reference[new_value['name']]
		
		if append:
			if len(new_values_numeric)!=0:
				current = self.see_current()
				self.previous_indicators = current
				current = [indicator for indicator in current if indicator['name'] not in self.indicators.keys()]
				new_values_numeric += current

			if len(new_values_heatmap)!=0:
				current_access = self.see_current(indicator_type='access')
				self.previous_access = current_access
				current_access = self._format_geojson(current_access)
				new_values_heatmap = [current_access]+new_values_heatmap

		new_values_heatmap = self._combine_heatmap_values(new_values_heatmap)
		return {'numeric':new_values_numeric,'heatmap':new_values_heatmap}
		
	def test_indicators(self):
		geogrid_data = self._get_grid_data()
		for indicator_name in self.indicators:
			if self.indicators[indicator_name].is_composite:
				indicator_values = self.get_indicator_values(include_composite=False)
				self._new_value(indicator_values,indicator_name)
			else:
				self._new_value(geogrid_data,indicator_name)
            
	def get_geogrid_props(self):
		'''
		Gets the GEOGRID properties defined for the table.
		These properties are not dynamic and include things such as the NAICS and LBCS composition of each lego type.
		'''
		if self.geogrid_props is None:
			r = self._get_url(self.cityIO_get_url+'/GEOGRID')
			if r.status_code==200:
				self.geogrid_props = r.json()['properties']
			else:
				warn('Cant access cityIO type definitions')
				sleep(1)


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
			if self.GEOGRID is None:
				r = self._get_url(self.cityIO_get_url+'/'+self.GEOGRID_varname)
				if r.status_code==200:
					geogrid = r.json()
					self.GEOGRID = geogrid
				else:
					warn('WARNING: Cant access GEOGRID data')
			for i in range(len(geogrid_data)):
				geogrid_data[i]['geometry'] = self.GEOGRID['features'][i]['geometry']
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

	def get_geogrid_data(self,include_geometries=False,as_df=False):
		'''
		Returns the geogrid data from:
		http://cityio.media.mit.edu/api/table/table_name/GEOGRIDDATA

		Parameters
		----------
		include_geometries : boolean (default=False)
			If True it will also add the geometry information for each grid unit.
		as_df: boolean (default=False)
			If True, it will return data as a DataFrame.
		'''
		geogrid_data = self._get_grid_data(include_geometries=include_geometries)
		if as_df:
			geogrid_data = pd.DataFrame(geogrid_data)
			if include_geometries:
				geogrid_data = gpd.GeoDataFrame(geogrid_data.drop('geometry',1),geometry=geogrid_data['geometry'].apply(lambda x: shape(x)))
		return geogrid_data

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
		if not self.quietly:
			print('Done with update')
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
	def __init__(self,*args,**kwargs):
		self.name = None
		self.indicator_type = 'numeric'
		self.viz_type = 'radar'
		self.requires_geometry = False
		self.model_path = None
		self.pickled_model = None
		self.int_types_def=None
		self.types_def=None
		self.geogrid_header=None
		self.is_composite = False
		self.tableHandler = None
		self.table_name = None
		for k in ['name','model_path','requires_geometry','indicator_type','viz_type']:
			if k in kwargs.keys():
				self.name = kwargs[k]
		if self.indicator_type in ['heatmap','access']:
			self.viz_type = None
		self.setup(*args,**kwargs)
		self.load_module()

	def _transform_geogrid_data_to_df(self,geogrid_data):
		'''
		Transform the geogrid_data to a DataFrame to be used by a pickled model.
		'''
		geogrid_data = pd.DataFrame(geogrid_data)
		if 'geometry' in geogrid_data.columns:
			geogrid_data = gpd.GeoDataFrame(geogrid_data.drop('geometry',1),geometry=geogrid_data['geometry'].apply(lambda x: shape(x)))
		return geogrid_data

	def link_table(self,table_name=None):
		'''
		Function used for developing the indicator.
		It retrieves the properties from GEOGRID/properties and links the table Handler.
		This should not be used for deploying the indicator.
		If the table_name is passed as a string, it will create an individual Handler for this indicator.
		The Handler will use this function to pass only the GEOGRID/properties

		Parameters
		----------
		table_name: str or Handler
			Name of the table or Handler object.
		'''
		if (table_name is None) & (self.table_name is None):
			raise NameError('Please provide a table_name to link')
		if table_name is None:
			table_name = self.table_name
		if isinstance(table_name,Handler):
			H = table_name
		else:
			H = Handler(table_name)
			self.tableHandler = H
		self.assign_geogrid_props(H)


	def get_geogrid_data(self,as_df=False):
		'''
		Returns the geogrid data from the linked table if there is any.
		(see link_table)

		Parameters
		----------
		as_df: boolean (default=False)
			If True, it will return data as a DataFrame.
		'''
		if self.tableHandler is not None:
			geogrid_data = self.tableHandler._get_grid_data(include_geometries=self.requires_geometry)
			if as_df:
				geogrid_data = pd.DataFrame(geogrid_data)
				if include_geometries:
					geogrid_data = gpd.GeoDataFrame(geogrid_data.drop('geometry',1),geometry=geogrid_data['geometry'].apply(lambda x: shape(x)))
			return geogrid_data
		else:
			return None
		

	def assign_geogrid_props(self, handler):
		'''
		Assigns the GEOGRID properties to the indicator.
		Takes care of filling
			self.types_def
			self.geogrid_header

		Parameters
		----------
		handler: Handler
			Instantiated object of the Handler class.
		'''
		geogrid_props = handler.geogrid_props
		self.int_types_def=geogrid_props['types']
		self.types_def = self.int_types_def.copy()
		if 'static_types' in geogrid_props:
			self.types_def.update(geogrid_props['static_types'])
		self.geogrid_header = geogrid_props['header']

	def restructure(self,geogrid_data):
		geogrid_data_df = self._transform_geogrid_data_to_df(geogrid_data)
		return geogrid_data_df

	def return_indicator(self,geogrid_data):
		'''
		Function must return either a dictionary, a list, or a number.
		When returning a dict follow the format:
		{'name': 'Sea-Shell','value': 1.00}
		'''
		if self.pickled_model is not None:
			geogrid_data_df = self.restructure(geogrid_data_df)
			return {'name': self.name, 'value': self.pickled_model.predict(geogrid_data_df)[0]}
		else:
			return {}

	def return_baseline(self,geogrid_data):
		'''
		In general, the baseline might want to use the geogrid_data, as it might need to access some information.
		For example, the baseline might be a heatmap that needs the coordinates of the table.
		'''
		return None


	def setup(self):
		pass

	def load_module(self):
		if self.model_path is not None:
			self.pickled_model = joblib.load(self.model_path)
			if self.name is None:
				self.name = self.model_path.split('/')[-1].split('.')[0]


class CompositeIndicator(Indicator):
	def setup(self,compose_function,selected_indicators=[],*args,**kwargs):
		self.compose_function = compose_function
		self.is_composite = True
		self.selected_indicators = selected_indicators

	def return_indicator(self, indicator_values):
		if len(self.selected_indicators)!=0:
			indicator_values = {k:indicator_values[k] for k in indicator_values if k in self.selected_indicators}
		try:
			value = self.compose_function(indicator_values)
		except:
			indicator_values = np.array([v for v in indicator_values.values()])
			value = self.compose_function(indicator_values)
		return [{'name': self.name, 'value': float(value), 'raw_value': None,'units': None,'viz_type': self.viz_type}]

