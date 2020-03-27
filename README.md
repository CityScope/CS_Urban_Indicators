# README

## Custom GEOGRID indicator (tldr)

Indicators are built as subclasses of the **Indicator** class, with three functions that need to be defined: *setup*, *load_module*, and *return_indicator*. The function *setup* acts like an *__init__* and can take any argument and is run when the object is instantiated. The function *load_module* is also run when the indicator in initialized, but it cannot take any arguments. Any inputs needed for *load_module* should be defined as properties in *setup*. The function *return_indicator* is the only required one and should take in a 'geogrid_data' object and return the value of the indicator either as a number, a dictionary, or a list of dictionaries/numbers. Sometimes, the indicator requires geographic information from the table to calculate it. To get geographic information from the table, set the property *requires_geometry* to True (see Noise heatmap as an example). 

The following example implements a diversity-of-land-use indicator:
```
from toolbox import Indicator
from toolbox import Handler

from numpy import log
from collections import Counter

class Diversity(Indicator):

	def setup(self):
		self.name = 'Entropy'

	def load_module(self):
		pass

	def return_indicator(self, geogrid_data):
		uses = [cell['land_use'] for cell in geogrid_data]
		uses = [use for use in uses if use != 'None']

		frequencies = Counter(uses)
		total = sum(frequencies.values(), 0.0)
		entropy = 0
		for key in frequencies:
			p = frequencies[key]/total
			entropy += -p*log(p)

		return entropy

div = Diversity()

H = Handler('corktown', quietly=False)
H.add_indicator(div)
H.listen()
```

## Custom accessibility indicator

The same class can be used to define a heatmap or accessiblity indicator, as opposed to a numeric indicator.
First, set the class property *category* equal to 'heatmap' or to 'access'. This will flag the indicator as a heatmap and will tell the Handler class what to do with it.
Second, make sure that the *return_indicator* function returns a list of features or a geojson. 
The example below shows an indicator that returns noise for every point in the center of a grid cell. Because this indicator needs the coordinates of table to return the geojson, it sets the property *requires_geometry* to True.

```
class Noise(Indicator):
    '''
    Example of Noise heatmap indicator for points centered in each grid cell.

    Note that this class requires the geometry of the table as input, which is why it sets:
    requires_geometry = True
    in the setup.

    '''
    def setup(self):
        self.category = 'heatmap'
        self.requires_geometry = True

    def load_module(self):
        pass

    def return_indicator(self, geogrid_data):
        features = []
        for cell in geogrid_data:
            feature = {}
            lat,lon = zip(*cell['geometry']['coordinates'][0])
            lat,lon = mean(lat),mean(lon)
            feature['geometry'] = {'coordinates': [lat,lon],'type': 'Point'}
            feature['properties'] = {self.name:random()}
            features.append(feature)
        out = {'type':'FeatureCollection','features':features}
        return out
```

## GEOGRID indicator tutorial - Diversity of land-use indicator

As an example, we'll build a diversity of land use indicator for the corktown table. The process is the same for any table, provided that it has a GEOGRID variable. Indicators are built as subclasses of the **Indicator** class, with three functions that need to be defined: *setup*, *load_module*, and *return_indicator*. The function *setup* acts like an *__init__* and can take any argument and is run when the object is instantiated. The function *load_module* is also run when the indicator in initialized, but it cannot take any arguments. Any inputs needed for *load_module* should be defined as properties in *setup*. The function *return_indicator* is the only required one and should take in a 'geogrid_data' object and return the value of the indicator either as a number, a dictionary, or a list of dictionaries/numbers. 

To start developing the diversity indicator, you can use the Handler class to get the geogrid_data that is an input of the *return_indicator* function.
```
from toolbox import Handler
H = Handler('corktown')
geogrid_data = H.geogrid_data()
```

The returned *geogrid_data* object depends on the table, but for corktown it looks like this:
```
[
	{
		'color': [0, 0, 0, 0],
		'height': 0.1,
		'id': 0,
		'interactive': True,
		'land_use': 'None',
		'name': 'empty',
		'tui_id': None
	},
	{
		'color': [247, 94, 133, 180],
		'height': [0, 80],
		'id': 1,
		'interactive': True,
		'land_use': 'PD',
		'name': 'Office Tower',
		'old_color': [133, 94, 247, 180],
		'old_height': [0, 10],
		'tui_id': None
	},
	{
		'color': [0, 0, 0, 0],
		'height': 0.1,
		'id': 2,
		'interactive': True,
		'land_use': 'None',
		'name': 'empty',
		'tui_id': None
	},
	...
]
```

We build the diversity indicator by delecting the 'land_use' variable in each cell and calculating the Shannon Entropy for this:
```
from numpy import log
from collections import Counter
uses = [cell['land_use'] for cell in geogrid_data]
uses = [use for use in uses if use != 'None']

frequencies = Counter(uses)

total = sum(frequencies.values(), 0.0)
entropy = 0
for key in frequencies:
	p = frequencies[key]/total
	entropy += -p*log(p)
```

Now, we wrap this calculation in the *return_indicator* in a Diversity class that inherits the properties from the Indicator module: 
```
from toolbox import Indicator
from numpy import log
from collections import Counter

class Diversity(Indicator):

	def setup(self):
		self.name = 'Entropy'

	def load_module(self):
		pass

	def return_indicator(self, geogrid_data):
		uses = [cell['land_use'] for cell in geogrid_data]
		uses = [use for use in uses if use != 'None']

		frequencies = Counter(uses)

		total = sum(frequencies.values(), 0.0)
		entropy = 0
		for key in frequencies:
			p = frequencies[key]/total
			entropy += -p*log(p)

		return entropy
```

Because this indicator is very simple, it does not need any parameters or data to calculate the value, which is why the *load_module* function is empty. The *setup* function defines the properties of the module, which in this case is just the name. 

Finally, we run the indicator by instantiating the new class and passing it to a Handler object:
```
from toolbox import Handler

div = Diversity()

H = Handler('corktown', quietly=False)
H.add_indicator(div)
H.listen()
```

## Industry-Occupation matrix

Data available at: 
```
https://www.bls.gov/oes/tables.htm
```

Download "National industry-specific and by ownership." The ownership part is not relevant, what matters is the industry specific. For 2018, download the file:
```
https://www.bls.gov/oes/special.requests/oesm18in4.zip
```

The data is available a multiple NAICS levels, with the 4-digit NAICS being the most fined grained that is complete. Due to privacy concerns, data at the 5 and 6 digit levels are available for select NAICS codes. Note that if we needed for example the 5-digit level, we would need to combine information from the 4-digit level with the 5-digit level to obtain the full picture where some industries would be at the 4-digit level and others at the 5-digit level. For now, we will just stick to the 4-digi level. If we needed to move up, we can simply aggregate from this level up. For 2018, the relevant file is:
```
nat4d_M2018_dl.xlsx
```

The script downloadIO.py takes care of everything by generating a csv file in tables/IO:
```
tables/IO/oesm18in4/nat4d_M2018_dl.csv
```

**IMPORTANT:** when using nat4d_M2018_dl.csv, we need to select a level of aggregation of the **occupations**. This is done by filtering the column 
*OCC_GROUP*. The options are:
```
major: 22 categories including 'Architecture and Engineering'
minor: 93 categories including 'Architects, Surveyors, and Cartographers' and 'Engineers'
broad: 455 categories including 'Marine Engineers and Naval Architects'; 'Surveyors, Cartographers, and Photogrammetrists'; Mechanical Engineers'; etc.
detailed: 808 categories
```

The column *TOT_EMP* has the employment in each occupation in each industry. 

## Locally download shapefiles

Running the following script will create an untracked directory in tables/shapes with shapefiles for census block groups, census tracts, and counties for 2019:
```
>> python download_shapeData.py
```

## Geofencing funcions

Most APIs provide data aggregated at a different geographic level (block groups, buildings, zip codes, etc.). Geofencing funcions are used to get the list of geographic zones within a given boundary. 

For example, to query the Zip Code Business Patterns API for information about Kendall Square area, we need to first know the zip codes within Kendall Square:
```
>> from geofence import getZips
>> bounds = gpd.read_file('tables/shapes/bounds/Kendall_bounds.shp').to_crs({'init':"EPSG:4326"})['geometry'].values[0]
>> zipcodeList = getZips(bounds=bounds)
```

Using the list of zip codes within Kendall, we can call the ZBP-API to get data for the number of companies and the number of employees within these zip codes. Note that ZBPCall is a wrapper that pings the ZBP-API with a default set of parameters:
```
>> from APICalls import ZBPCall
>> no_employees = ZBPCall(zipcodeList=zipcodeList)
```

Different zip codes overlap differently with our geofenced bounds. We can use the getOSMWeights function from geofence.py to weight each zip code based on the fraction of the volume of buildings that fall within our bounds:
```
>> form geofence import getOSMWeights
>> zipShapes = getZips(bounds=bounds,asList=False)
>> weights = getOSMWeights(bounds,zipShapes,'ZCTA5CE10',quietly=False)
```

Finally, we merge the weights with the query results and sum:
```
>> weighted = pd.merge(no_employees,weights.rename(columns={'ZCTA5CE10':'zip code'}))
>> weighted['weighted_EMP']   = weighted['EMP']*weighted['weight']
>> print(weighted[['weighted_EMP','weighted_ESTAB']].sum())
```