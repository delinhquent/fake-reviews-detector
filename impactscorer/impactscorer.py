from datetime import datetime
import numpy as np
import pandas as pd
import re
import math

class ImpactScorer:
    def __init__(self, model_df,profiles_df):
        self.model_df = model_df
        self.profiles_df = profiles_df

    def get_total_fake_reviews(self):
        fake_reviews_df = self.model_df.groupby('acc_num').agg({'fake_reviews':np.sum}).reset_index()
        fake_reviews_df = fake_reviews_df.rename(columns={"fake_reviews":"total_fake_reviews"})
        return fake_reviews_df

    def create_profile_heuristics(self):
        self.profiles_df['proportion_fake_reviews'] = self.profiles_df['total_fake_reviews']/self.profiles_df['cleaned_total_reviews_posted']
        # Normalizing the data so that the data, approximately follows a Gaussian distribution 

        self.profiles_df['cleaned_not_brand_monogamist'] = 1- self.profiles_df['cleaned_brand_monogamist']
        self.profiles_df['cleaned_not_brand_loyalist'] = 1- self.profiles_df['cleaned_brand_loyalist']
        self.profiles_df['cleaned_not_brand_repeater'] = 1- self.profiles_df['cleaned_brand_repeater']
        suspicious_reviewer_columns = ['cleaned_not_brand_monogamist','cleaned_not_brand_loyalist','cleaned_not_brand_repeater','cleaned_never_verified_reviewer','cleaned_one_hit_wonder']
        self.profiles_df['suspicious_reviewer_score'] = (self.profiles_df['cleaned_not_brand_monogamist'] + self.profiles_df['cleaned_not_brand_loyalist'] + self.profiles_df['cleaned_not_brand_repeater'] + self.profiles_df['cleaned_never_verified_reviewer'] + self.profiles_df['cleaned_one_hit_wonder']) / len(suspicious_reviewer_columns)
        self.profiles_df.loc[self.profiles_df.proportion_fake_reviews > 1, 'proportion_fake_reviews'] = 1

    def create_time_scores(self):
        self.model_df['diff_days'] = datetime.now() - pd.to_datetime(self.model_df['cleaned_reviews_date_posted'], infer_datetime_format=True) 
        self.model_df['diff_days'] = self.model_df['diff_days'] // np.timedelta64(1,'D')  

        self.model_df['time_score'] = -1
        # within 1 mth
        self.model_df.loc[ (self.model_df.diff_days <= 30) & (self.model_df.time_score == -1), 'time_score'] = 1
        # 1 to 3 mth
        self.model_df.loc[ (self.model_df.diff_days <= 90) & (self.model_df.time_score == -1), 'time_score'] = 0.8
        # 3 to 6 mth
        self.model_df.loc[ (self.model_df.diff_days <= 180) & (self.model_df.time_score == -1), 'time_score'] = 0.6
        # 6 mth to 12 mth
        self.model_df.loc[ (self.model_df.diff_days <= 360) & (self.model_df.time_score == -1), 'time_score'] = 0.4
        # 12 to 24 mth
        self.model_df.loc[ (self.model_df.diff_days <= 720) & (self.model_df.time_score == -1), 'time_score'] = 0.2
        # more than 24 mth
        self.model_df.loc[ (self.model_df.diff_days > 720) & (self.model_df.time_score == -1), 'time_score'] = 0

    def re_evaluate_results(self):
        new_decision_function = []
        new_results = []

        for index, row in self.model_df.iterrows():
            if math.isnan(row['fake_reviews']):
                new_decision_function.append(0)
                new_results.append(0)
            elif row['fake_reviews'] == 1 and row['decision_function'] < 0.75:
                new_decision_function.append(row['decision_function'])
                new_results.append(0)
            else:
                new_decision_function.append(row['decision_function'])
                new_results.append(row['fake_reviews'])
        
        self.model_df['fake_reviews'] = new_results
        self.model_df['decision_function'] = new_decision_function

    def assess_impact(self):
        print("Retrieving total fake reviews for each user...")
        fake_reviews_df = self.get_total_fake_reviews()

        self.profiles_df = pd.merge(self.profiles_df,fake_reviews_df,left_on=['acc_num'], right_on = ['acc_num'], how = 'left')

        print("Creating heuristics for users...")
        self.create_profile_heuristics()

        self.model_df = pd.merge(self.model_df,self.profiles_df[['acc_num','suspicious_reviewer_score','proportion_fake_reviews']],left_on=['acc_num'], right_on = ['acc_num'], how = 'left')

        print("Evaluating recency of reviews...")
        self.create_time_scores()
        
        bin_labels = {0:'Not Severe', 1:'Severe',2:'Very Severe'}
        
        print("Calculating impact score...")
        decision_function = self.model_df['decision_function']
        max_decision_function = max(decision_function)
        min_decision_function = min(decision_function)
        self.model_df['decision_function'] = [(float(i) - min_decision_function)/(max_decision_function - min_decision_function) for i in decision_function]
        self.re_evaluate_results()


        helpful_votes = self.model_df['cleaned_reviews_voting']
        max_helpful_votes = max(helpful_votes)
        min_helpful_votes = min(helpful_votes)
        self.model_df['normalized_voting'] = [(float(i) - min_helpful_votes)/(max_helpful_votes - min_helpful_votes) for i in self.model_df['cleaned_reviews_voting']]

        self.model_df['impact_score'] = self.model_df.time_score + self.model_df.normalized_voting + ((self.model_df.fake_reviews) * (self.model_df.decision_function)) + self.model_df.proportion_fake_reviews + self.model_df.suspicious_reviewer_score
        self.model_df['impact_score'] /= 5
        self.model_df['impact_score'] = self.model_df['impact_score'].fillna(0)
        self.model_df['rank'] = self.model_df['impact_score'].rank(method='first')
        self.model_df['impact'] = pd.qcut(self.model_df['rank'].values, 3,).codes
        self.model_df = self.model_df.replace({"impact": bin_labels}) 

        self.model_df = self.model_df.sort_values(by='impact_score', ascending=False)

        self.model_df = self.model_df.drop(columns=['diff_days','time_score','rank','suspicious_reviewer_score','proportion_fake_reviews','normalized_voting'])
        return self.model_df, self.profiles_df
        

