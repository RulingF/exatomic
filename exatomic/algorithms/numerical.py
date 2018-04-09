# -*- coding: utf-8 -*-
# Copyright (c) 2015-2018, Exa Analytics Development Team
# Distributed under the terms of the Apache License 2.0
"""
Numerical methods and classes
###############################
Everything in this module is implemented in numba.
"""
import numpy as np
from numba import (jit, jitclass, deferred_type,
                   optional, int64, float64, boolean)
from exatomic.base import nbche

#################
# Miscellaneous #
#################

@jit(nopython=True, nogil=True, cache=nbche)
def _fac(n,v): return _fac(n-1, n*v) if n else v
@jit(nopython=True, nogil=True, cache=nbche)
def _fac2(n,v): return _fac2(n-2, n*v) if n > 0 else v

@jit(nopython=True, nogil=True, cache=nbche)
def fac(n): return _fac(n, 1) if n > -1 else 0
@jit(nopython=True, nogil=True, cache=nbche)
def fac2(n): return _fac2(n, 1) if n > 1 else 1 if n > -2 else 0
@jit(nopython=True, nogil=True, cache=nbche)
def dfac21(n): return fac2(2 * n - 1)
@jit(nopython=True, nogil=True, cache=nbche)
def choose(n, k): return fac(n) // (fac(k) * fac(n - k))
@jit(nopython=True, nogil=True, cache=nbche)
def sdist(ax, ay, az, bx, by, bz):
    return (ax - bx) ** 2 + (ay - by) ** 2 + (az - bz) ** 2

#@vectorize(['int64(int64)'])
def _vec_fac(n): return fac(n)
#@vectorize(['int64(int64)'])
def _vec_fac2(n): return fac2(n)
#@vectorize(['int64(int64)'])
def _vec_dfac21(n): return dfac21(n)


################################
# Matrix packing and reshaping #
################################


@jit(nopython=True, nogil=True, cache=nbche, parallel=False)
def _tri_indices(vals):
    nel = vals.shape[0]
    nbas = int64(np.round(np.roots(np.array([1, 1, -2 * vals.shape[0]]))[1]))
    chi0 = np.empty(nel, dtype=np.int64)
    chi1 = np.empty(nel, dtype=np.int64)
    cnt = 0
    for i in range(nbas):
        for j in range(i + 1):
            chi0[cnt] = i
            chi1[cnt] = j
            cnt += 1
    return chi0, chi1

@jit(nopython=True, nogil=True, cache=nbche, parallel=False)
def _triangle(vals):
    nbas = vals.shape[0]
    ndim = nbas * (nbas + 1) // 2
    tri = np.empty(ndim, dtype=np.float64)
    cnt = 0
    for i in range(nbas):
        for j in range(i + 1):
            tri[cnt] = vals[i, j]
            cnt += 1
    return tri

@jit(nopython=True, nogil=True, cache=nbche, parallel=False)
def _square(vals):
    nbas = int64(np.round(np.roots(np.array([1, 1, -2 * vals.shape[0]]))[1]))
    square = np.empty((nbas, nbas), dtype=np.float64)
    cnt = 0
    for i in range(nbas):
        for j in range(i + 1):
            square[i, j] = vals[cnt]
            square[j, i] = vals[cnt]
            cnt += 1
    return square

@jit(nopython=True, nogil=True, cache=nbche, parallel=False)
def _flat_square_to_triangle(flat):
    cnt, ndim = 0, np.int64(np.sqrt(flat.shape[0]))
    tri = np.empty(ndim * (ndim + 1) // 2)
    for i in range(ndim):
        for j in range(i + 1):
            tri[cnt] = flat[i * ndim + j]
            cnt += 1
    return tri


#####################################################################
# Numba vectorized operations for Orbital, MOMatrix, Density tables #
# These probably belong here but should be made more consistent     #
# with the functions above for matrix manipulation.                 #
#####################################################################


@jit(nopython=True, nogil=True, cache=nbche)
def _square_indices(n):
    m = n**2
    x = np.empty((m, ), dtype=np.int64)
    y = x.copy()
    k = 0
    # Order matters so don't us nb.prange
    for i in range(n):
        for j in range(n):
            x[k] = i
            y[k] = j
            k += 1
    return x, y


@jit(nopython=True, nogil=True, cache=nbche)
def density_from_momatrix(cmat, occvec):
    nbas = len(occvec)
    arlen = nbas * (nbas + 1) // 2
    dens = np.empty(arlen, dtype=np.float64)
    chi0 = np.empty(arlen, dtype=np.int64)
    chi1 = np.empty(arlen, dtype=np.int64)
    frame = np.zeros(arlen, dtype=np.int64)
    cnt = 0
    for i in range(nbas):
        for j in range(i + 1):
            dens[cnt] = (cmat[i,:] * cmat[j,:] * occvec).sum()
            chi0[cnt] = i
            chi1[cnt] = j
            cnt += 1
    return chi0, chi1, dens, frame


@jit(nopython=True, nogil=True, cache=nbche)
def density_as_square(denvec):
    nbas = int((-1 + np.sqrt(1 - 4 * -2 * len(denvec))) / 2)
    square = np.empty((nbas, nbas), dtype=np.float64)
    cnt = 0
    for i in range(nbas):
        for j in range(i + 1):
            square[i, j] = denvec[cnt]
            square[j, i] = denvec[cnt]
            cnt += 1
    return square


@jit(nopython=True, nogil=True, cache=nbche)
def momatrix_as_square(movec):
    nbas = np.int64(len(movec) ** (1/2))
    square = np.empty((nbas, nbas), dtype=np.float64)
    cnt = 0
    for i in range(nbas):
        for j in range(nbas):
            square[j, i] = movec[cnt]
            cnt += 1
    return square


#######################
# Basis set expansion #
#######################

@jit(nopython=True, nogil=True, cache=nbche)
def _enum_cartesian(L):
    # Gen1Int ordering
    # for z in range(L + 1):
    #     for y in range(L + 1 - z):
    #         yield (L - y - z, y, z)
    # Naive combinations with replacements
    # for i in range(L, -1, -1):
    #     for j in range(L, -1, -1):
    #         for k in range(L, -1, -1):
    #             if i + j + k == L:
    #                 yield (i, j, k)
    # Double loop CWR
    for x in range(L, -1, -1):
        for z in range(L + 1 - x):
            yield (x, L - x - z, z)

@jit(nopython=True, nogil=True, cache=nbche)
def _enum_spherical(L, increasing=True):
    if increasing:
        for m in range(-L, L + 1):
            yield L, m
    else:
        for m in range(L + 1):
            if not m:
                yield L, m
            else:
                for i in (m, -m):
                    yield L, i



#####################
# Basis set classes #
#####################

shell_type = deferred_type()

@jitclass([('L', int64), ('nprim', int64), ('ncont', int64),
           ('spherical', boolean), ('gaussian', boolean),
           ('alphas', float64[:]), ('_coef', float64[:]),
           ('rs', optional(int64[:])), ('ns', optional(int64[:]))])
class Shell(object):
    """The primary object used for all things basis set related.
    Due to limitations in numba, contraction coefficients are stored
    as a 1D-array and reshaped when calling contract methods.

    Args:
        coef (np.ndarray): 1D-array of contraction coefficients
        alphas (np.ndarray): 1D-array of primitive exponents
        nprim (int): number of primitives in the shell
        ncont (int): number of contracted functions in the shell
        L (int): angular momentum quantum number
        spherical (bool): whether angular momentum is expanded in linearly independent set
        gaussian (bool): whether exponential dependence is r or r2
        rs (np.ndarray): 1D-array of radial exponents (default None)
        ns (np.ndarray): additional normalization factors (default None)
    """

    def dims(self):
        """Mimics numpy.ndarray shape property but as a method."""
        return self.nprim, self.ncont

    def contract(self):
        """Reshapes contraction coefficients into (nprim, ncont) array."""
        x = 0
        rect = np.empty((int64(self.nprim), int64(self.ncont)))
        for i in range(self.nprim):
            for j in range(self.ncont):
                rect[i, j] = self._coef[x]
                x += 1
        return rect

    def _prim_sphr_norm(self):
        """Deprecated."""
        Ns = np.empty(len(self.alphas), dtype=np.float64)
        for i, a in enumerate(self.alphas):
            prefac = (2 / np.pi) ** (0.75)
            numer = 2 ** self.L * a ** ((self.L + 1.5) / 2)
            denom = dfac21(self.L) ** 0.5
            Ns[i] = prefac * numer / denom
        return Ns

    def norm_contract(self):
        """Determine the correct normalization procedure and contract."""
        if not self.gaussian:
            return self._sto_norm_contract()
        if self.spherical:
            return self._sphr_norm_contract()
        return self._cart_norm_contract()

    def enum_cartesian(self):
        """Iterate over cartesian powers in L."""
        return _enum_cartesian(self.L)

    def enum_spherical(self):
        """Iterate over ml degeneracy in L."""
        return _enum_spherical(self.L)

    def _cart_norm_contract(self):
        """Cartesian gaussian normalization."""
        # float is (2 * np.pi) ** -0.75
        return self._norm_cont_kernel(0.251979435538381)

    def _sphr_norm_contract(self):
        """Spherical gaussian normalization."""
        # float is (2 / np.pi) ** 0.25
        prefact = 0.893243841738002 / np.sqrt(dfac21(self.L))
        return self._norm_cont_kernel(prefact)

    def _norm_cont_kernel(self, pre):
        """Gaussian normalization."""
        coef = self.contract()
        ltot = self.L + 1.5
        lhaf = ltot / 2.
        prim, cont = coef.shape
        for c in range(cont):
            norm = 0.
            for pi in range(prim):
                for pj in range(prim):
                    ovl = (2. * (np.sqrt(self.alphas[pi] * self.alphas[pj])
                                     / (self.alphas[pi] + self.alphas[pj]))) ** ltot
                    norm += coef[pi, c] * coef[pj, c] * ovl
            norm = pre / np.sqrt(norm)
            for p in range(prim):
                coef[p, c] *= norm * (4.0 * self.alphas[p]) ** lhaf
        return coef

    def _sto_norm_contract(self):
        """Slater-type orbital normalization and reshaping."""
        # Assumes no contractions
        return np.array(self._sto_norm())*self.contract()

    def _sto_norm(self):
        """Slater-type orbital normalization."""
        return [((2 * a) ** n * ((2 * a) / fac(2 * n)) ** 0.5,)
                for a, n in zip(self.alphas, self.ns)]

    def __init__(self, coef, alphas, nprim, ncont, L,
                 spherical, gaussian, rs=None, ns=None):
        self.spherical = spherical
        self.gaussian = gaussian
        self.alphas = alphas
        self._coef = coef
        self.nprim = nprim
        self.ncont = ncont
        self.L = L
        self.rs = rs
        self.ns = ns

shell_type.define(Shell.class_type.instance_type)