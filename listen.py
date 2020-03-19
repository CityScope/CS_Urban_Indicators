from toolbox import Handler
from density_proximity_indicator import Density_Proximity
from innovation_indicator import InnoIndicator

def main():
	density_proximity = Density_Proximity(name="density_proximity")
	innovation        = InnoIndicator(name="innovation")

	H = Handler('corktown', quietly=False)
	H.add_indicator(density_proximity)
	H.add_indicator(innovation)
	H.listen()

if __name__ == '__main__':
	main()