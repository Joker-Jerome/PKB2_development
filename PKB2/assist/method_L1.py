"""
L1 penalty method
author: li zeng
"""

import numpy as np
from assist.util import get_K
import multiprocessing as mp
import warnings
import sklearn.exceptions
warnings.filterwarnings("ignore", category=sklearn.exceptions.ConvergenceWarning)
from sklearn import linear_model

# function to be paralleled
"""
solve L1 penalized regression for pathway m
sharedK: shared kernel matrix
model: model class object
m: pathway index
h: first order derivative
q: second order derivative
sele_loc: index of subset of data to use
"""
def paral_fun_L1(sharedK,model,m,nrow,h,q,Lambda,sele_loc):
    # working Lambda
    new_Lambda= Lambda/2 # due to setting of sklearn.linear_model.Lasso
    # get K
    Km = get_K(sharedK,m,nrow,sele_loc)
    # transform eta, K for penalized regression
    if model.problem in ('classification','survival'):
        eta = h/q
        w_half = np.diag(np.sqrt(q/2))
        eta_tilde = w_half.dot(eta - eta*q/q.sum())
        Km_tilde = w_half.dot(Km - np.ones([len(sele_loc),1]).dot((q/q.sum()).dot(Km).reshape([1,len(sele_loc)])))
    elif model.problem == 'regression':
        pass

    # get beta
    lasso_fit = linear_model.Lasso(alpha = new_Lambda,fit_intercept = False,\
                selection='random',max_iter=20000,tol=10**-4)
    lasso_fit.fit(-Km_tilde,eta_tilde)
    beta = lasso_fit.coef_
    #get c
    c = -(q/q.sum()).dot(eta +  Km.dot(beta))
    # calculate val
    val = np.sum((eta_tilde+Km_tilde.dot(beta))**2)+ Lambda*len(sele_loc)*np.sum(np.abs(beta))
    return [val,[m,beta,c]]

# find a Lambda value
def find_Lambda_L1(K_train,model,Kdims):
    if model.problem in ('classification','survival'):
        h = model.calcu_h()
        q = model.calcu_q()
        eta = h/q
        w_half = np.diag(np.sqrt(q/2))
        eta_tilde = w_half.dot(eta - eta*q/q.sum())

        prod = []
        for m in range(Kdims[1]):
            Km = K_train[:,:,m]
            Km_tilde = w_half.dot(Km - np.ones([Kdims[0],1]).dot((q/q.sum()).dot(Km).reshape([1,Kdims[0]])))
            prod += list(Km_tilde.dot(eta_tilde))
        return 2*np.percentile(np.abs(prod),85)/Kdims[0]
    elif model.problem == 'regression':
        pass

"""
perform one iteration of L1-boosting
sharedK: kernel matrix
model: model class object
Kdims: (Ntrain, Ngroup)
sele_loc: subset index
group_subset: bool, whether randomly choose a subset of pathways
"""
def oneiter_L1(sharedK,model,Kdims,Lambda,\
               ncpu = 1,parallel=False,sele_loc = None,group_subset = False):
    # whether stochastic gradient boosting
    if sele_loc is None:
        sele_loc = np.array(range(model.Ntrain))

    # calculate derivatives h,q
    h = model.calcu_h()
    q = model.calcu_q()

    # identify best fit K_m
    if not parallel: ncpu =1
    # random subset of groups
    mlist = range(Kdims[1])
    if group_subset:
        mlist= np.random.choice(mlist,min([Kdims[1]//3,100]),replace=False)

    pool = mp.Pool(processes =ncpu,maxtasksperchild=300)
    results = [pool.apply_async(paral_fun_L1,args=(sharedK,model,m,Kdims[0],h,q,Lambda,sele_loc)) for m in mlist]
    out = [res.get() for res in results]
    pool.close()
    return out[np.argmin([x[0] for x in out])][1]
