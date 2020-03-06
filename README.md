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
>> df = ZBPCall(zipcodeList=zipcodeList)
```
