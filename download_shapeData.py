import requests
import re
import os
import sys
import zipfile
from io import BytesIO
from pathlib import Path
from APICalls import fetch
SHAPES_PATH  = 'tables/shapes/' 
SHAPE_LEVELS = ['BG','TRACT','COUNTY','CBSA','ZCTA5']

def getShapes(shape_level,year_version,shapesPath,base_url = 'https://www2.census.gov/geo/tiger/',quietly=True):
    '''
    Downloads and unzips shapefile data from census.gov/geo/tiger.

    Parameters
    ----------
    shape_level : str
        Shape level to query (e.g. BG, TRACT, COUNTY, CBSA, etc)
        See https://www2.census.gov/geo/tiger/TIGER2019/ for full list of options
    year_version : str
        Version year to use. 
        See https://www2.census.gov/geo/tiger/ for full list of options
    shapesPath : str
        Path where to save data to. 

    '''
    batch_path = os.path.join(shapesPath,year_version+'_'+shape_level.lower())
    Path(batch_path).mkdir(parents=True, exist_ok=True)
    url = base_url+'TIGER'+year_version+'/'+shape_level.upper()+'/'
    r = requests.get(url)
    if r.status_code!=200:
        raise NameError('URL not found, probably year does not exist. Status code:',r.status_code)

    fnames = set(re.findall(re.compile('tl_'+year_version+'_.._'+shape_level.lower()+'[^\.]*\.zip'),r.text))
    for fname in fnames:
        if not os.path.isdir(os.path.join(batch_path,fname.replace('.zip',''))):
            url_f = url+fname
            r = fetch(url_f,quietly=quietly)
            if r.status_code==200:
                if not quietly:
                    print('\tWriting file...')
                zipdata = BytesIO()
                zipdata.write(r.content)
                with zipfile.ZipFile(zipdata) as zip_ref:
                    zip_ref.extractall(os.path.join(batch_path,fname.replace('.zip','')))

def match_zip_bg(shapesPath,year_version):
    '''
    Matches block groups to zip codes.
    '''
    match_path = os.path.join(shapesPath,'ZIP_BG_matched_{}.csv'.format(year_version))
    if not os.path.isfile(match_path):
        zipShapes = gpd.read_file(os.path.join(shapesPath,year_version+'_zcta5','tl_{}_us_zcta510'.format(year_version),'tl_{}_us_zcta510.shp'.format(year_version)),dtype={'ZCTA5CE10':str})
        matched = []
        fnames = [os.path.join(shapesPath,year_version+'_bg',f,f+'.shp') for f in os.listdir(os.path.join(shapesPath,year_version+'_bg'))]
        for f in fnames:
            state = f.split('/')[-1].split('_')[2]
            print(state,f)
            bgs = gpd.read_file(f)

            small = bgs[['GEOID','geometry']]
            large = zipShapes[['ZCTA5CE10','geometry']]

            small = small[['GEOID','geometry']]
            large = large[['ZCTA5CE10','geometry']]
            matchRaw = gpd.overlay(small,large,how='intersection')
            match = matchRaw[matchRaw.columns]
            match['INT_AREA'] = match.geometry.area
            match = pd.merge(match,match.groupby('GEOID').sum()[['INT_AREA']].rename(columns={'INT_AREA':'TOT_AREA'}).reset_index())
            match['weight'] = match['INT_AREA']/match['TOT_AREA']

            match = match[match['weight']>0.1]
            match = pd.merge(match.drop('TOT_AREA',1),match.groupby('GEOID').sum()[['INT_AREA']].rename(columns={'INT_AREA':'TOT_AREA'}).reset_index())
            match['weight'] = match['INT_AREA']/match['TOT_AREA']

            match = match[['GEOID','ZCTA5CE10','weight']].drop_duplicates()
            match['STATE_FIPS'] = state
            matched.append(match)
        match = pd.concat(matched)
        match.to_csv(match_path,index=False)

def match_zip_msa(shapesPath,year_version='2019'):
    match_path = os.path.join(shapesPath,'ZIP_MSA_matched_{}.csv'.format(year_version))
    if not os.path.isfile(match_path):
        msas = gpd.read_file(os.path.join(SHAPES_PATH,'{}_cbsa'.format(year_version),'tl_{}_us_cbsa'.format(year_version),'tl_{}_us_cbsa.shp'.format(year_version)),dtype={'ZCTA5CE10':str})
        msas = msas[msas['LSAD']=='M1']
        zipShapes = gpd.read_file(os.path.join(SHAPES_PATH,'{}_zcta5'.format(year_version),'tl_{}_us_zcta510'.format(year_version),'tl_{}_us_zcta510.shp'.format(year_version)),dtype={'ZCTA5CE10':str})

        small = zipShapes[['ZCTA5CE10','geometry']]
        large = msas[['CBSAFP','geometry']]

        small = small[['ZCTA5CE10','geometry']]
        large = large[['CBSAFP','geometry']]
        matchRaw = gpd.overlay(small,large,how='intersection')
        match = matchRaw[matchRaw.columns]
        match['INT_AREA'] = match.geometry.area
        match = pd.merge(match,match.groupby('ZCTA5CE10').sum()[['INT_AREA']].rename(columns={'INT_AREA':'TOT_AREA'}).reset_index())
        match['weight'] = match['INT_AREA']/match['TOT_AREA']
        match = match.sort_values(by='weight',ascending=False).groupby(['ZCTA5CE10']).first().reset_index()[['ZCTA5CE10','CBSAFP']]
        match.to_csv(match_path,index=False)


def main(shapesPath):
    Path(shapesPath).mkdir(parents=True, exist_ok=True)
    year_version = '2019'
    for shape_level in SHAPE_LEVELS:
        print(shape_level)
        getShapes(shape_level,year_version,shapesPath,quietly=False)

    if not os.path.isfile(os.path.join(shapesPath,'ZIP_BG_matched_{}.csv'.format(year_version))):
        print('Matching BGs and ZIPs')
        match_zip_bg(shapesPath,year_version)


if __name__ == '__main__':
    try:
        SHAPES_PATH = sys.argv[1]
        print('Download path set to:',SHAPES_PATH)
    except:
        pass
    main(SHAPES_PATH)
    
