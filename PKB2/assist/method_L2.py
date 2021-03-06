"""
L2 penalty method
author: li zeng
"""

import numpy as np
from assist.util import get_K, undefined
import multiprocessing as mp
import scipy

# function to parallelized
"""
solve L2 penalized regression for pathway m
sharedK: shared kernel matrix
model: model class object
m: pathway index
h: first order derivative
q: second order derivative
sele_loc: index of subset of data to use
"""
def paral_fun_L2(sharedK,Z,model,m,nrow,h,q,Lambda,sele_loc):
    # get K
    Km = get_K(sharedK,m,nrow,sele_loc)
    if model.problem in ('classification','survival'):
        # working Lambda
        new_Lambda= len(sele_loc)*Lambda
        # convert eta, Km
        eta = model.calcu_eta(h,q)
        w = model.calcu_w(q)
        w_half = model.calcu_w_half(q)
        mid_mat = np.eye(len(sele_loc)) - Z.dot( np.linalg.solve(Z.T.dot(w).dot(Z), Z.T.dot(w)) )
        eta_tilde = w_half.dot(mid_mat).dot(eta)
        Km_tilde = w_half.dot(mid_mat).dot(Km)
    elif model.problem == 'regression':
        # working Lambda
        new_Lambda= len(sele_loc)*Lambda
        e = np.linalg.solve(Z.T.dot(Z), np.eye(Z.shape[1])).dot(Z.T)
        eta = model.calcu_eta(Z)
        mid_mat = np.eye(len(sele_loc)) - Z.dot(e)
        #mid_mat = np.eye(len(sele_loc)) - Z.dot( np.linalg.solve(Z.T.dot(Z), Z.T) )
        eta_tilde = mid_mat.dot(eta)
        Km_tilde = mid_mat.dot(Km)
    # L2 solution
    #===========================================================================
    # print("L2 solution")
    # print(Km_tilde)
    # print(Km_tilde.T.dot(Km_tilde))
    #===========================================================================
    tmp_mat1 = Km_tilde.T.dot(Km_tilde)
    tmp_mat = Km_tilde.T.dot(Km_tilde) + np.eye(len(sele_loc))*new_Lambda
    #sol = scipy.linalg.inv(tmp_mat)
    #sol = np.linalg.inv(tmp_mat,np.eye(tmp_mat.shape[0]))
    #print("solved")
    #beta = - scipy.linalg.inv(tmp_mat,np.eye(tmp_mat.shape[0])).dot(Km_tilde.T.dot(eta_tilde))
    #===========================================================================
    # try:
    #     inverse = np.linalg.inv(tmp_mat)
    #     print("Yeah!")
    # except np.linalg.LinAlgError:
    #     pass
    #===========================================================================
    #beta = - scipy.linalg.inv(tmp_mat).dot(Km_tilde.T.dot(eta_tilde))

    beta = - np.linalg.solve( Km_tilde.T.dot(Km_tilde) + np.eye(len(sele_loc))*new_Lambda, Km_tilde.T.dot(eta_tilde))

    #get gamma
    if model.problem in ('classification','survival'):
        gamma = - np.linalg.solve(Z.T.dot(w).dot(Z), Z.T.dot(w)).dot(eta + Km.dot(beta))
    elif model.problem == 'regression':
        #gamma = - np.linalg.solve(Z.T.dot(Z), Z.T).dot(eta + Km.dot(beta))
        gamma = - e.dot(eta + Km.dot(beta))
    val = np.sum((eta_tilde+Km_tilde.dot(beta))**2) + new_Lambda*np.sum(beta**2)
    return [val,[m,beta,gamma]]

"""
find a feasible lambda for L2 problem
K_train: training kernel, shape (Ntrain, Ntrain, Ngroup)
Z: training clinical data, shape (Ntrain, Npred_clin)
model: model class object
Kdims: (Ntrain, Ngroup)
"""
def find_Lambda_L2(K_train,Z,model,Kdims,C=2):
    l_list = [] # list of lambdas from each group
    if model.problem in ('classification','survival'):
        h = model.calcu_h()
        q = model.calcu_q()
        eta = model.calcu_eta(h,q)
        w = model.calcu_w(q)
        w_half = model.calcu_w_half(q)
        mid_mat = np.eye(Kdims[0]) - Z.dot( np.linalg.solve(Z.T.dot(w).dot(Z), Z.T.dot(w)) )
        eta_tilde = w_half.dot(mid_mat).dot(eta)
        # max(|Km*eta|)/N for each Km
        for m in range(Kdims[1]):
            Km = K_train[:,:,m]
            Km_tilde = w_half.dot(mid_mat).dot(Km)
            d = np.linalg.svd(Km_tilde)[1][0]
            l = d*(np.sqrt(np.sum(eta_tilde**2)) - C)/(C*Kdims[0])
            l = l if l>0 else 0.01
            l_list.append(l)
    elif model.problem == 'regression':
        eta = model.calcu_eta(Z)
        mid_mat = np.eye(Z.shape[0]) - Z.dot( np.linalg.solve(Z.T.dot(Z), Z.T) )
        eta_tilde = mid_mat.dot(eta)
        # max(|Km*eta|)/N for each Km
        for m in range(Kdims[1]):
            Km = K_train[:,:,m]
            Km_tilde = mid_mat.dot(Km)
            d = np.linalg.svd(Km_tilde)[1][0]
            l = d*(np.sqrt(np.sum(eta_tilde**2)) - C)/(C*Kdims[0])
            l = l if l>0 else 0.01
            l_list.append(l)
    return np.percentile(l_list,20)


"""
perform one iteration of L2-boosting
sharedK: kernel matrix
model: model class object
Kdims: (Ntrain, Ngroup)
sele_loc: subset index
group_subset: bool, whether randomly choose a subset of pathways
"""
def oneiter_L2(sharedK,Z,model,Kdims,Lambda,ncpu = 1,\
               parallel=False,sele_loc = None,group_subset = False):
    # whether stochastic gradient boosting
    if sele_loc is None:
        sele_loc = np.array(range(model.Ntrain))

    # calculate derivatives h,q
    if model.problem in ('classification','survival'):
        # calculate derivatives h,q
        h = model.calcu_h()
        q = model.calcu_q()
    elif model.problem == 'regression':
        h = None
        q = None

    # identify best fit K_m
    if not parallel: ncpu =1
        # random subset of groups
    mlist = range(Kdims[1])
    if group_subset:
        mlist= np.random.choice(mlist,min([Kdims[1]//3,100]),replace=False)

    pool = mp.Pool(processes =ncpu,maxtasksperchild=300)
    results = [pool.apply_async(paral_fun_L2,args=(sharedK,Z,model,m,Kdims[0],h,q,Lambda,sele_loc)) for m in mlist]
    out = [res.get() for res in results]
    pool.close()
    return out[np.argmin([x[0] for x in out])][1]
