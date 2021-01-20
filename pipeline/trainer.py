from data_loader.data_loader import DataLoader

from featureselector.featureselector import FeatureSelector

from gensim.models.fasttext import FastText
from gensim.models import KeyedVectors
from gensim.scripts.glove2word2vec import glove2word2vec

import pandas as pd

import numpy as np

import os

from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import normalize, StandardScaler 

from trainers.dbscan import DBScan
from trainers.isolationforest import IsoForest
from trainers.lof import LOF
from trainers.rrcf import RRCF
from trainers.ocsvm import OneClassSVM
from trainers.copod import CopulaPOD
from trainers.hbos import HistoBOS

from utils.engineer_functions import temp_new_text


class Trainer:
    def __init__(self, **kwargs):
        valid_keys = ["config", "comet_config", "model_config", "experiment", "model", "text_represent", "feature_select","normalize"]
        for key in valid_keys:
            setattr(self, key, kwargs.get(key))
        self.model_data_loader = DataLoader(self.config.model.save_data_path)
        self.model_data = None
        self.text_represent_data = None
        self.modelling_data = None
        self.trainer = None

    def load_data(self):
        self.model_data = self.get_model_data()

    def get_model_data(self):
        self.model_data_loader.load_data()
        return self.model_data_loader.get_data()
    
    def get_tfidf_vector(self):
        print("Generating TFIDF Vector...")
        vec = TfidfVectorizer (ngram_range = (1,2),min_df=0.1,max_df=0.9)
        reviews = temp_new_text(list(self.model_data['cleaned_reviews_text']))
        tfidf_reviews = vec.fit_transform(reviews)
        tfidf_reviews_df = pd.DataFrame(tfidf_reviews.toarray(), columns=vec.get_feature_names())
        
        return tfidf_reviews_df.fillna(value=0)

    def get_fasttext_vector(self):
        # parameters to train fast text
        embedding_size = 300
        window_size = 5
        min_word = 5
        down_sampling = 1e-2

        print("Generating Vector with fastText...")
        reviews = temp_new_text(list(self.model_data['cleaned_reviews_text']))

        ft_model = FastText(reviews,
                      size=embedding_size,
                      window=window_size,
                      min_count=min_word,
                      sample=down_sampling,
                      sg=0, # put 1 if you want to use skip-gram, look into the documentation for other variables
                      iter=100)
        
        vec = CountVectorizer(ngram_range = (1,1))
        ft_reviews_df = pd.DataFrame(columns=vec.get_feature_names())
        for i in range(len(reviews)):
            doc = reviews[i]
            words = doc.split()
            for word in words:
                try:
                    vector_value = np.mean(ft_model.wv[word])
                except:
                    vector_value = np.zeros(embedding_size)
                    
                ft_reviews_df.at[i, word] = vector_value
        
        return ft_reviews_df.fillna(value=0)
    
    def get_glove_vector(self):
        word2vec_output_file = 'data/uc2/external/glove.6B.300d.txt.word2vec' 
        if not os.path.exists(word2vec_output_file):
            # retrieve glove vector
            glove_input_file = 'data/uc2/external/glove.6B.300d.txt'
            glove2word2vec(glove_input_file, word2vec_output_file)

        # load the Stanford GloVe model, 
        glove_model = KeyedVectors.load_word2vec_format(word2vec_output_file, binary=False)
        
        print("Generating Vector with GloVe...")
        reviews = temp_new_text(list(self.model_data['cleaned_reviews_text']))
        
        vec = CountVectorizer(ngram_range = (1,1))
        glove_reviews_df = pd.DataFrame(columns=vec.get_feature_names())
        for i in range(len(reviews)):
            doc = reviews[i]
            words = doc.split()
            for word in words:
                try:
                    vector_value = np.mean(glove_model.wv[word])
                except:
                    vector_value = np.zeros(300)
                    
                glove_reviews_df.at[i, word] = vector_value
        
        return glove_reviews_df.fillna(value=0)
    
    def get_modelling_data(self):
        unnessary_columns = ['asin','acc_num','cleaned_reviews_profile_link','cleaned_reviews_text']
        modelling_df = self.model_data
        modelling_df = modelling_df.drop(columns=unnessary_columns)
        modelling_df = modelling_df.fillna(value=0)
        
        if self.feature_select == 'y':
            print("Proceeding with Feature Selection...")
            feature_selector = FeatureSelector(modelling_df)
            important_features = feature_selector.select_features()
            modelling_df = modelling_df[important_features]
        
        if self.normalize == 'y':
            print("Normalizing Data...")
            modelling_df = self.normalize_data()

        if self.text_represent == 'tfidf':
            self.text_represent_data = self.get_tfidf_vector()
        elif self.text_represent == 'fasttext':
            self.text_represent_data = self.get_fasttext_vector()
        elif self.text_represent == 'glove':
            self.text_represent_data = self.get_glove_vector()            
            
        print("Combining vectors with dataset...")
        return pd.concat([modelling_df, self.text_represent_data],axis=1)

    def normalize_data(self):
        scaler = StandardScaler() 
        X_scaled = scaler.fit_transform(self.modelling_data) 

        # Normalizing the data so that the data, approximately follows a Gaussian distribution 
        X_normalized = normalize(X_scaled) 

        # Converting the numpy array into a pandas DataFrame 
        X_normalized = pd.DataFrame(X_normalized) 
        
        # Renaming the columns 
        X_normalized.columns = self.modelling_data.columns 
        
        return X_normalized

    def train_model(self):
        print("Retrieving necessary columns for modelling...")
        self.modelling_data = self.get_modelling_data()

        if self.model == "dbscan":
            metrics, results = self.dbscan_pipeline()
        elif self.model == "isolation_forest":
            metrics, results = self.isolation_forest_pipeline(False)
        elif self.model == "eif":
            metrics, results = self.isolation_forest_pipeline(True)
        elif self.model == "lof":
            metrics, results = self.lof_pipeline()
        elif self.model == "rrcf":
            metrics, results = self.rrcf_pipeline()
        elif self.model == "ocsvm":
            metrics, results = self.ocsvm_pipeline()
        elif self.model == "copad":
            metrics, results = self.copad_pipeline()
        elif self.model == "hbos":
            metrics, results = self.hbos_pipeline()
            
        self.model_data['fake_reviews'] = [1 if x == -1 else 0 for x in results]

        print("Saving results...")
        self.save_results(metrics)

    def experiment_params(self,params):
        self.experiment.log_parameters(params)

    def save_results(self,metrics):
        self.experiment.log_metrics(metrics)
        
        results_path = {
            "dbscan" : self.model_config.dbscan.results.save_data_path,
            "isolation_forest": self.model_config.isolation_forest.results.save_data_path,
            "eif" : self.model_config.eif.results.save_data_path,
            "lof" : self.model_config.lof.results.save_data_path,
            "rrcf" : self.model_config.rrcf.results.save_data_path,
            "ocsvm" : self.model_config.ocsvm.results.save_data_path,
            "copad" : self.model_config.copad.results.save_data_path,
            "hbos" : self.model_config.hbos.results.save_data_path
            }

        self.model_data.to_csv(results_path[self.model],index=False)
        self.experiment.log_model(name=self.model,
                        file_or_folder=results_path[self.model])

    def dbscan_pipeline(self):
        print("Loading DBScan...")
        self.trainer = DBScan(model_config = self.model_config, model_df = self.modelling_data)
        params = self.trainer.hypertune_dbscan_params()

        print("Parsing parameters to Experiment...\nTesting parameters: {}".format(params))
        self.experiment_params(params)

        results = self.trainer.dbscan_cluster(params)
        
        self.model_data['dbscan_clusters'] = results

        metrics = self.trainer.evaluate_dbscan(results)
        
        return metrics, results
    
    def isolation_forest_pipeline(self, extended):
        if extended:
            print("Loading Extended Isolation Forest...")
        else:
            print("Loading Isolation Forest...")
        self.trainer = IsoForest(model_config = self.model_config, model_df = self.modelling_data)

        params = self.trainer.make_isolation_forest(extended)

        print("Parsing parameters to Experiment...\nTesting parameters: {}".format(params))
        self.experiment_params(params)

        results = self.trainer.predict_anomalies(extended)

        if extended:
            self.model_data['eif'] = results
        else:
            self.model_data['isolation_forest'] = results

        metrics = self.trainer.evaluate_isolation_forest(results,extended)
    
        return metrics, results
    
    def lof_pipeline(self):
        print("Loading Local Outlier Factor...")
        self.trainer = LOF(model_config = self.model_config, model_df = self.modelling_data)

        params = self.trainer.make_lof()

        print("Parsing parameters to Experiment...\nTesting parameters: {}".format(params))
        self.experiment_params(params)

        results = self.trainer.predict_anomalies()

        self.model_data['lof'] = results

        metrics = self.trainer.evaluate_lof(results)
    
        return metrics, results

    def rrcf_pipeline(self):
        print("Loading Robust Random Cut Forest...")
        self.trainer = RRCF(model_config = self.model_config, model_df = self.modelling_data)

        params = self.trainer.make_rrcf()

        print("Parsing parameters to Experiment...\nTesting parameters: {}".format(params))
        self.experiment_params(params)

        codisp_results, results = self.trainer.predict_anomalies()

        self.model_data['rrcf'] = codisp_results

        metrics = self.trainer.evaluate_rrcf(results)
    
        return metrics, results
    
    def ocsvm_pipeline(self):
        print("Loading One-Class SVM...")
        self.trainer = OneClassSVM(model_config = self.model_config, model_df = self.modelling_data)

        params = self.trainer.make_ocsvm()

        print("Parsing parameters to Experiment...\nTesting parameters: {}".format(params))
        self.experiment_params(params)

        results = self.trainer.predict_anomalies()

        self.model_data['ocsvm'] = results

        metrics = self.trainer.evaluate_ocsvm(results)
    
        return metrics, results
    
    def copad_pipeline(self):
        print("Loading Copula Based Outlier Detector...")
        self.trainer = CopulaPOD(model_config = self.model_config, model_df = self.modelling_data)

        params = self.trainer.make_copad()

        print("Parsing parameters to Experiment...\nTesting parameters: {}".format(params))
        self.experiment_params(params)

        results = self.trainer.predict_anomalies()

        self.model_data['copad'] = results

        metrics = self.trainer.evaluate_copad(results)
    
        return metrics, results
    
    def hbos_pipeline(self):
        print("Loading Histogram-based Outlier Detection...")
        self.trainer = HistoBOS(model_config = self.model_config, model_df = self.modelling_data)

        params = self.trainer.make_hbos()

        print("Parsing parameters to Experiment...\nTesting parameters: {}".format(params))
        self.experiment_params(params)

        results = self.trainer.predict_anomalies()

        self.model_data['hbos'] = results

        metrics = self.trainer.evaluate_hbos(results)
    
        return metrics, results