"""
utility functions
author: li zeng
"""
import numpy as np
import scipy

"""-----------------
FUNCTIONS
--------------------"""


"""
line search function
sharedK: shared kernel matrix
model: a specific model class
pars: [m, beta, c] from each iteration
sele_loc: used in CV, only a subset of data used
"""
def line_search(sharedK,model,Kdims,pars,sele_loc=None):
    [m,beta,c] = pars
    if sele_loc is None:
        sele_loc = np.array(range(model.Ntrain))
    # get K
    nrow = Kdims[0]
    Km = get_K(sharedK,m,nrow,sele_loc)

    b = Km.dot(beta)+c
    # line search function
    def temp_fun(x):
        return model.loss_fun(model.ytrain, model.F_train+x*b)
    out = scipy.optimize.minimize_scalar(temp_fun)
    if not out.success:
        print("warning: minimization failure")
    return out.x

# sampling
def subsamp(y,col,fold=3):
    grouped = y.groupby(col)
    out = [list() for i in range(fold)]
    for i in grouped.groups.keys():
        ind = grouped.get_group(i)
        n = ind.shape[0]
        r = list(range(0,n+1,n//fold))
        r[-1] = n+1
        # permute index
        perm_index = np.random.permutation(ind.index)
        for j in range(fold):
            out[j] += list(perm_index[r[j]:r[j+1]])
    return out


"""
get kernel matrices from sharedK
return K[:,:,m][sele_loc,selec_l]
"""
def get_K(sharedK,m,nrow,sele_loc):
    width = nrow**2
    Km = sharedK[(m*width):((m+1)*width)].reshape((nrow,nrow))
    Km = Km[np.ix_(sele_loc,sele_loc)]
    return Km


"""
print title
"---- title ----"
"""
def print_section(s, width = 60):
    print()
    if not s:
        print('-'*width)
    else:
        ct_left = (width - len(s) -2)//2
        ct_right = width - len(s) - 2 - ct_left
        print('-'*ct_left + ' {} '.format(s) + '-'*ct_right)



"""-----------------
DERIVATIVES
--------------------"""

# first order
def calcu_h(F_train,ytrain,problem):
    if problem == "classification":
        denom  = np.exp(ytrain * F_train) + 1
        return (-ytrain)/denom
    elif problem == "survival":
        pass


# second order
def calcu_q(F_train,ytrain,problem):
    if problem == "classification":
        denom = (np.exp(ytrain * F_train) + 1)**2
        return np.exp(ytrain * F_train)/denom
    elif problem == "survival":
        pass
