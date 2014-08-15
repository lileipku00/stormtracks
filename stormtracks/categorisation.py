from collections import OrderedDict
from copy import copy

import numpy as np
import pylab as plt
try:
    from sklearn.linear_model import SGDClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.lda import LDA
    from sklearn.qda import QDA
    from sklearn import tree
except ImportError:
    print 'IMPORT mlpy/scikit failed: must be on UCL computer'

from utils.utils import geo_dist


class CatData(object):
    def __init__(self, data, are_hurr_actual, dates, hurr_counts, missed_count):
        self.data = data
        self.are_hurr_actual = are_hurr_actual
        self.dates = dates
        self.hurr_counts = hurr_counts
        self.missed_count = missed_count

# TODO: utils.
class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'


def calc_t_anom(cyclone, date):
    return cyclone.t850s[date] - cyclone.t995s[date]


def get_vort(cyclone, date):
    return cyclone.vortmax_track.vortmax_by_date[date].vort
    # return cyclone.get_vort(date)


def calc_ws_dist(cyclone, date):
    return geo_dist(cyclone.max_windspeed_positions[date], cyclone.get_vmax_pos(date))


def calc_ws_dir(cyclone, date):
    p1, p2 = (cyclone.max_windspeed_positions[date], cyclone.get_vmax_pos(date))
    dy = p2[1] - p1[1]
    dx = p2[0] - p1[0]
    return np.arctan2(dy, dx)


def calc_lat(cyclone, date):
    pos = cyclone.get_vmax_pos(date)
    return pos[1]


def calc_lon(cyclone, date):
    pos = cyclone.get_vmax_pos(date)
    return pos[0]


def get_cyclone_attr(cyclone, attr, date):
    if attr['name'] != 'calc':
        return getattr(cyclone, attr['name'])[date]
    else:
        val = attr['calc'](cyclone, date)
        return val


SCATTER_ATTRS = OrderedDict([
    # Normally x.
    ('vort', {'name': 'calc', 'calc': get_vort, 'index': 0}),
    ('pmin', {'name': 'pmins', 'index': 1}),
    ('pambdiff', {'name': 'p_ambient_diffs', 'index': 2}),
    ('mindist', {'name': 'min_dists', 'index': 3}),
    ('t995', {'name': 't995s', 'index': 4}),
    ('t850', {'name': 't850s', 'index': 5}),
    ('tanom', {'name': 'calc', 'calc': calc_t_anom, 'index': 6}),
    ('maxwindspeed', {'name': 'max_windspeeds', 'index': 7}),
    ('maxwindspeeddist', {'name': 'calc', 'calc': calc_ws_dist, 'index': 8}),
    ('maxwindspeeddir', {'name': 'calc', 'calc': calc_ws_dir, 'index': 9}),
    ('cape', {'name': 'capes', 'index': 10}),
    ('pwat', {'name': 'pwats', 'index': 11}),
    ('rh995', {'name': 'rh995s', 'index': 12}),
    ('lon', {'name': 'calc', 'calc': calc_lon, 'index': 13}),
    ('lat', {'name': 'calc', 'calc': calc_lat, 'index': 14}),
])


class CategoriserComparison(object):
    def __init__(self, cal_cd, val_cd):
        self.cal_cd = cal_cd
        self.val_cd = val_cd
        self.cats = []

    def add_cat(self, cat):
        self.cats.append(cat)

    def train(self):
        for cat in self.cats:
            if cat.is_trainable:
                cat.train(self.cal_cd)

    def compare(self):
        for cat in self.cats:
            cat.try_cat(self.cal_cd)
            self.output_stats(cat)

    def output_stats(self, cat):
        print(cat.res)


class Categoriser(object):
    def __init__(self):
        self.missed_count = 0
        self.settings = OrderedDict()
        self.best_settings = None
        self.is_trained = False

        self.res = {}

    def train(self, cat_data, indices=None, **kwargs):
        self.settings = copy(kwargs)
        self.is_trained = True

        if not indices:
            max_index = SCATTER_ATTRS['lon']['index']
            self.settings['indices'] = range(max_index)
        else:
            self.settings['indices'] = indices

    def try_cat(self, cat_data, plot=None, var1='vort', var2='pmin', fig=None):
        self.missed_count = cat_data.missed_count
        self.cat_data = cat_data

        self.categorise(cat_data)
        self.compare(cat_data.are_hurr_actual, self.are_hurr_pred)

        self.calc_stats()

        print(self.res)
        print(self.settings)

        if plot in ['remaining', 'all']:
            self.plot_remaining_actual(var1, var2, fig)

        if plot in ['confusion', 'all']:
            self.plot_confusion(var1, var2, fig)

        plt.figure(0)
        plt.xlim((0, 1))
        plt.ylim((0, 1))
        plt.xlabel('sensitivity')
        plt.ylabel('ppv')
        plt.plot(self.sensitivity, self.ppv, 'b+')
    
    def categorise(self, cat_data):
        if not self.is_trained:
            raise Exception('Not yet trained')

    def plot_remaining_actual(self, var1, var2, fig=None, hurr_on_top=False):
        if not fig:
            fig = self.fig
        print('Figure {0}'.format(fig))
        plt.figure(fig)

        plt.clf()
        cd = self.cat_data.data[self.are_hurr_pred]
        h = self.cat_data.are_hurr_actual[self.are_hurr_pred]

        i1 = SCATTER_ATTRS[var1]['index']
        i2 = SCATTER_ATTRS[var2]['index']

        plt.xlabel(var1)
        plt.ylabel(var2)

        if hurr_on_top:
            plt.plot(cd[:, i1][~h], 
                     cd[:, i2][~h], 'bx', zorder=1)
            plt.plot(cd[:, i1][h], 
                     cd[:, i2][h], 'ko', zorder=2)
        else:
            plt.plot(cd[:, i1][~h], 
                     cd[:, i2][~h], 'bx', zorder=3)
            plt.plot(cd[:, i1][h], 
                     cd[:, i2][h], 'ko', zorder=2)
    
    def plot_confusion(self, var1, var2, fig = None, show_true_negs=False):
        if not fig:
            fig = self.fig
        print('Figure {0}'.format(fig + 1))
        plt.figure(fig + 1)
        plt.clf()

        plt.xlabel(var1)
        plt.ylabel(var2)

        i1 = SCATTER_ATTRS[var1]['index']
        i2 = SCATTER_ATTRS[var2]['index']

        cd = self.cat_data.data

        tp = self.are_hurr_pred & self.cat_data.are_hurr_actual
        tn = ~self.are_hurr_pred & ~self.cat_data.are_hurr_actual
        fp = self.are_hurr_pred & ~self.cat_data.are_hurr_actual
        fn = ~self.are_hurr_pred & self.cat_data.are_hurr_actual

        hs = ((tp, 'go', 1), 
              (fp, 'ro', 3),
              (fn, 'rx', 4),
              (tn, 'gx', 2))

        if not show_true_negs:
            hs = hs[:-1]

        for h, fmt, order in hs:
            # plt.subplot(2, 2, order)
            plt.plot(cd[:, i1][h], cd[:, i2][h], fmt, zorder=order)
    
    def compare(self, are_hurr_actual, are_hurr_pred):
        # Missed hurrs are counted as FN.
        self.res['fn'] = self.missed_count + (are_hurr_actual & ~are_hurr_pred).sum()
        self.res['fp'] = (~are_hurr_actual & are_hurr_pred).sum()
        self.res['tp'] = (are_hurr_actual & are_hurr_pred).sum()
        self.res['tn'] = (~are_hurr_actual & ~are_hurr_pred).sum()
        return self.res

    def calc_stats(self, show=True):
        res = self.res
        self.sensitivity = 1. * res['tp'] / (res['tp'] + res['fn'])
        self.ppv = 1. * res['tp'] / (res['tp'] + res['fp'])

        if show:
            print('sens: {0}, ppv: {1}'.format(self.sensitivity, self.ppv))


class CategoriserChain(Categoriser):
    '''Allows categorisers to be chained together.'''
    def __init__(self, cats):
        super(CategoriserChain, self).__init__()
        self.fig = 100
        self.cats = cats

    def train(self, cat_data, indices=None, **kwargs):
        '''Keyword args can be passed to e.g. the second categoriser by using:
        two={'loss': 'log'}
        '''
        super(CategoriserChain, self).train(cat_data, indices, **kwargs)
        curr_cat_data = CatData(cat_data.data,
                                cat_data.are_hurr_actual,
                                cat_data.dates,
                                cat_data.hurr_counts,
                                cat_data.missed_count)

        args = ['one', 'two', 'three']
        for arg, categoriser in zip(args, self.cats):
            categoriser.train(curr_cat_data, **kwargs[arg]).categorise(curr_cat_data)

            data_mask = categoriser.are_hurr_pred
            curr_cat_data = CatData(curr_cat_data.data[data_mask],
                                    curr_cat_data.are_hurr_actual[data_mask],
                                    curr_cat_data.dates[data_mask],
                                    curr_cat_data.hurr_counts,
                                    curr_cat_data.missed_count)
        return self

    def categorise(self, cat_data):
        super(CategoriserChain, self).categorise(cat_data)

        curr_cat_data = CatData(cat_data.data,
                                cat_data.are_hurr_actual,
                                cat_data.dates,
                                cat_data.hurr_counts,
                                cat_data.missed_count)
        are_hurr_pred = np.ones(len(cat_data.data)).astype(bool)
        removed_cat_data = None
        for categoriser in self.cats:
            categoriser.categorise(curr_cat_data)

            # Mask data based on what curr categoriser detected as positives.
            data_mask = categoriser.are_hurr_pred
            are_hurr_pred[are_hurr_pred] = data_mask
            curr_cat_data = CatData(curr_cat_data.data[data_mask],
                                    curr_cat_data.are_hurr_actual[data_mask],
                                    curr_cat_data.dates[data_mask],
                                    curr_cat_data.hurr_counts,
                                    curr_cat_data.missed_count)

        self.are_hurr_pred = are_hurr_pred


class CutoffCategoriser(Categoriser):
    def __init__(self):
        super(CutoffCategoriser, self).__init__()
        self.fig = 10

    def train(self, cat_data, indices=None, **kwargs):
        super(CutoffCategoriser, self).train(cat_data, indices, **kwargs)
        if 'best' in self.settings and self.settings['best'] == True:
            self.best_so_far()
        return self

    def best_so_far(self):
        self.settings = OrderedDict([('vort_lo', 0.000104), 
                                     # ('pwat_lo', 53), # possibly?
                                     ('t995_lo', 297.2), 
                                     ('t850_lo', 286.7), 
                                     ('maxwindspeed_lo', 16.1), 
                                     ('pambdiff_lo', 563.4)])

    def categorise(self, cat_data):
        super(CutoffCategoriser, self).categorise(cat_data)
        self.are_hurr_pred = np.ones((len(cat_data.data),)).astype(bool)

        for cutoff in self.settings.keys():
            var, hilo = cutoff.split('_')
            index = SCATTER_ATTRS[var]['index']
            if hilo == 'lo':
                mask = cat_data.data[:, index] > self.settings[cutoff]
            elif hilo == 'hi':
                mask = cat_data.data[:, index] < self.settings[cutoff]

            self.are_hurr_pred &= mask

        return self.are_hurr_pred


class LDACategoriser(Categoriser):
    '''Linear Discriminant analysis categoriser'''
    def __init__(self):
        super(LDACategoriser, self).__init__()
        self.fig = 20
        self.is_trainable = True
        self.is_trained = False

    def train(self, cat_data, indices=None, **kwargs):
        super(LDACategoriser, self).train(cat_data, indices, **kwargs)
        indices = self.settings['indices']

        self.lda = LDA(**kwargs)

        self.lda.fit(cat_data.data[:, indices], cat_data.are_hurr_actual)
        return self

    def categorise(self, cat_data):
        super(LDACategoriser, self).categorise(cat_data)
        indices = self.settings['indices']

        self.are_hurr_pred = self.lda.predict(cat_data.data[: , indices])
        return self.are_hurr_pred


class QDACategoriser(Categoriser):
    '''Quadratic Discriminant analysis categoriser'''
    def __init__(self):
        super(QDACategoriser, self).__init__()
        self.fig = 20
        self.is_trainable = True
        self.is_trained = False

    def train(self, cat_data, indices=None, **kwargs):
        super(QDACategoriser, self).train(cat_data, indices, **kwargs)
        indices = self.settings['indices']

        self.qda = QDA(**kwargs)

        self.qda.fit(cat_data.data[:, indices], cat_data.are_hurr_actual)
        return self

    def categorise(self, cat_data):
        super(QDACategoriser, self).categorise(cat_data)
        indices = self.settings['indices']

        self.are_hurr_pred = self.qda.predict(cat_data.data[: , indices])
        return self.are_hurr_pred


class DTACategoriser(Categoriser):
    '''Decision tree categoriser'''
    def __init__(self):
        super(DTACategoriser, self).__init__()
        self.fig = 50
        self.is_trainable = True
        self.is_trained = False

    def train(self, cat_data, indices=None, **kwargs):
        super(DTACategoriser, self).train(cat_data, indices, **kwargs)
        indices = self.settings['indices']

        self.dtc = tree.DecisionTreeClassifier(**kwargs)

        self.dtc.fit(cat_data.data[:, indices], cat_data.are_hurr_actual)
        return self

    def categorise(self, cat_data):
        super(DTACategoriser, self).categorise(cat_data)
        indices = self.settings['indices']

        self.are_hurr_pred = self.dtc.predict(cat_data.data[: , indices])
        return self.are_hurr_pred


class SGDCategoriser(Categoriser):
    '''Stochastic Gradient Descent categoriser'''
    def __init__(self):
        super(SGDCategoriser, self).__init__()
        self.fig = 30
        self.is_trainable = True
        self.is_trained = False

    def train(self, cat_data, indices=None, **kwargs):
        super(SGDCategoriser, self).train(cat_data, indices, **kwargs)
        indices = self.settings['indices']

        self.sgd_clf = SGDClassifier(**kwargs)

        self.scaler = StandardScaler()
        self.scaler.fit(cat_data.data[:, indices])
        self.cat_data_scaled = self.scaler.transform(cat_data.data[:, indices])

        self.sgd_clf.fit(self.cat_data_scaled, cat_data.are_hurr_actual)
        self.is_trained = True
        return self

    def categorise(self, cat_data):
        super(SGDCategoriser, self).categorise(cat_data)
        indices = self.settings['indices']

        self.cat_data_scaled = self.scaler.transform(cat_data.data[:, indices])
        self.are_hurr_pred = self.sgd_clf.predict(self.cat_data_scaled)

        return self.are_hurr_pred
