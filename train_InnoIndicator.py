import numpy as np
import pandas as pd
import os
import joblib
import matplotlib.pyplot as plt

from toolbox import Handler,Indicator
from innovation_indicator import InnoIndicator
from indicator_tools import DataLoader

from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler, OneHotEncoder, PolynomialFeatures
from sklearn.linear_model import LogisticRegression, Lasso, Ridge, LinearRegression
from sklearn.model_selection import train_test_split, GridSearchCV, cross_val_predict
from sklearn.decomposition import PCA
from sklearn.base import TransformerMixin, BaseEstimator, clone
from sklearn.metrics import r2_score

class FactorExtractor(TransformerMixin, BaseEstimator):
	def __init__(self, factor):
		'''
		Custom transformer that selects the given features from a pandas DataFrame.
		This object can easily be integrated in a Pipeline. 
		'''
		self.factor = factor

	def transform(self, data):
		missing = set(self.factor).difference(data.columns)
		if len(missing)!=0:
			data = data.assign(MERGE_FLAG=np.nan)
			data = pd.merge(data,pd.DataFrame([],columns=['MERGE_FLAG']+list(missing)),how='left').drop('MERGE_FLAG',1)
		return data[self.factor]

	def fit(self, *_):
		return self

def param_search(pipelines,X,Y):
	best_params = {}

	param_grid = {'lasso__alpha': np.logspace(-5,0,6)}
	search = GridSearchCV(pipelines['Lasso'], param_grid, n_jobs=-1,cv=int(0.1*len(Y)))
	search.fit(X,Y)
	best_params = {**best_params,**search.best_params_}

	param_grid = {'ridge__alpha': np.logspace(-5,0,6),}
	search = GridSearchCV(pipelines['Ridge'], param_grid, n_jobs=-1,cv=int(0.1*len(Y)))
	search.fit(X,Y)
	best_params = {**best_params,**search.best_params_}
	return best_params


def CV_r2(model,X,Y):
	Y_pred = cross_val_predict(model,X,Y,cv=len(Y))
	return r2_score(Y, Y_pred)

def CV_test_model(test_pipelines,X,Y,draw_scatter=False,find_best_params=False):
	for model in test_pipelines.values():
		model.fit(X, Y)
	if find_best_params:
		best_params = param_search(test_pipelines,X,Y)
		print('Best Parameters:',best_params)

	if draw_scatter:
		plt.figure(figsize=(15,7))
		i=1
		for k in test_pipelines:
			model = test_pipelines[k]
			print('LeaveOneOut cross validation score {}:'.format(k))
			Y_pred = cross_val_predict(model,X,Y,cv=len(Y))
			print('\tR2 score:',print(r2_score(Y, Y_pred)))
			plt.subplot(1,len(test_pipelines),i)
			i+=1
			plt.plot(Y_pred,Y,'o')
	else:
		for k in test_pipelines:
			model = test_pipelines[k]
			print('LeaveOneOut cross validation score {}:'.format(k))
			print('\tR2 score:',CV_r2(model,X,Y))


def define_sks_pipeline(feature_list):

	numeric_features = feature_list
	numeric_transformer = Pipeline([
		('imputer',SimpleImputer()),
		('scaler', StandardScaler()),
		('cuadratic',PolynomialFeatures(degree=2))
	])

	preprocessor = ColumnTransformer([
		('num', numeric_transformer, numeric_features)
	])

	pipeline_r = Pipeline([
		('extractor',FactorExtractor(numeric_features)),
		('preprocessor', preprocessor),
		('ridge',Ridge(alpha=1.,max_iter=10000))
	])

	pipeline_l = Pipeline([
		('extractor',FactorExtractor(numeric_features)),
		('preprocessor', preprocessor),
		('lasso',Lasso(alpha=0.01,max_iter=10000))
	])

	return pipeline_r,pipeline_l


def define_kno_pipeline(feature_list):

	categorical_features = ['CBSAFP']
	numeric_features = [f for f in feature_list if f not in categorical_features]

	numeric_transformer = Pipeline([
	    ('imputer',SimpleImputer()),
	    ('scaler', StandardScaler()),
	    ('cuadratic',PolynomialFeatures(degree=2))
	])

	
	categorical_transformer = Pipeline([
	    ('imputer',SimpleImputer(strategy="constant",fill_value=0)),
	    ('onehot', OneHotEncoder(handle_unknown='ignore'))
	])

	preprocessor = ColumnTransformer([
	        ('num', numeric_transformer, numeric_features),
	        ('cat', categorical_transformer, categorical_features)
	])

	pipeline_r = Pipeline([
	    ('extractor',FactorExtractor(numeric_features+categorical_features)),
	    ('preprocessor', preprocessor),
	    ('ridge',Ridge(alpha=1.,max_iter=100000))
	])

	pipeline_l = Pipeline([
	    ('extractor',FactorExtractor(numeric_features+categorical_features)),
	    ('preprocessor', preprocessor),
	    ('lasso',Lasso(alpha=0.001,max_iter=100000))
	])
	return pipeline_r,pipeline_l


def train_sks_indicator(data,sks_model_path,test_model=True,draw_scatter=False,find_best_params=False):
	msa_skills = data.msa_skills
	skills_columns = msa_skills.drop('GEOID',1).columns.tolist()

	df = msa_skills
	df = df.assign(TOT_SKS=df[skills_columns].sum(1))
	for c in skills_columns:
	    df[c] = df[c]/df['TOT_SKS']

	df = pd.merge(df,data.nPats,how='inner')
	df = pd.merge(df,data.emp_msa.groupby('GEOID').sum().reset_index())
	df = df.assign(pats_pc = df['nPats']/df['pop'])

	X = df.drop(['GEOID','nPats','pop','pats_pc','TOT_EMP','TOT_SKS'],1)
	Y = np.log(df['pats_pc'].values)

	feature_list = X.columns.tolist()
	pipeline_r,pipeline_l = define_sks_pipeline(feature_list)

	if test_model:
		test_pipelines = {
			'Ridge': clone(pipeline_r), 
			'Lasso': clone(pipeline_l)
		}
		print('Testing SKS indicators')
		CV_test_model(test_pipelines,X,Y,draw_scatter=draw_scatter,find_best_params=find_best_params)

	pipeline_l.fit(X,Y)
	joblib.dump(pipeline_l,sks_model_path)


def train_kno_indicator(data,kno_model_path,test_model=True,draw_scatter=False,find_best_params=False):

	zip_knowledge = data.zip_knowledge
	knowledge_columns = zip_knowledge.drop('ZCTA5CE10',1).columns.tolist()

	df = zip_knowledge
	df = df.assign(TOT_KNO=df[knowledge_columns].sum(1))
	for c in knowledge_columns:
	    df[c] = df[c]/df['TOT_KNO']

	df = pd.merge(df,data.emp_zip.groupby('ZCTA5CE10').sum()[['TOT_EMP']].reset_index())
	df = pd.merge(df,data.emp_zip[['ZCTA5CE10','CBSAFP']].drop_duplicates())
	df = df.assign(ZCTA5CE10=('000'+df['ZCTA5CE10'].astype(str)).str[-5:])
	df = pd.merge(df,data.RECPI[['zipcode','state','RECPI','EQI','SFR']].rename(columns={'zipcode':'ZCTA5CE10'}))

	df = df[df['state'].isin(['MI','WI','IK','OH','IN','MN','IA','MO'])]
	df = df[df['SFR']>1]
	df = df[df['EQI']>0.0002041]


	X = df.drop(['ZCTA5CE10','TOT_KNO','state','TOT_EMP','RECPI','EQI','SFR'],1,errors='ignore')
	Y = df['EQI'].values
	Y = np.log(Y-min(Y)+0.000001)

	feature_list = X.columns.tolist()
	pipeline_r,pipeline_l = define_kno_pipeline(feature_list)

	if test_model:
		test_pipelines = {
			'Ridge': clone(pipeline_r), 
			'Lasso': clone(pipeline_l)
		}
		print('Testing KNO indicators')
		CV_test_model(test_pipelines,X,Y,draw_scatter=draw_scatter,find_best_params=find_best_params)

	pipeline_l.fit(X,Y)
	joblib.dump(pipeline_l,kno_model_path)


def main():
	modelPath      = 'tables/innovation_data'
	sks_model_path = os.path.join(modelPath,'sks_model.joblib')
	kno_model_path = os.path.join(modelPath,'kno_model.joblib')

	data = DataLoader()
	data.load_OCC_data()
	data.load_MSA_data()
	data.load_patent_data()
	data.load_onet_data()
	data.load_RECPI()

	train_sks_indicator(data,sks_model_path,test_model=False)
	train_kno_indicator(data,kno_model_path,test_model=False)

if __name__ == '__main__':
	main()