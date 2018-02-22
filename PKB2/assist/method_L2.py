"""
L2 penalty method
author: li zeng
"""

import numpy as np
from assist.util import get_K, undefined
import multiprocessing as mp

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
        # calculte values
        """
        K2 = np.append(Km,np.ones([len(sele_loc),1]),axis=1)
        L_mat = np.diag(list(np.repeat(new_Lambda,len(sele_loc)))+[0])
        eta = -np.linalg.solve((K2.T).dot(np.diag(q/2)).dot(K2)+L_mat,(K2.T).dot(h/2))
        beta = eta[:-1]
        c = eta[-1]
        temp = K2.dot(eta)
        """
        # convert eta, Km
        eta = model.calcu_eta(h,q)
        w = model.calcu_w(q)
        w_half = model.calcu_w_half(q)
        mid_mat = np.eye(len(sele_loc)) - Z.dot( np.linalg.solve(Z.T.dot(w).dot(Z), Z.T.dot(w)) )
        eta_tilde = w_half.dot(mid_mat).dot(eta)
        Km_tilde = w_half.dot(mid_mat).dot(Km)
        # L2 solution
        beta = - np.linalg.solve( Km_tilde.T.dot(Km_tilde) + np.eye(len(sele_loc))*new_Lambda, Km_tilde.T.dot(eta_tilde))
        #get gamma
        gamma = - np.linalg.solve(Z.T.dot(w).dot(Z), Z.T.dot(w)).dot(eta + Km.dot(beta))
        val = np.sum((eta_tilde+Km_tilde.dot(beta))**2) + new_Lambda*np.sum(beta**2)
        return [val,[m,beta,gamma]]
    elif model.problem == 'regression':
        undefined()


"""
find a feasible lambda for L2 problem
K_train: training kernel, shape (Ntrain, Ntrain, Ngroup)
Z: training clinical data, shape (Ntrain, Npred_clin)
model: model class object
Kdims: (Ntrain, Ngroup)
"""
def find_Lambda_L2(K_train,Z,model,Kdims,C=2):
    if model.problem in ('classification','survival'):
        h = model.calcu_h()
        q = model.calcu_q()
        eta = model.calcu_eta(h,q)
        w = model.calcu_w(q)
        w_half = model.calcu_w_half(q)
        mid_mat = np.eye(Kdims[0]) - Z.dot( np.linalg.solve(Z.T.dot(w).dot(Z), Z.T.dot(w)) )
        eta_tilde = w_half.dot(mid_mat).dot(eta)

        l_list = [] # list of lambdas from each group
        # max(|Km*eta|)/N for each Km
        for m in range(Kdims[1]):
            Km = K_train[:,:,m]
            Km_tilde = w_half.dot(mid_mat).dot(Km)
            #Km_tilde = w_half.dot(Km - np.ones([Kdims[0],1]).dot((q/q.sum()).dot(Km).reshape([1,Kdims[0]])))
            d = np.linalg.svd(Km_tilde)[1][0]
            l = d*(np.sqrt(np.sum(eta_tilde**2)) - C)/(C*Kdims[0])
            if l > 0:
                l_list.append(l)
            else:
                l_list.append(0.01)
        return np.percentile(l_list,20)
    elif model.problem == 'regression':
        undefined()


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
    h = model.calcu_h()
    q = model.calcu_q()

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
