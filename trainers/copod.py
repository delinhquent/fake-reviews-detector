import math

import numpy as np

from pyod.models.copod import COPOD


class CopulaPOD:
    def __init__(self, model_config, model_df):
        self.model_config = model_config
        self.model_df = model_df

    def make_copad(self):
        self.model =  COPOD()
        return self.model.get_params()
    
    def predict_anomalies(self):
        self.model.fit(self.model_df)
        return self.model.labels_

    def evaluate_copad(self, results):
        print("Evaluating LMDD...")

        total_reviews = len(list(results))
        total_fake_reviews = list(results).count(-1)
        total_non_fake_reviews = total_reviews - total_fake_reviews

        metrics = {"total_fake_reviews": total_fake_reviews,"percentage_fake_reviews": (total_fake_reviews/total_reviews),"total_non_fake_reviews":total_non_fake_reviews,"percentage_non_fake_reviews":total_non_fake_reviews/total_reviews}
        
        return metrics