from toolbox import Handler
from proximity_indicator import ProxIndicator
from innovation_indicator import InnoIndicator
from mobility_indicator import MobilityIndicator
from aggregate_indicator import AggregateIndicator
from economic_indicator import EconomicIndicator

from statistics import mean

def main():
    I = InnoIndicator()    
    P = ProxIndicator(name='proximity',  category_in='heatmap', table_name='corktown')
    M = MobilityIndicator(name='mobility',  table_name='corktown')
    
#    2nd order indicators
    E = EconomicIndicator(innovation_indicator=I, name='Economic')
    
    swb_aggregation=[{'indicator': P, 'names': [
            'Access to education', 
#            'Access to employment',
            'Access to restaurants',
            'Access to groceries',
            'Access to parks'
            ]}]
       
    S=AggregateIndicator(name='Social Well-Being',
                              indicators_to_aggregate=swb_aggregation, 
                              agg_fun=mean)
    
    H = Handler('corktown', quietly=False)
    H.add_indicator(I)
    H.add_indicator(P)
    H.add_indicator(M)
    H.add_indicator(E)
    H.add_indicator(S)  

    H.listen()

if __name__ == '__main__':
	main()