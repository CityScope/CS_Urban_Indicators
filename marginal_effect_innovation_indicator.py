import pandas as pd
import numpy as np
import joblib
import os
from innovation_indicator import InnoIndicator
from indicator_tools import DataLoader
from APICalls import CBPCall

def industry_to_skills_knowledge(Xdiff,I):
	industry_compositions = Xdiff.to_dict('records')
	skill_compositions = []
	knowledge_compositions = []
	for industry_composition in industry_compositions:
		worker_composition    = I.industries_to_occupations(industry_composition)
		skill_composition     = I.occupations_to_skills(worker_composition)
		knowledge_composition = I.occupations_to_knowledge(worker_composition)
		skill_compositions.append(skill_composition)
		knowledge_compositions.append(knowledge_composition)
	return skill_compositions,knowledge_compositions

def AME_industry(I,col,X):
	'''
	Numbers should be interpreted as the change in the average indicator (over all X) as a result of a 0.1 increase in the given NAICS code
	'''
	dx = np.median(np.diff(sorted(X[X[col]!=0][col])))

	X_ = X.reset_index().drop('index',1)
	X_[col] = X[col]+dx
	Xdiff = pd.concat([X.reset_index().drop('index',1),X_]).sort_index().sort_values(by=col).sort_index()

	skill_compositions,knowledge_compositions = industry_to_skills_knowledge(Xdiff,I)

	Ypred = I.sks_model.predict(pd.DataFrame(skill_compositions))
	if I.normalize:
		Ypred = I.normalize_value(Ypred,I.sks_bounds)
	dsks = np.diff(Ypred)[::2]
	dsksdx = (dsks/dx)*0.1

	Ypred = I.kno_model.predict(pd.DataFrame(knowledge_compositions))
	if I.normalize:
		Ypred = I.normalize_value(Ypred,I.kno_bounds)
	dkno = np.diff(Ypred)[::2]
	dknodx = (dkno/dx)*0.1

	return np.mean(dsksdx),np.mean(dknodx)

def main():
	outPath = 'tables/innovation_data'
	outfpath = os.path.join(outPath,'innovation_marginal_effect.csv')
	if os.path.isfile(outfpath):
		print('Marginal effects already stored. To recompute, delete the current results located at: {}'.format(outfpath))
	else:
		print('Loading indicator and employment by industry for each MSA')
		I = InnoIndicator()

		data = DataLoader()
		data.load_MSA_emp_byInd()

		X = pd.pivot_table(data.emp_msa_ind,values='EMP',index='MSA',columns='NAICS2017').fillna(0)
		X = X.assign(TOTAL=X.sum(1))
		for c in set(data.emp_msa_ind['NAICS2017']):
		    X[c] = X[c]/X['TOTAL']
		X = X.drop('TOTAL',1)
		X = X.reset_index().drop('MSA',1)

		kno_ames = {}
		sks_ames = {}
		for col in X.columns:
			print('\tDerivating with respect to NAICS: {}'.format(col))
			sks_ame,kno_ame = AME_industry(I,col,X)
			sks_ames[col] = sks_ame
			kno_ames[col] = kno_ame

		print('Combining and saving results')
		ames = pd.DataFrame(sks_ames.items(),columns=['NAICS','SKS_AME'])
		ames = pd.merge(ames,pd.DataFrame(kno_ames.items(),columns=['NAICS','KNO_AME']))
		ames.to_csv(outfpath,index=False)

if __name__ == '__main__':
	main()