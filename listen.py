from toolbox import Handler, Indicator, CompositeIndicator
from proximity_indicator import ProxIndicator
from innovation_indicator import InnoIndicator
from mobility_indicator import MobilityIndicator
from aggregate_indicator import AggregateIndicator
from economic_indicator import EconomicIndicator
from buildings_indicator import BuildingsIndicator
from diversity_indicator import DiversityIndicator

from statistics import mean

def main():
    # Individual Indicators
    I = InnoIndicator()    
    P = ProxIndicator(name='proximity',   indicator_type_in='numeric', table_name='corktown')
    P_hm = ProxIndicator(name='proximity_heatmap',  indicator_type_in='heatmap', table_name='corktown')
    M = MobilityIndicator(name='mobility', table_name='corktown')
    B= BuildingsIndicator(name='buildings',  table_name='corktown')
    D= DiversityIndicator(name='diversity',  table_name='corktown')
    
    # 2nd order  individual indicators 
    E = EconomicIndicator(name='Economic',
                          table_name='corktown')
    
    for indicator in [
            I,
            P, 
            M, B, E,
            D]:
        indicator.viz_type='bar'
    
    H = Handler('corktown', quietly=False)
    
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
                       selected_indicators=['Access to housing','Access to restaurants', 
                                            'Access to education', 'Access to groceries',
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
	main()