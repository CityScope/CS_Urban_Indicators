import pandas as pd
import json
from toolbox import Handler, Indicator
from indicator_tools import EconomicIndicatorBase, shannon_equitability_score, flatten_grid_cell_attributes, collect_grid_cell_counts

class DiversityIndicator(EconomicIndicatorBase):
    def setup(self ,*args,**kwargs):
        self.table_name='corktown'
        self.category='numeric'
        self.two_digit_naics_species=['11', '21', '22', '23', '31', '32', '33', 
                                      '42', '44', '45', '48', '49', '51', '52', 
                                      '53', '54', '55', '56', '61', '62', '71', 
                                      '72', '81', '92']
#        self.third_place_naics_codes=['7224', '7225', '7211', 
#                                    '4451', '4452', '4453' ]
        self.education_naics_codes=['6111', '6113', '6115', 
                                    '6116' ]
        parcel_data_loc='./tables/{}/geometry/{}_site_parcels_cs_types.geojson'.format(self.table_name, self.table_name)
        self.parcel_data=json.load(open(parcel_data_loc))
        self.school_type_to_NAICS={'School': '6111'}
        self.prepare_base_populations()
        
        

        
    def prepare_base_populations(self):
        # create dict of housing {'R2', 'R3', 'R5', 'R6'}
        self.housing_counts={'R1': 0, 'R2':0, 'R3':0, 'R4': 0,'R5':0, 'R6':0}
        self.education_counts={'6111':0, '6113':0, '6115':0, 
                                    '6116':0}
        self.third_place_counts={'2200':0, '2100':0, '7240':0}
        
        for feat in self.parcel_data['features']:
            area=feat['properties']['area_sqm']
            floor_area=feat['properties']['floor_area_sqm']
            if feat['properties']['CS_LU']=='Institutional':
                school_naics=self.school_type_to_NAICS[feat['properties']['school_type']]
                self.education_counts[school_naics]+=floor_area
            elif 'Residential' in feat['properties']['CS_LU']:
                if feat['properties']['ZONING'] in self.housing_counts:
                    self.housing_counts[feat['properties']['ZONING']]+=floor_area
            elif feat['properties']['CS_LU']=='Retail':
                self.third_place_counts['2200']+=0.9*floor_area
                self.third_place_counts['2100']+=0.1*floor_area
            elif feat['properties']['CS_LU']=='Park':
                self.third_place_counts['7240']+=area
            
    def return_indicator(self,geogrid_data):
        industry_composition=self.grid_to_industries(geogrid_data)
        industry_species_counts={}
#        third_place_species_counts={}
#        education_species_counts={}
        for td_code in self.two_digit_naics_species:
            industry_species_counts[td_code]=sum([industry_composition[code] for 
                                 code in industry_composition if code[:2]==td_code])
#        for tp_code in self.third_place_naics_codes:
#            third_place_species_counts[tp_code]=sum([industry_composition[code] for 
#                                 code in industry_composition if code==tp_code])
#        for ed_code in self.education_naics_codes:
#            education_species_counts[ed_code]=sum([industry_composition[code] for 
#                                 code in industry_composition if code==ed_code])
    
        job_diversity=shannon_equitability_score([industry_species_counts[code] for code in industry_species_counts])
#        third_diversity=shannon_equitability_score([third_place_species_counts[code] for code in third_place_species_counts])
#        edu_diversity=shannon_equitability_score([education_species_counts[code] for code in education_species_counts])
        
        # make copies of the baseline counts
        housing_counts={k:self.housing_counts[k] for k in self.housing_counts}
        education_counts={k:self.education_counts[k] for k in self.education_counts}
        third_place_counts={k:self.third_place_counts[k] for k in self.third_place_counts}
        
        all_new_LBCS=[]
        all_new_NAICS=[]
        for cell in geogrid_data:
            if cell['interactive']:
                lbcs_this_cell=flatten_grid_cell_attributes(
                        type_def=self.types_def[cell['name']], height=cell['height'],
                        attribute_name='LBCS', area_per_floor=self.geogrid_header['cellSize']**2,
                        return_units='floors')
                naics_this_cell=flatten_grid_cell_attributes(
                        type_def=self.types_def[cell['name']], height=cell['height'],
                        attribute_name='NAICS', area_per_floor=self.geogrid_header['cellSize']**2,
                        return_units='floors')
                all_new_LBCS.append(lbcs_this_cell)
                all_new_NAICS.append(naics_this_cell)
                
        all_new_LBCS_agg=collect_grid_cell_counts(all_new_LBCS)
        all_new_NAICS_agg=collect_grid_cell_counts(all_new_NAICS)
        
        area_one_floor=self.geogrid_header['cellSize']**2
        # for each education lbcs, add new
        # for each third_place lbcs add new
        for lbcs in third_place_counts:
            if lbcs in all_new_LBCS_agg:
                third_place_counts[lbcs]+=all_new_LBCS_agg[lbcs]*area_one_floor
        for naics in education_counts:
            if naics in all_new_NAICS_agg:
                education_counts[naics]+=all_new_NAICS_agg[naics]*area_one_floor
            
        # new_R5 = 80% of new housing
        # new_R6 = 20% of new housing 
        if '1100' in all_new_LBCS_agg:
            new_housing=all_new_LBCS_agg['1100']*area_one_floor
        else:
            new_housing=0
        housing_counts['R5']+=new_housing*0.8
        housing_counts['R6']+=new_housing*0.2
        
        third_diversity=shannon_equitability_score([third_place_counts[code] for code in third_place_counts])
        housing_diversity=shannon_equitability_score([housing_counts[code] for code in housing_counts])
        edu_diversity=shannon_equitability_score([education_counts[code] for code in education_counts])
        
        
        return [{'name': 'Diversity Jobs', 'value': job_diversity,'raw_value': job_diversity, 
                 'viz_type': self.viz_type, 'units': None},
                {'name': 'Diversity Third Places', 'value': third_diversity, 'raw_value': third_diversity, 
                 'viz_type': self.viz_type, 'units': None},
                 {'name': 'Diversity Education', 'value': edu_diversity, 'raw_value': edu_diversity,  
                 'viz_type': self.viz_type, 'units': None},
                  {'name': 'Diversity Housing', 'value': housing_diversity, 'raw_value': housing_diversity,  
                 'viz_type': self.viz_type, 'units': None}]
        

def main():
    D = DiversityIndicator()
    H = Handler('corktown', quietly=False)
    H.add_indicator(D)
#    geogrid_data=H.get_geogrid_data()
    H.listen()

if __name__ == '__main__':
	main()
