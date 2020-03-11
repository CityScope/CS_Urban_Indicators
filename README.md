# README

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