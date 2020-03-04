import warnings
try:
    import censusgeocode as cg
except:
    warnings.warn("Module censusgeocode not available")
import requests
import time
import pandas as pd
import numpy as np


def get_OSM(address):
    '''
    Geocodes given address using Open Street Map.

    Returns
    -------
    r : dict
        Query results under r['results'], and request status under r['status'].
        If request fails r['status'] will be 'NOT_FOUND'
    '''
    base_url = 'https://nominatim.openstreetmap.org/search'
    query = {
        'q':address, #Free form string
        'format':'json',
        'polygon':1,
        'addressdetails':1,
        'namedetails':1
    }
    r = requests.get(base_url,params=query)
    return {'results':r.json(),'status':('OK' if len(r.json())>0 else 'NOT_FOUND')}

def get_census(address):
    '''
    Geocodes given address using census API.

    Returns
    -------
    r : dict
        Query results under r['results'], and request status under r['status'].
        If request fails r['status'] will be 'NOT_FOUND'
    '''
    try:
        r = cg.onelineaddress(address, returntype='locations')
        return {'results':r,'status':('OK' if len(r)>0 else 'NOT_FOUND')}
    except:
        return {'results':[],'status':'NOT_FOUND'}
    
class GAPI():
    '''
    Instanciated object can be used to query Google Geocoding API.

    Parameters
    ----------
    KEY : str
        Google Geocoding API KEY
    debug : boolean (optional, default=False)
        If True, it will not trigger a request.
    '''
    def __init__(self,KEY,debug=False,qLimit=35000):
        self.base_url = 'https://maps.googleapis.com/maps/api/geocode/json'
        self.distance_base_url = 'https://maps.googleapis.com/maps/api/distancematrix/json'
        self.over_limit = False
        self.GOOGLE_GEOCODING_API_KEY = KEY
        self.debug = debug
        self.time = time.time()
        self.QPS = 50.
        self.qLimit = qLimit
        self.qCount = 0
        self.pricePerQuery = 0.005

    def money_spent(self):
        '''
        Amount of money spent in queries so far.
        '''
        print('Total of',self.qCount,'queries')
        print('\tpaid',self.qCount*self.pricePerQuery,'USD')

    def get(self,address):
        '''
        Geocodes given address using Google API.

        Returns
        -------
        r : dict
            Query results under r['results'], and request status under r['status'].
            If request fails it will try until it goes through, unless its over query limit.
            If KEY exceedes query limit, then r['status']='OVER_QUERY_LIMIT'
        '''
        query = {'address':address,'key':self.GOOGLE_GEOCODING_API_KEY}
        if not self.over_limit:
            r = self._get(self.base_url,params=query)
            if r['status'] in set(['OVER_QUERY_LIMIT','OVER_DAILY_LIMIT']):
                self.over_limit = True
            return r
        else:
            return {'status':'OVER_QUERY_LIMIT','results':[]}

    def distance(self,origins,destinations,mode='all',departure_time=None,arrival_time=None,transit_mode='subway|bus'):
        '''
        Uses Google API to find travel times betweel all originas and destinations.

        Returns
        -------
        origins : list
            List of lat,lon coordinates
        destinations : list
            List of lat,lon coordinates
        mode : str (default='all')
            Choose form driving, walking, transit
        '''
        if len(origins)*len(destinations)>100:
            raise NameError('Number of elements per request exceeds limit:',len(origins)*len(destinations))
        if len(origins[0])>2:
            origins = [o[-2:] for o in origins]
            destinations = [d[-2:] for d in destinations]

        query = {'key':self.GOOGLE_GEOCODING_API_KEY,
        'origins':'|'.join(map(lambda x: ','.join(map(str,x)),origins)),
        'destinations':'|'.join(map(lambda x: ','.join(map(str,x)),destinations)),
        'arrival_time':arrival_time,'departure_time':departure_time,
        'transit_mode':transit_mode,'mode':mode}

        if mode == 'all':
            out = {'status':'all_modes'}
            for m in ['driving','walking','transit']:
                query['mode']=m
                r = self._get(self.distance_base_url,params=query)
                out[m] = r
        else:
            r = self._get(self.distance_base_url,params=query)
            out = {mode:r}
        return out

    def _getWrapper(self,url,params):
        if self.qCount>self.qLimit:
            raise NameError('Local query limit exceeded')
        r = requests.get(url,params=params).json()
        self.qCount+=1
        return r

    def _get(self,url,params={}):
        if not self.debug:
            while (time.time()-self.time)<60./self.QPS:
                time.sleep(1)
            self.time = time.time()
            # r = requests.get(url,params=params).json()
            r = self._getWrapper(url,params)
            while r['status']=='OVER_QUERY_LIMIT':
                print('OVER_QUERY_LIMIT')
                time.sleep(1)
                # r = requests.get(url,params=params).json()
                r = self._getWrapper(url,params)
            while r['status']=='OVER_DAILY_LIMIT':
                print('OVER_DAILY_LIMIT')
                time.sleep(3600)
                # r = requests.get(url,params=params).json()
                r = self._getWrapper(url,params)
        else:
            r = {'status':'OK','results':[]}
        return r
