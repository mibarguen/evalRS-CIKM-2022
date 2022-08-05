"""

    This script contains the list of tests that has been prepared for the challenge. Tests are standard
    IR metrics, interesting datasets slices based on data analysis and literature, and novel behavioral tests.

    While you should not modify this class, your submission should contain a class extending "EvalRSRecList"
    with custom tests that you found useful to debug the behavior of your model, or check for 
    regression errors in test cases you care about (check the README and notebooks for more details)

    You're free to experiment with the dataset, and share your insightful work as operationalized in RecTests with
    the community!

"""
import numpy as np
import pandas as pd
from reclist.abstractions import RecList, RecDataset, rec_test
from evaluation.utils import TOP_K_CHALLENGE

class EvalRSRecList(RecList):


    def mrr_at_k_slice(self,
                        y_preds: pd.DataFrame,
                        y_test: pd.DataFrame,
                        slice_info: pd.DataFrame,
                        slice_key: str):

        from reclist.metrics.standard_metrics import rr_at_k
        # get rr (reciprocal rank) for each prediction made
        rr = rr_at_k(y_preds, y_test, k=TOP_K_CHALLENGE)
        # convert to DataFrame
        rr = pd.DataFrame(rr, columns=['rr'], index=y_test.index)
        # grab slice info
        rr[slice_key] = slice_info[slice_key].values
        # group-by slice and get per-slice mrr
        return rr.groupby(slice_key)['rr'].agg('mean').to_json()

    def false_positives_at_k_slice(self,
                                   y_preds: pd.DataFrame,
                                   y_test: pd.DataFrame,
                                   slice_info: pd.DataFrame,
                                   slice_key: str):
        from reclist.metrics.standard_metrics import false_positives_at_k
        # get false positives
        fp = false_positives_at_k(y_preds, y_test, k=TOP_K_CHALLENGE).min(axis=2)
        # convert to dataframe
        fp = pd.DataFrame(fp, columns=['fp'], index=y_test.index)
        # grab slice info
        fp[slice_key] = slice_info[slice_key].values
        # group-by slice and get per-slice mrr
        return fp.groupby(slice_key)['fp'].agg('mean')

    def false_positive_equality_difference(self,
                                           y_preds: pd.DataFrame,
                                           y_test: pd.DataFrame,
                                           slice_info: pd.DataFrame,
                                           slice_key: str):
        from reclist.metrics.standard_metrics import false_positives_at_k

        fpr_per_slice = self.false_positives_at_k_slice(y_preds, y_test, slice_info, slice_key)
        fpr = false_positives_at_k(y_preds, y_test, k=TOP_K_CHALLENGE).min(axis=2).mean()
        fped = (fpr_per_slice-fpr).abs().mean()
        res = fpr_per_slice.to_dict()
        return {'fped': fped, 'fpr': fpr, **res}


    def cosine_sim(self, u: np.array, v: np.array) -> np.array:
        return  np.sum(u * v, axis=1) / (np.linalg.norm(u, axis=1) * np.linalg.norm(v, axis=1))

    @rec_test('stats')
    def stats(self):
        tracks_per_users = (self._y_test.values!=-1).sum(axis=1)
        return {
            'num_users': len(self._x_test['user_id'].unique()),
            'max_items': int(tracks_per_users.max()),
            'min_items': int(tracks_per_users.min())
        }

    @rec_test('HIT_RATE')
    def hit_rate_at_20(self):
        from reclist.metrics.standard_metrics import hit_rate_at_k
        hr = hit_rate_at_k(self._y_preds, self._y_test, k=TOP_K_CHALLENGE)
        return hr

    @rec_test('MRR')
    def mrr_at_20(self):
        from reclist.metrics.standard_metrics import mrr_at_k
        return mrr_at_k(self._y_preds, self._y_test, k=TOP_K_CHALLENGE)

    @rec_test('FPED_COUNTRY')
    def fped_country(self):
        country_list = ["US", "RU", "DE", "UK", "PL", "BR", "FI", "NL", "ES", "SE", "UA", "CA", "FR", "NaN"]
        user_countries = self.product_data['users'].loc[self._y_test.index, ['country']].fillna('NaN')
        valid_country_mask = user_countries['country'].isin(country_list)
        y_pred_valid = self._y_preds[valid_country_mask]
        y_test_valid = self._y_test[valid_country_mask]
        user_countries = user_countries[valid_country_mask]

        return self.false_positive_equality_difference(y_pred_valid, y_test_valid, user_countries, 'country')

    @rec_test('FPED_USER_ACTIVITY')
    def fped_user_activity(self):
        bins = np.array([10,100,1000,10000])
        user_activity = self._x_train[self._x_train['user_id'].isin(self._y_test.index)]
        user_activity = user_activity.groupby('user_id',as_index=True, sort=False)[['user_track_count']].sum()
        user_activity = user_activity.loc[self._y_test.index]

        user_activity['bin_index'] = np.digitize(user_activity.values.reshape(-1), bins)
        user_activity['bins'] = bins[user_activity['bin_index'].values-1]

        return self.false_positive_equality_difference(self._y_preds,self._y_test, user_activity, 'bins')

    @rec_test('FPED_ARTIST_POPULARITY')
    def fped_artist_popularity(self):
        bins = np.array([10, 100, 1000, 10000, 100000])
        artist_id = self.product_data['items'].loc[self._y_test['track_id'], 'artist_id']
        artist_activity = self._x_train[self._x_train['artist_id'].isin(artist_id)]
        artist_activity = artist_activity.groupby('artist_id', as_index=True, sort=False)[['user_track_count']].sum()
        artist_activity = artist_activity.loc[artist_id]

        artist_activity['bin_index'] = np.digitize(artist_activity.values.reshape(-1), bins)
        artist_activity['bins'] = bins[artist_activity['bin_index'].values - 1]

        return self.false_positive_equality_difference(self._y_preds, self._y_test, artist_activity, 'bins')

    @rec_test('FPED_GENDER')
    def fped_gender(self):
        user_gender = self.product_data['users'].loc[self._y_test.index, ['gender']]
        return self.false_positive_equality_difference(self._y_preds, self._y_test, user_gender, 'gender')

    @rec_test('BEING_LESS_WRONG')
    def being_less_wrong(self):
        from reclist.metrics.standard_metrics import hits_at_k

        hits = hits_at_k(self._y_preds, self._y_test, k=TOP_K_CHALLENGE).max(axis=2)
        misses = (hits == False)
        miss_gt_vectors = self._dense_repr[self._y_test.loc[misses, 'track_id'].values.reshape(-1)]
        # we calculate the score w.r.t to the first prediction
        miss_pred_vectors = self._dense_repr[self._y_preds.loc[misses, '0'].values.reshape(-1)]

        return float(self.cosine_sim(miss_gt_vectors, miss_pred_vectors).mean())
    
        # return self.cosine_distance(miss_gt_vectors, miss_pred_vectors)


class EvalRSDataset(RecDataset):
    def load(self, **kwargs):
        self._x_train = kwargs.get('x_train')
        self._x_test = kwargs.get('x_test')
        self._y_test = kwargs.get('y_test')
        self._catalog = {
            'users': kwargs.get('users'),
            'items': kwargs.get('items')
        }
