from toolbox import Handler
from density_diversity_indicator import Density_Diversity
from proximity_indicator import ProxIndicator
from innovation_indicator import InnoIndicator

def main():
	density_diversity = Density_Diversity()
#	innovation        = InnoIndicator()
	proximity         = ProxIndicator()  

	H = Handler('corktown', quietly=False)
	H.add_indicator(density_diversity)
#	H.add_indicator(innovation)
	H.add_indicator(proximity)
	H.listen()

if __name__ == '__main__':
	main()