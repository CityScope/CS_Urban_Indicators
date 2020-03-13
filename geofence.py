import geopandas as gpd
import pandas as pd
import os
import osmnx as ox
from download_shapeData import SHAPES_PATH,SHAPE_LEVELS

def check_shapes(year_version = '2019',shapesPath=SHAPES_PATH):
    '''
    Check if shapes have been downloaded
    '''
    for shape_level in SHAPE_LEVELS:
        if not os.path.isdir(os.path.join(shapesPath,year_version+'_'+shape_level.lower())):
            raise NameError('Missing shapefiles for:',shape_level)

def getZips(bounds=None,cbsaCode=None,shapesPath=SHAPES_PATH,zipShapes=None,asList=True,quietly=True):
    '''
    Get the zipcodes for the given bounds or for the given cbsaCode

    Parameters
    ----------
    bounds : shapely.Polygon
        Polygon of bounds in WGS84 (EPSG:4326).
    cbsaCode : str
        CBSA Code of metro area to select
    shapesPath : str
        Path to shapes: SHAPES_PATH.
        > SHAPES_PATH  = 'tables/shapes/' 
    zipShapes : geopandas.GeoDataFrame (optional)
        If provided, it will not loaded. 
        Providing the shapes is preferred when running this function multiple times.
        > zipShapes = gpd.read_file(os.path.join(SHAPES_PATH,'2019_zcta5','tl_2019_us_zcta510','tl_2019_us_zcta510.shp'),dtype={'ZCTA5CE10':str})
        > getZips(bounds=bounds,zipShapes=zipShapes)
    asList : boolean (default=True)
        If True, it will return a list of zip codes. 
        If False, it will return all the columns of the filtered GeoDataFrame.
    quietly : boolean (default=True)
        Used for debugging.
        If true, it will print status.
    '''
    if not quietly:
        print('Checking shapes')
    check_shapes()
    if (bounds is None)&(cbsaCode is not None):
        if not quietly:
            print('Loading msa shapes')
        msas = gpd.read_file(os.path.join(SHAPES_PATH,'2019_cbsa','tl_2019_us_cbsa','tl_2019_us_cbsa.shp'),dtype={'ZCTA5CE10':str})
        bounds = msas[msas['GEOID']==cbsaCode].geometry.values[0]
    elif (bounds is None)&(cbsaCode is None):
        raise NameError('Must provide either cbsaCode or bounds')
    if zipShapes is None:
        if not quietly:
            print('Loading ZIP shapes')
        zipShapes = gpd.read_file(os.path.join(SHAPES_PATH,'2019_zcta5','tl_2019_us_zcta510','tl_2019_us_zcta510.shp'),dtype={'ZCTA5CE10':str})
    if not quietly:
        print('Filtering zips')
    zips = zipShapes[zipShapes.geometry.intersection(bounds).area!=0]
    if asList:
        zips = zips['ZCTA5CE10'].values.tolist()
    return zips

def match_polygons(left_df,right_df,left_id,right_id,quietly=True):
    '''
    Matches two GeoDataFrames with polygons enforcing a one to many match.

    Parameters
    ----------
    left_df : geopandas.GeoDataFrame
        Shapefile with polygons to be used as reference. Each polygon has a unique match in right_df.
    right_df : geopandas.GeoDataFrame
        Shapefile with polygons to be used as groups. Each polygon can have multiple matches in left_df.
    left_id : str
        Column in left_df to be considered as id.
    right_id : str
        Column in right_df to be considered as id.
    quietly : boolean (default=True)
        Used for debugging.
        If true, it will print status.

    Returns
    -------
    matched : pandas.DataFrame
        Table with left_id,right_id columns.
    '''
    matched = gpd.sjoin(left_df, right_df)
    matched = matched[[left_id,right_id]].drop_duplicates()
    count = matched.groupby(left_id).count().reset_index()
    repeatedSet = set(count[count[right_id]>1][left_id])
    if len(repeatedSet)!=0:
        if not quietly:
            print('Solving repeated matches')
        repeated = matched[matched[left_id].isin(repeatedSet)][[left_id,right_id]]
        repeated = pd.merge(repeated,left_df[[left_id,'geometry']].rename(columns={'geometry':'geometry_left'}))
        repeated = pd.merge(repeated,right_df[[right_id,'geometry']].rename(columns={'geometry':'geometry_right'}))
        repeated['area'] = [gb.intersection(gp).area for gb,gp in repeated[['geometry_left','geometry_right']].values]
        repeated = repeated.sort_values(by='area',ascending=False).groupby([left_id,right_id]).first()[[]].reset_index()
        matched = pd.concat([matched[~matched[left_id].isin(repeatedSet)],repeated])
    return matched

def getOSMWeights(bounds,patches,patchIdCol,buildingsRaw=None,quietly=True):
    '''
    Gets the weight for each polygon in patches to calculate variables within bounds. 
    It uses building shapes and heights from Open Street Map to infer the weights.

    Parameters
    ----------
    bounds : shapely.Polygon
        Bounds of area to calcualte indicators for.
    patches : geopandas.GeoDataFrame
        Table with shapes of patches for which data is available (e.g. census blocks, zip codes, etc)
    patchIdCol : str
        Name of column to be considered as the ID of each polygon in patches.
        E.g. the zipcode.
    buildingsRaw : geopandas.GeoDataFrame (optional)
        Raw buildings file downloaded from OSM using osmnx. 
        If not provided, it will be downloaded, which can take a while.
        > buildingsRaw = ox.footprints_from_polygon(limit.buffer(0.001),footprint_type='building')
    quietly : boolean (default=True)
        Used for debugging.
        If true, it will print status.

    Returns
    -------
    weights : pandas.DataFrame
        Table with patchIdCol,volume,intersected_volume, and weight.
    '''
    limit = patches.geometry.unary_union
    if buildingsRaw is None:
        if not quietly:
            print('Downloading OSM data')
        buildingsRaw = ox.footprints_from_polygon(limit.buffer(0.001),footprint_type='building')
    if not quietly:
        print('Downloading OSM data')
    buildings = buildingsRaw[buildingsRaw.geometry.within(limit)]
    buildings = buildings.reset_index().rename(columns={'index':'OSM_id'})
    buildings['area'] = buildings.geometry.area
    buildings['building:levels'] = buildings['building:levels'].fillna(1).astype(float)
    buildings['volume'] = buildings['area']*buildings['building:levels']
    buildings['intersected_area'] = buildings.geometry.intersection(bounds).area
    buildings['intersected_volume'] = buildings['volume']*buildings['intersected_area']/buildings['area']
    buildings = gpd.GeoDataFrame(buildings[['OSM_id','building:levels','area','volume','intersected_area','intersected_volume']],crs={'init':'epsg:4269'},geometry=buildings['geometry'])

    if not quietly:
        print('Matching buildings')
    matched = match_polygons(buildings, patches,'OSM_id',patchIdCol,quietly=quietly)
    matched = pd.merge(matched,buildings)
    
    weights = matched.groupby(patchIdCol).sum()[['volume','intersected_volume']].reset_index()
    weights['weight'] = weights['intersected_volume']/weights['volume']
    return weights


def getAreaWeights(bounds,patches,patchIdCol,quietly=True):
    '''
    Gets the weight for each polygon in patches to calculate variables within bounds. 
    It uses the fraction of the area overlapped by the bounds.
    This method is much faster than using OSM buildings, but much less precise.

    Parameters
    ----------
    bounds : shapely.Polygon
        Bounds of area to calcualte indicators for.
    patches : geopandas.GeoDataFrame
        Table with shapes of patches for which data is available (e.g. census blocks, zip codes, etc)
    patchIdCol : str
        Name of column to be considered as the ID of each polygon in patches.
        E.g. the zipcode.
    quietly : boolean (default=True)
        Used for debugging.
        If true, it will print status.

    Returns
    -------
    weights : pandas.DataFrame
        Table with patchIdCol,arrea,intersected_area, and weight.
    '''
    patches['area'] = patches.geometry.area
    patches['intersected_area'] = patches.geometry.intersection(bounds).area
    weights = patches[[patchIdCol,'area','intersected_area']]
    weights['weight'] = weights['intersected_area']/weights['area']
    return weights
