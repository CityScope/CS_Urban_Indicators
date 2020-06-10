import pandas as pd
import json
from toolbox import Handler, Indicator
from indicator_tools import EconomicIndicatorBase, shannon_equitability_score

class DiversityIndicator(EconomicIndicatorBase):
    def setup(self ,*args,**kwargs):
        self.table_name='corktown'
        self.category='numeric'
        self.two_digit_naics_species=['11', '21', '22', '23', '31', '32', '33', 
                                      '42', '44', '45', '48', '49', '51', '52', 
                                      '53', '54', '55', '56', '61', '62', '71', 
                                      '72', '81', '92']
        self.third_place_naics_codes=['7224', '7225', '7211', 
                                    '4451', '4452', '4453' ]
        self.education_naics_codes=['6111', '6113', '6115', 
                                    '6116' ]


    def return_indicator(self,geogrid_data):
        industry_composition=self.grid_to_industries(geogrid_data)
        industry_species_counts={}
        third_place_species_counts={}
        education_species_counts={}
        for td_code in self.two_digit_naics_species:
            industry_species_counts[td_code]=sum([industry_composition[code] for 
                                 code in industry_composition if code[:2]==td_code])
        for tp_code in self.third_place_naics_codes:
            third_place_species_counts[tp_code]=sum([industry_composition[code] for 
                                 code in industry_composition if code==tp_code])
        for ed_code in self.education_naics_codes:
            education_species_counts[ed_code]=sum([industry_composition[code] for 
                                 code in industry_composition if code==ed_code])
    
        job_diversity=shannon_equitability_score([industry_species_counts[code] for code in industry_species_counts])
        third_diversity=shannon_equitability_score([third_place_species_counts[code] for code in third_place_species_counts])
        edu_diversity=shannon_equitability_score([education_species_counts[code] for code in education_species_counts])
        
        return [{'name': 'Diversity Jobs', 'value': job_diversity,'raw_value': job_diversity, 
                 'viz_type': self.viz_type, 'units': None},
                {'name': 'Diveristy Third Places', 'value': third_diversity, 'raw_value': third_diversity, 
                 'viz_type': self.viz_type, 'units': None},
                 {'name': 'Diveristy Education', 'value': edu_diversity, 'raw_value': edu_diversity,  
                 'viz_type': self.viz_type, 'units': None}]
        

def main():
    D = Diversity_Indicator()
    H = Handler('corktown', quietly=False)
    H.add_indicator(D)
#    geogrid_data=H.get_geogrid_data()
    H.listen()

if __name__ == '__main__':
	main()
