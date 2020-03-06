import geopandas as gpd
import os
from download_shapeData import SHAPES_PATH,SHAPE_LEVELS

def check_shapes(year_version = '2019'):
    '''
    Check if shapes have been downloaded
    '''
    for shape_level in SHAPE_LEVELS:
        if not os.path.isdir(os.path.join(SHAPES_PATH,year_version+'_'+shape_level.lower())):
            raise NameError('Missing shapefiles for:',shape_level)

def getZips(bounds=None,cbsaCode=None,zipShapes=None,asList=True,quietly=True):
    '''
    Get the zipcodes for the given bounds or for the given cbsaCode

    Parameters
    ----------
    bounds : shapely.Polygon
        Polygon of bounds in WGS84 (EPSG:4326).
    cbsaCode : str
        CBSA Code of metro area to select
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