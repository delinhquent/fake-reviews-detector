"""
This script loads the required files, preprocesses it, and saves in a directory.
"""
from comet_ml import Experiment

from utils.config import process_config
from utils.utils import get_args
from src.data.make_dataset import generate
from src.features.build_features import build_features
from src.models.train_model import train_model

def automate_experiment_name(text_represent, feature_select, normalize, valid_models):
    feature_name = "All Features "
    if feature_select in ['y','Y']:
        feature_name = 'Important Features '
    
    text_represent_dict = {"tfidf":"with TFIDF","fasttext":"with fastText","glove":"with GloVe","word2vec":"with Word2Vec", "doc2vec":"with Doc2Vec"}

    if normalize in ['y','Y']:
        return valid_models[str(model.lower())] + " - " + feature_name + 'Normalized ' + text_represent_dict[text_represent]
    
    return valid_models[str(model.lower())] + " - " + feature_name + text_represent_dict[text_represent]

if __name__ == '__main__':
    try:
        args = get_args()
        config = process_config(args.config)
        mode = args.mode

        if mode == 'all':
            generate(config)
            build_features(config)
        if mode == 'dataset':
            generate(config)
        elif mode == 'build_features':
            build_features(config)
        elif mode == 'train_model':
            model = args.model
            
            valid_models = {'isolation_forest': "Isolation Forest", "lof": "LOF",
                            "ocsvm":"One-Class SVM", "copod":"Copula Based Outlier Detector", "hbos":"Histogram-based Outlier Detection",'pyod_isolation_forest': "PYOD Isolation Forest",
                            "pyod_lof": "PYOD LOF"}
            # valid_models = {"ocsvm":"One-Class SVM"}

            if model == None:
                print("Please parse the model's names using -model respectively...")
            elif model == None:
                print("Please parse the model's names using -model_n respectively...")
            elif str(model).lower() not in valid_models.keys():
                print("Unable to find such models...")
            else:
                text_represent = str(args.text_represent).lower()
                feature_select = str(args.feature_select).lower()
                normalize = str(args.normalize).lower()

                normalize_feature_select_valid_values = ['y','n','Y','N']
                # text_represent_valid_values = ['tfidf','glove','fasttext','word2vec','doc2vec']
                text_represent_valid_values = ['doc2vec']

                if text_represent in text_represent_valid_values and feature_select in normalize_feature_select_valid_values and normalize in normalize_feature_select_valid_values:
                    model_config = process_config(args.model_config)
                    comet_config = process_config(args.comet_config)

                    # Automatically create experiment name
                    experiment_name = automate_experiment_name(text_represent,feature_select,normalize, valid_models)

                    print("Logging experiment name: {name}".format(name=experiment_name))
                    experiment = Experiment(
                        api_key=comet_config.experiment.api_key,
                        project_name=comet_config.experiment.project_name,
                        workspace=comet_config.experiment.workspace
                    )
                    
                    experiment.set_name(experiment_name)

                    configs = [config, comet_config, model_config]
                    user_config = [text_represent, feature_select, normalize]
                    train_model(configs, experiment, model, user_config)
                else:
                    print("Please input y or n for -feature_select/-normalize & doc2vec for -text_represent...")    
        else:
            print("There is no such mode yet...")
            exit(0)
    except ValueError:
        print("Missing or invalid arguments")
        exit(0)





