# README

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