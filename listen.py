from toolbox import Handler, Indicator, CompositeIndicator
from proximity_indicator import ProxIndicator
from innovation_indicator import InnoIndicator
from mobility_indicator import MobilityIndicator
from economic_indicator import EconomicIndicator
from buildings_indicator import BuildingsIndicator
from diversity_indicator import DiversityIndicator

import sys
import json

from statistics import mean

def main(host_mode='remote', table_name='corktown_dev'):
    reference=json.load(open('./tables/{}/reference.json'.format(table_name)))
    if host_mode=='local':
        host = 'http://127.0.0.1:5000/'
    else:
        host = 'https://cityio.media.mit.edu/'
    # Individual Indicators
    I = InnoIndicator()    
    P = ProxIndicator(name='proximity',   host=host, indicator_type_in='numeric', table_name=table_name)
    P_hm = ProxIndicator(name='proximity_heatmap',  host=host, indicator_type_in='heatmap', table_name=table_name)
    M = MobilityIndicator(name='mobility', table_name=table_name)
    B= BuildingsIndicator(name='buildings',  host=host,table_name=table_name)
    D= DiversityIndicator(name='diversity',  table_name=table_name)
    
    # 2nd order  individual indicators 
    E = EconomicIndicator(name='Economic',
                          table_name=table_name)
    
    for indicator in [
            I,
            P, 
            M, B, E,
            D]:
        indicator.viz_type='bar'
    
    H = Handler(table_name, quietly=False, host_mode=host_mode, reference=reference)
    
    H.add_indicators([
            I,
            P,
            P_hm,
            M,
            E,
            B,
            D
            ])
    
    comp_I = CompositeIndicator(mean,
                               selected_indicators=['Knowledge','Skills','R&D Funding'],
                               name='Innovation Potential')
    
    comp_M = CompositeIndicator(mean,
                               selected_indicators=['Mobility CO2 Performance','Mobility Health Impacts'],
                               name='Sustainable Mobility')
    
    comp_E = CompositeIndicator(mean,
                               selected_indicators=['Average Salary','Productivity','Employment Density', 'Diversity Jobs'],
                               name='Economic Performance')
    
    comp_B = CompositeIndicator(mean,
                           selected_indicators=['Buildings Energy Performance'],
                           name='Sustainable Buildings')
    
    comp_SW = CompositeIndicator(mean,
                       selected_indicators=['Access to housing', 
                                            'Access to education', 'Access to 3rd Places',
                                            'Access to parks', 'Access to employment', 'Diversity Jobs',
                                            'Diversity Third Places', 'Diversity Education'],
                       name='Community Benefits')
       
    for indicator in [
            comp_I,
            comp_M,
            comp_E,
            comp_B,
            comp_SW
            ]:
        indicator.viz_type='radar'
    
    H.add_indicators([
            comp_I,
            comp_M,
            comp_E,
            comp_B,
            comp_SW
            ])

    H.listen()

if __name__ == '__main__':
    if len(sys.argv)>1:
        table_name=sys.argv[1]
    else:
        table_name='corktown_dev'
    print('Running for table named {} on city_IO'.format(table_name))
    main(table_name=table_name)