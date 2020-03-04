import requests
import re
import os
import sys
import zipfile
from io import BytesIO
from pathlib import Path
SHAPES_PATH = 'tables/shapes/'

def fetch(url,nAttempts=5,quietly=True):
    '''
    Attempts to retrieve the given url until status_code equals 200.
    '''
    attempts = 0
    success = False
    while (attempts<nAttempts)&(not success):
        if not quietly:
            print(url,'Attempt:',attempts)
        r = requests.get(url)
        if r.status_code==200:
            success=True
        else:
            attempts+=1
    return r

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

    fnames = set(re.findall(re.compile('tl_'+year_version+'_.._'+shape_level.lower()+'.zip'),r.text))
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

def main(shapesPath):
    Path(shapesPath).mkdir(parents=True, exist_ok=True)
    year_version = '2019'
    for shape_level in ['BG','TRACT','COUNTY','CBSA']:
        print(shape_level)
        getShapes(shape_level,year_version,shapesPath,quietly=False)

if __name__ == '__main__':
    try:
        SHAPES_PATH = sys.argv[1]
        print('Download path set to:',SHAPES_PATH)
    except:
        pass
    main(SHAPES_PATH)
    
