from toolbox import Handler, Indicator
from proximity_indicator import ProxIndicator
from innovation_indicator import InnoIndicator
from mobility_indicator import MobilityIndicator
from aggregate_indicator import AggregateIndicator
from economic_indicator import EconomicIndicator
from buildings_indicator import BuildingsIndicator

from statistics import mean

def main():
    # Individual Indicators
    I = InnoIndicator()    
    P = ProxIndicator(name='proximity',   indicator_type_in='numeric', table_name='corktown')
    P_hm = ProxIndicator(name='proximity',  indicator_type_in='heatmap', table_name='corktown')
    M = MobilityIndicator(name='mobility', table_name='corktown')
    B= BuildingsIndicator(name='buildings',  table_name='corktown')
    
    # 2nd order  individual indicators 
    E = EconomicIndicator(name='Economic',
                          table_name='corktown')
    
    for indicator in [
#            I,
            P, M, B, E]:
        indicator.viz_type='bar'
    
    H = Handler('corktown', quietly=False)
    H.add_indicator(I)
    H.add_indicator(P)
    H.add_indicator(P_hm)
    H.add_indicator(M)
    H.add_indicator(E)
    H.add_indicator(B)
    
    
    # Composite indicators    
    social_aggregation=[{'indicator': P_hm, 'names': [
            'Access to education', 
#            'Access to employment',
            'Access to restaurants',
            'Access to groceries',
            'Access to parks'
            ]}]
    
    social_agg_ind=AggregateIndicator(name='Social Well-Being',
                              indicators_to_aggregate=social_aggregation, 
                              agg_fun=mean)
    
    inno_aggregation=[{'indicator': I, 'names': [
            'District-knowledge', 
            'City-skills',
            'Region-funding'
            ]}]
    inno_agg_ind=AggregateIndicator(name='Innovation Potential',
                              indicators_to_aggregate=inno_aggregation, 
                              agg_fun=mean)
    
    mobility_agg=[{'indicator': M, 'names': [
            'Mobility CO2 Performance', 
            'Mobility Health Impacts'
            ]}]
    mobility_agg_ind=AggregateIndicator(name='Sustaiable Mobility',
                              indicators_to_aggregate=mobility_agg, 
                              agg_fun=mean)
    
    economic_agg=[{'indicator': E, 'names': [
            'Average Earnings', 
            'Industry Output'
            ]}]
    economic_agg_ind=AggregateIndicator(name='Local Economy',
                              indicators_to_aggregate=economic_agg, 
                              agg_fun=mean)
    
    buildings_agg=[{'indicator': B, 'names': [
            'Commercial Energy Performance', 
            'Residential Energy Performance'
            ]}]
    buildings_agg_ind=AggregateIndicator(name='Sustainable Buildings',
                              indicators_to_aggregate=buildings_agg, 
                              agg_fun=mean)
    
    for indicator in [social_agg_ind, 
                      inno_agg_ind, 
                      mobility_agg_ind,
                      economic_agg_ind,buildings_agg_ind ]:
        indicator.viz_type='radar'
           
    H.add_indicator(social_agg_ind)
    H.add_indicator(inno_agg_ind) 
    H.add_indicator(mobility_agg_ind) 
    H.add_indicator(economic_agg_ind) 
    H.add_indicator(buildings_agg_ind) 

    H.listen()

if __name__ == '__main__':
	main()