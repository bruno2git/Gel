#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
This module contains experimental functionality for simulation of agarose gel
electrophoresis of DNA.

Note
----
This code is in a very early stage of development and documentation.
Read the source code to get an idea for how it works.
"""

from __future__ import division
from numbers import Number
from StringIO import StringIO
from random import randint

import numpy as np
import matplotlib.ticker as mtick
from scipy.interpolate import griddata
from scipy.optimize import leastsq, fsolve
from scipy import stats
from matplotlib import pyplot as plt, cm
from matplotlib.ticker import FixedLocator
from mpldatacursor import datacursor, HighlightingDataCursor  # version 0.5.0
from pint import UnitRegistry, DimensionalityError

import pydna



# Unit registry (move to package level)
ureg = UnitRegistry()
Q_ = ureg.Quantity
ureg.define('base_pair = [] = bp = basepair')
#ureg.define('base_pair = 3.4 angstrom = bp = basepair')
ureg.define('pixel = [] = px')
ureg.default_format = '~'


# Variable mapping ########################################################################
Vars = {'E': {'synonyms': ('field','electric field'), 'units': 'V/cm',
              'details': ("Electric field intensity as given by the applied "
                          "voltage divided by the distance between the "
                          "electrodes.")},
        'quantities': {'synonyms': (), 'units': 'ng',
                       'details': "Mass of DNA in a sample or a band."},
        'volume': {'synonyms': (), 'units': 'ul',
                   'details': ""}
        }

ladders = {
    '1kb_GeneRuler': {
        'sizes': Q_([10000, 8000, 6000, 5000, 4000, 3500, 3000, 2500, 2000,
                     1500, 1000, 750, 500, 250], 'bp'),
        'percent': Q_([0.06, 0.06, 0.14, 0.06, 0.06, 0.06, 0.14, 0.05, 0.05,
                       0.05, 0.12, 0.05, 0.05, 0.05])
        },
    '1kb+_GeneRuler': {
        'sizes': Q_([20000, 10000, 7000, 5000, 4000, 3000, 2000, 1500, 1000,
                     700, 500, 400, 300, 200, 75], 'bp'),
        'percent': Q_([0.04, 0.04, 0.04, 0.15, 0.04, 0.04, 0.04, 0.16, 0.05,
                       0.05, 0.15, 0.05, 0.05, 0.05, 0.05])
        },
    'Mix_GeneRuler': {
        'sizes': Q_([10000, 8000, 6000, 5000, 4000, 3500, 3000, 2500, 2000,
                     1500, 1200, 1000, 900, 800, 700, 600, 500, 400, 300, 200,
                     100], 'bp'),
        'percent': Q_([0.036, 0.036, 0.036, 0.036, 0.036, 0.036, 0.12, 0.032,
                       0.032, 0.032, 0.032, 0.12, 0.034, 0.034, 0.034, 0.034,
                       0.12, 0.04, 0.04, 0.04, 0.04])
        },
    'High_Range_GeneRuler': {
        'sizes': Q_([48502, 24508, 20555, 17000, 15258, 13825, 12119, 10171],
                    'bp'),
        'percent': Q_([0.16, 0.176, 0.16, 0.118, 0.118, 0.1, 0.094, 0.074])
        }
    }


# Data
hor_str = '''
+------+-----+-------+-------+-----------+-----------+----------+--------+-------+--------+
|  E   | %T  | L_max | L_min | mu_S*10^8 | mu_L*10^8 |   gamma  |  chi^2 | L'max | chi^2' |
|(V/cm)|     | (bp)  | (bp)  |(m^2/V.sec)|(m^2/V.sec)|   (kbp)  |        | (bp)  |        |
+------+-----+-------+-------+-----------+-----------+----------+--------+-------+--------+
| 0.71 | 0.5 | 35000 | 1000  |    2.61   |    0.42   |   29.70  | 0.9999 |       |        |
| 0.71 | 1.0 | 20000 |  300  |    2.54   |  1.64E-07 | 2.81E+07 | 0.9981 |  5000 | 0.9992 |
| 0.71 | 1.3 | 20000 |  200  |    2.49   |  2.60E-09 | 1.06E+09 | 0.9647 |  2600 | 0.9990 |
| 1.00 | 1.0 | 48502 |  400  |    2.37   |    0.23   |   29.99  | 0.9997 |       |        |
| 1.00 | 1.1 | 30000 |  200  |    2.21   |    0.05   |   74.08  | 0.9987 | 25000 | 0.9991 |
| 1.00 | 1.2 | 27500 |  200  |    2.14   |    0.01   |  144.40  | 0.9964 |  1300 | 0.9990 |
| 1.23 | 0.7 | 47500 | 1000  |    2.60   |    0.66   |   19.86  | 0.9997 |       |        |
| 1.23 | 0.8 | 35000 |  200  |    2.55   |    0.23   |   23.84  | 0.9988 | 27500 | 0.9990 |
| 1.23 | 0.9 | 25000 |  200  |    2.44   |    0.08   |   49.58  | 0.9971 |  3000 | 0.9992 |
| 1.31 | 0.5 | 35000 |  400  |    2.54   |    0.39   |   19.69  | 0.9999 |       |        |
| 1.31 | 1.0 | 25000 |  200  |    2.52   |    0.15   |   25.75  | 0.9986 | 17500 | 0.9992 |
| 1.31 | 1.3 | 48502 |  200  |    2.48   |    0.05   |   46.75  | 0.9967 | 14000 | 0.9991 |
| 1.51 | 1.0 | 35000 |  200  |    2.24   |    0.29   |   17.86  | 0.9997 |       |        |
| 1.51 | 1.1 | 32500 |  300  |    2.26   |    0.14   |   23.78  | 0.9980 | 20000 | 0.9989 |
| 1.51 | 1.2 | 48502 |  200  |    2.17   |    0.04   |   64.31  | 0.9974 | 15000 | 0.9991 |
| 1.80 | 0.5 | 47500 |  300  |    2.48   |    0.51   |   17.23  | 0.9998 |       |        |
| 1.80 | 1.3 | 30000 |  200  |    2.39   |    0.22   |   11.93  | 0.9980 | 13000 | 0.9991 |
| 2.00 | 1.0 | 48502 |  200  |    2.22   |    0.23   |   13.96  | 0.9982 | 20000 | 0.9992 |
| 2.00 | 1.1 | 48502 |  200  |    2.24   |    0.16   |   13.06  | 0.9971 | 10000 | 0.9991 |
| 2.00 | 1.2 | 17500 |  200  |    2.15   |    0.07   |   30.99  | 0.9979 | 10000 | 0.9990 |
| 2.22 | 0.5 | 35000 |  300  |    2.68   |    0.65   |   12.90  | 0.9995 |       |        |
| 2.22 | 1.0 | 35000 |  200  |    2.64   |    0.43   |    9.56  | 0.9994 |       |        |
| 2.22 | 1.3 | 32500 |  200  |    2.56   |    0.29   |    8.42  | 0.9981 | 17500 | 0.9991 |
| 2.47 | 0.7 | 32500 |  200  |    2.59   |    0.51   |    9.50  | 0.9997 |       |        |
| 2.47 | 0.8 | 35000 |  500  |    2.64   |    0.47   |    8.77  | 0.9998 |       |        |
| 2.47 | 0.9 | 48502 |  200  |    2.57   |    0.39   |    8.98  | 0.9992 |       |        |
| 2.51 | 0.7 | 35000 |  200  |    2.44   |    0.45   |   14.19  | 0.9999 |       |        |
| 2.51 | 0.8 | 35000 |  200  |    2.44   |    0.39   |   12.41  | 0.9996 |       |        |
| 2.51 | 0.9 | 48502 |  200  |    2.43   |    0.27   |   11.03  | 0.9986 | 15000 | 0.9991 |
| 2.78 | 0.5 | 10000 |  200  |    3.32   |    0.92   |    9.30  | 0.9999 |       |        |
| 2.78 | 0.6 | 10000 |  200  |    3.25   |    0.80   |    8.47  | 1.0000 |       |        |
| 2.78 | 0.7 | 10000 |  200  |    3.18   |    0.66   |    9.80  | 0.9998 |       |        |
| 2.78 | 0.8 | 10000 |  200  |    3.06   |    0.55   |    9.84  | 0.9997 |       |        |
| 2.78 | 0.9 | 10000 |  200  |    2.93   |    0.46   |    9.64  | 0.9997 |       |        |
| 2.78 | 1.0 | 10000 |  200  |    2.93   |    0.39   |   10.40  | 0.9997 |       |        |
| 2.78 | 1.1 | 10000 |  200  |    2.93   |    0.33   |   10.35  | 0.9993 |       |        |
| 2.78 | 1.2 | 10000 |  200  |    2.85   |    0.30   |   10.82  | 0.9995 |       |        |
| 2.78 | 1.3 | 10000 |  200  |    2.84   |    0.25   |   11.14  | 0.9996 |       |        |
| 2.78 | 1.4 | 10000 |  200  |    2.79   |    0.22   |   11.52  | 0.9994 |       |        |
| 2.78 | 1.5 | 10000 |  200  |    2.70   |    0.19   |   11.63  | 0.9993 |       |        |
| 3.10 | 1.0 | 32500 |  200  |    2.65   |    0.58   |    8.61  | 0.9999 |       |        |
| 3.10 | 1.1 | 30000 |  200  |    2.62   |    0.55   |    7.99  | 0.9998 |       |        |
| 3.10 | 1.2 | 27500 |  200  |    2.56   |    0.33   |    6.06  | 0.9980 |  5000 | 0.9994 |
| 3.51 | 0.5 | 35000 |  900  |    2.58   |    0.75   |   13.34  | 0.9993 |       |        |
| 3.51 | 1.0 | 48502 |  200  |    2.58   |    0.52   |    6.82  | 0.9997 |       |        |
| 3.51 | 1.3 | 25000 |  200  |    2.51   |    0.38   |    6.05  | 0.9989 |  8000 | 0.9990 |
| 5.00 | 0.5 | 22500 | 1000  |    2.53   |    0.75   |   18.15  | 0.9996 |       |        |
| 5.00 | 1.0 | 20000 |  400  |    2.55   |    0.67   |    5.78  | 0.9995 |       |        |
| 5.00 | 1.3 | 17500 |  200  |    2.51   |    0.50   |    4.22  | 0.9995 |       |        |
+------+-----+-------+-------+-----------+-----------+----------+--------+-------+--------+
'''

ver_str = '''
+------+-----+--------+-------+-----------+-----------+----------+--------+-------+--------+
|  E   | %T  | L_max  | L_min | mu_S*10^8 | mu_L*10^8 |   gamma  |  chi^2 | L'max | chi^2' |
|(V/cm)|     |  (bp)  | (bp)  |(m^2/V.sec)|(m^2/V.sec)|   (kbp)  |        | (bp)  |        |
+------+-----+--------+-------+-----------+-----------+----------+--------+-------+--------+
| 0.62 | 0.4 |  48502 | 1000  |    2.67   |    0.21   |  52.799  | 0.9993 |       |        |
| 0.93 | 0.4 | 194000 | 1000  |    2.54   |    0.34   |  25.304  | 0.9992 |       |        |
| 1.24 | 0.4 |  48502 |  200  |    3.67   |    0.81   |  14.922  | 0.9997 |       |        |
| 1.55 | 0.4 | 194000 |  200  |    3.18   |    0.77   |  14.488  | 0.9992 |       |        |
| 1.86 | 0.4 | 194000 |  200  |    3.12   |    0.78   |  12.603  | 0.9990 |       |        |
| 2.17 | 0.4 | 194000 |  200  |    3.07   |    0.89   |  11.911  | 0.9971 | 17500 | 0.9992 |
| 2.48 | 0.4 | 194000 |  200  |    3.13   |    0.90   |  12.648  | 0.9979 | 15000 | 0.9991 |
| 3.10 | 0.4 | 194000 |  200  |    3.14   |    0.98   |   9.423  | 0.9964 | 12000 | 0.9991 |
| 4.97 | 0.4 | 194000 |  200  |    3.34   |    1.22   |   9.630  | 0.9983 |  8000 | 0.9990 |
| 6.21 | 0.4 | 194000 |  200  |    3.11   |    1.20   |   9.214  | 0.9959 |  4400 | 0.9993 |
| 0.62 | 0.7 |  48502 |  200  |    2.86   |  8.36E-06 | 7.32E+05 | 0.9973 |  2700 | 0.9990 |
| 0.93 | 0.7 | 194000 |  200  |    2.38   |    0.09   |  54.264  | 0.9968 | 25000 | 0.9990 |
| 1.24 | 0.7 |  48502 |  200  |    3.71   |    0.49   |  15.255  | 0.9993 |       |        |
| 1.55 | 0.7 | 194000 |  200  |    3.61   |    0.53   |  13.125  | 0.9994 |       |        |
| 1.86 | 0.7 |  47500 |  300  |    3.61   |    0.62   |   9.834  | 0.9997 |       |        |
| 2.17 | 0.7 | 194000 |  200  |    3.07   |    0.55   |  10.151  | 0.9998 |       |        |
| 2.48 | 0.7 | 194000 |  200  |    3.42   |    0.72   |   9.036  | 0.9997 |       |        |
| 3.10 | 0.7 | 194000 |  200  |    3.14   |    0.69   |   7.713  | 0.9996 |       |        |
| 4.97 | 0.7 | 194000 |  200  |    3.08   |    0.93   |   6.188  | 0.9984 | 15000 | 0.9990 |
| 6.21 | 0.7 | 194000 |  200  |    3.24   |    1.03   |   6.371  | 0.9987 | 10000 | 0.9991 |
| 0.62 | 1.0 |  48502 |  200  |    2.48   |  1.82E-14 | 1.83E+14 | 0.9938 |  2900 | 0.9990 |
| 0.93 | 1.0 | 194000 |  300  |    2.41   |  1.37E-13 | 2.33E+13 | 0.9947 |  2900 | 0.9990 |
| 1.24 | 1.0 |  48502 |  200  |    3.34   |    0.17   |  25.855  | 0.9974 | 14000 | 0.9990 |
| 1.55 | 1.0 |  47500 |  200  |    3.25   |    0.33   |  12.773  | 0.9977 | 14000 | 0.9990 |
| 1.86 | 1.0 |  47500 |  400  |    3.69   |    0.47   |   8.502  | 0.9984 | 10000 | 0.9991 |
| 2.17 | 1.0 | 194000 |  200  |    2.87   |    0.38   |   9.372  | 0.9989 | 15000 | 0.9990 |
| 2.48 | 1.0 | 194000 |  200  |    3.39   |    0.52   |   7.209  | 0.9990 |       |        |
| 3.10 | 1.0 |  19400 |  300  |    3.36   |    0.61   |   5.852  | 0.9994 |       |        |
| 4.97 | 1.0 |  48502 |  200  |    3.04   |    0.77   |   4.749  | 0.9989 | 48502 | 0.9991 |
| 6.21 | 1.0 | 194000 |  200  |    3.13   |    0.88   |   4.417  | 0.9975 | 12500 | 0.9991 |
| 0.62 | 1.3 |  48502 |  200  |    2.12   |  1.87E-10 | 1.11E+10 | 0.9904 |  1800 | 0.9991 |
| 0.93 | 1.3 | 194000 |  300  |    1.96   |  3.80E-06 | 6.10E+05 | 0.9928 |  2600 | 0.9992 |
| 1.24 | 1.3 |  48502 |  300  |    3.32   |    0.02   | 179.189  | 0.9967 |  2600 | 0.9991 |
| 1.55 | 1.3 | 194000 |  200  |    3.47   |    0.27   |  11.920  | 0.9958 |  9000 | 0.9990 |
| 1.86 | 1.3 |  47500 |  400  |    3.97   |    0.36   |   8.594  | 0.9970 |  7000 | 0.9991 |
| 2.17 | 1.3 | 194000 |  200  |    2.76   |    0.21   |  12.412  | 0.9966 | 10000 | 0.9990 |
| 2.48 | 1.3 | 194000 |  200  |    3.26   |    0.45   |   7.464  | 0.9985 | 11000 | 0.9990 |
| 3.10 | 1.3 |  47500 |  200  |    3.37   |    0.50   |   5.159  | 0.9984 |  6000 | 0.9992 |
| 4.97 | 1.3 |  48502 |  200  |    2.68   |    0.49   |   4.048  | 0.9983 |  4000 | 0.9993 |
| 6.21 | 1.3 | 194000 |  200  |    2.70   |    0.59   |   3.555  | 0.9991 |       |        |
+------+-----+--------+-------+-----------+-----------+----------+--------+-------+--------+
'''

# Strings of data as text files
data_as_file = {'horizontal': StringIO(hor_str\
                                       .replace('\n|','\n')\
                                       .replace('|\n','\n')),
                'vertical':   StringIO(ver_str\
                                       .replace('\n|','\n')\
                                       .replace('|\n','\n'))
                }

# Load data into numpy arrays
datasets = {}
for name in data_as_file:
    datasets[name] = {}
    data_source = data_as_file[name]
    temp_dset = np.genfromtxt(data_source, delimiter='|', dtype=None,
                              skip_header=5, skip_footer=1,
                              usecols=(0,1,4,5,6),
                              names=('E','T','muS','muL','gamma'))
    #for attribute in temp_dset.dtype.names:
    datasets[name]['E'] = temp_dset['E'] * ureg('V/cm')
    datasets[name]['T'] = temp_dset['T'] * ureg('(g/(100 mL))*100')
    datasets[name]['muS'] = temp_dset['muS'] * ureg('1E-8 m**2/(V*s)')
    datasets[name]['muL'] = temp_dset['muL'] * ureg('1E-8 m**2/(V*s)')
    datasets[name]['gamma'] = temp_dset['gamma'] * ureg('kbp')
     
del hor_str, ver_str, data_as_file, data_source, temp_dset

# vWBR equation
def vWBR(muS, muL, gamma):
    '''vWBR equation'''
    alpha = 1/muL - 1/muS
    beta = 1/muS
    return lambda L: 1/(beta + alpha * (1 - np.exp(-L/gamma)))

# Mobility function: mu(L) = f(muS, muL, gamma)
mu_funcs = {}
for name in datasets:
    mu_funcs[name] = vWBR(datasets[name]['muS'].to('cm**2/V/s'),  # cm^2/(V.sec)
                          datasets[name]['muL'].to('cm**2/V/s'),  # cm^2/(V.sec)
                          datasets[name]['gamma'].to('bp')  # bp
                          )
del name

# Constants
kB = ureg.boltzmann_constant.to('m**2 * kg / s**2 / K')  # Boltzmann constant (1.3806488E-23 m^2.kg/(s^2.K))
lp = 50 * ureg('nm')  # persistence length of dsDNA (nm)
l = 2 * lp            # Kuhn length (nm)
b = 0.34 * ureg('nm/bp')  # curvilinear length dsDNA (nm/bp)
e = ureg.e.to('A*s')  # elementary charge (1.602176565E-19 A.s)
qeff = e/Q_(7,'bp')  # effective charge per dsDNA base pair (A.s/bp)
constants = {'kB': kB, 'lp': lp, 'l': l, 'b': b, 'qeff': qeff}

# mobility = distance/(time*field)
runtime = lambda distance, mobility, field: distance/(mobility*field)

rundistance = lambda time, mobility, field: time*mobility*field

# Intrinsic band broadening as function of the diffusion coefficient and time
bandbroadening = lambda D, time: np.sqrt(2*D*time)

pore_size = lambda gamma, muL, mu0, lp, b: (gamma*muL*lp*b/mu0)**(1/2)

pore_size_fit = lambda C: 143*ureg('nm*g**0.59/mL**0.59')*C**(-0.59)

radius_gyration = lambda L, lp: (lp*L/3*(1-lp/L+lp/L*np.exp(-L/lp)))**(1/2)

H2Oviscosity = lambda T: 2.414E-5*ureg('kg/m/s')*10**(247.8*ureg.K/(T-140*ureg.K))  # (Pa.s)=(kg/(m.s)) accurate to within 2.5% from 0 °C to 370 °C

contour_length = lambda Nbp, b: Nbp*b

reduced_field = lambda eta, a, mu0, E, kB, T: eta*a**2*mu0*E/(kB*T)

reduced_field_Kuhn = lambda eta, l, mu0, E, kB, T: eta*l**2*mu0*E/(kB*T)

# Diffusion coefficient of a blob
Dblob = lambda kB, T, eta, a: kB*T/(eta*a)

# Diffusion coefficient of a Kuhn segment
DKuhn = lambda kB, T, eta, l: kB*T/(eta*l)

# Relations between basepairs (Nbp), Kuhn segments (NKuhn) and blobs (N)
Nbp_to_NKuhn = lambda Nbp, b, l: Nbp*b/l  # number of Kuhn segments (~= Nbp/300)
NKuhn_to_Nbp = lambda NKuhn, b, l: NKuhn*l/b  # number of base pairs (bp)
NKuhn_to_N = lambda NKuhn, l, a: NKuhn*(l/a)**2  # number of occupied pores
N_to_NKuhn = lambda N, a, l: N*(a/l)**2  # number of Kuhn segments
N_to_Nbp = lambda N, a, b, l: N*(l/b)*(a/l)**2  # number of base pairs (bp)
Nbp_to_N = lambda Nbp, a, b, l: Nbp*(b/l)*(l/a)**2  # number of occupied pores

# Individual diffusion regimes
reptation_equilibrium = lambda Dblob, N: Dblob/N**2
reptation_accelerated = lambda Dblob, epsilon, N: Dblob*epsilon*N**(-1/2)
reptation_plateau = lambda Dblob, epsilon: Dblob*epsilon**(3/2)
free_solution = lambda kB, T, eta, Rh: kB*T/(6*np.pi*eta*Rh)
Zimm_g = lambda Nbp, DRouse, qeff, mu0, kB, T: DRouse*Nbp*qeff/(mu0*kB*T)
Ogston_Zimm = lambda D0, g: D0 * g
Ogston_Rouse = lambda Nbp, kB, T, a, eta, b, l: kB*T*a**3/(eta*b**2*l**2*Nbp**2)

# Diffusion regime frontiers (in number of occupied pores)
Zimm_Rouse = lambda x0, args: (
    Nbp_to_N(fsolve(diff_Zimm_Rouse, x0, args)[0] * ureg.bp,
             args[5], args[6], args[7]))
equil_accel = lambda epsilon: epsilon**(-2/3)
accel_plateau = lambda epsilon: epsilon**(-1)

def diff_Zimm_Rouse(Nbp, args):
    kB, T, qeff, eta, mu0, a, b, l, lp = args
    Nbp = Q_(Nbp[0], 'bp')
    L = contour_length(Nbp, b)
    Rg = radius_gyration(L, lp)
    D0 = free_solution(kB, T, eta, Rg)
    DRouse = Ogston_Rouse(Nbp, kB, T, a, eta, b, l)
    g = Zimm_g(Nbp, DRouse, qeff, mu0, kB, T)
    g = g.to_base_units()
    DZimm = Ogston_Zimm(D0, g)
##    print 'Nbp =\t', Nbp
##    print 'kB =\t', kB
##    print 'T =\t', T
##    print 'qeff =\t', qeff
##    print 'eta =\t', eta
##    print 'mu0 =\t', mu0
##    print 'a =\t', a
##    print 'b =\t', b
##    print 'l =\t', l
##    print 'lp =\t', lp
##    print 'L =\t', L
##    print 'Rg =\t', Rg
##    print 'D0 =\t', D0
##    print 'DRouse =\t', DRouse
##    print 'g =\t', g
##    print 'DZimm =\t', DZimm
##    print 'DZimm - DRouse =\t', DZimm - DRouse
##    print 70*'#'
    return DZimm - DRouse

# Diffusion coefficient
def diffusion_coefficient(Nbp, N_lim1, N_lim2, N_lim3, args):
    kB, T, qeff, eta, mu0, a, b, l, lp = args
    N = Nbp_to_N(Nbp, a, b, l)
    if N < N_lim3:
        # Ogston-Zimm
        L = contour_length(Nbp, b)
        Rg = radius_gyration(L, lp)
        D0 = free_solution(kB, T, eta, Rg)
        DRouse = Ogston_Rouse(Nbp, kB, T, a, eta, b, l)
        g = Zimm_g(Nbp, DRouse, qeff, mu0, kB, T)
        D = Ogston_Zimm(D0, g)
    elif N < N_lim2:
        # Rouse/Reptation-equilibrium
        D = Db/N**2
    elif N > N_lim1:
        # Reptation-plateau (reptation with orientation)
        D = Db*epsilon**(3/2)
    else:
        # Accelerated-reptation
        D = Db*epsilon*N**(-1/2)
    return D

def rand_str(sample, length):
    rnd_str = ''
    for i in xrange(length):
        r = randint(0, len(sample)-1)
        rnd_str += sample[r]
    return rnd_str

def randDNAseqs(sizes):
    ladder = []
    for size in sizes:
        seq = pydna.Dseq(rand_str('actg', size))
        ladder.append(seq)
    return ladder

def gen_ladder(sizes, quantities, vol=Q_(12,'ul')):
    frags = randDNAseqs(to_units(sizes, 'bp').magnitude)
    return Sample(frags, quantities, vol)

def ladder_from_info(key, qty=Q_(500,'ng'), vol=Q_(12,'ul')):
    assert key in ladders, "Key not recognized. Choose from: %s" %ladders.keys()
    qty = to_units(qty, Vars['quantities']['units'], var_name='qty')
    vol = to_units(vol, Vars['volume']['units'], var_name='vol')
    sizes = ladders[key]['sizes']
    fracs = ladders[key]['percent']
    quantities = qty*fracs
    return gen_ladder(sizes, quantities, vol)

def logspace_int(minimum, maximum, divs):
    space = np.logspace(np.log10(minimum), np.log10(maximum), divs)
    return np.array([int(round(val, 0)) for val in space])

def flatten(List):
    if List == []: return List
    flatL = []
    for elem in List:
        if not isinstance(elem, Q_) and hasattr(elem, '__iter__'):
            flatE = flatten(elem)
            [flatL.append(E) for E in flatE]
        else:
            flatL.append(elem)
    return flatL

# Gaussian function
Gaussian = lambda x, hgt, ctr, dev: hgt*np.exp(-(x-ctr)**2/(2*dev**2))
Gauss_hgt = lambda auc, dev: auc/(dev*np.sqrt(2*np.pi))
Gauss_dev = lambda FWHM: FWHM/(2*np.sqrt(2*np.log(2)))
#Gauss_dev = lambda FWTM: FWTM/(2*np.sqrt(2*np.log(10)))
Gauss_FWHM = lambda FWTM: FWTM * np.sqrt(2*np.log(2))/np.sqrt(2*np.log(10))


def _to_units(quantity, units, var_name=None):
    '''Asserts that the quantity has the proper dimensions
    (inferred from the default units) if the quantity is an instance of
    pint.unit.Quantity or assigns the default units if it's not.
    '''
    if isinstance(quantity, Q_):
        try:
            quantity = quantity.to(units)
        except TypeError as error:
            quantity = [q.to(units) for q in quantity]
        except Exception as error:
            if var_name: error.extra_msg = " for variable '%s'" %var_name
            raise error
    else: quantity = Q_(quantity, units)
    return quantity


def to_units(quantity, units, var_name=None):
    '''Asserts that the quantity has the proper dimensions
    (inferred from the default units) if the quantity is an instance of
    pint.unit.Quantity or assigns the default units if it's not.
    '''
    if (not isinstance(quantity, Q_) and hasattr(quantity, '__iter__') and
        len(quantity) > 0 and sum([isinstance(q, Q_) for q in flatten(quantity)]) > 0):
        temp_qty = [to_units(q, units, var_name) for q in quantity]
        quantity = Q_([q.magnitude for q in temp_qty], units)
    else:
        quantity = _to_units(quantity, units, var_name)
    return quantity


def dim_or_units(quantity, reference):
    """If <quantity> is not an instance of <Quantity>, instantiate a <Quantity>
    object with <quantity> as magnitude and as <reference.units> as units.
    If <quantity> is an instance of <Quantity>, check whether it has the same
    dimensionality as <reference>.
    """
    if not isinstance(quantity, Q_):
        quantity = to_units(quantity, reference.units)
    else:
        assert quantity.dimensionality == reference.dimensionality, (
            "Dimension mismatch: (%s) != (%s)" %(quantity.dimensionality,
                                                 reference.dimensionality))
    return quantity


def assign_quantities(samples, quantities, maxdef=Q_(150,'ng')):
    '''
    Assigns quantities (masses in nanograms) to the DNA fragments without
    corresponding quantity assuming a linear relationship between the DNA
    length (in basepairs) and its mass. As if the fragments originated in
    a restriction procedure.
    For each sample takes the maximum quantity (either from the other samples
    or from the default) and assigns it to the fragment with greater length.
    '''
    outQs = []
    units = Vars['quantities']['units']
    maxQ = Q_(0, units)
    # Preprocessing
    if quantities is None: quantities = []
    if isinstance(quantities, Q_):
        if isinstance(quantities.magnitude, Number):
            quantities = Q_([quantities.magnitude for i in
                             xrange(len(samples))], quantities.units)
        else:
            for i, qty in enumerate(quantities.magnitude):
                if qty is None:
                    quantities.magnitude[i] = []
    else:
        if isinstance(quantities, Number):
            quantities = [quantities for i in xrange(len(samples))]
        elif hasattr(quantities, '__iter__'):
            for i, qty in enumerate(quantities):
                if qty is None:
                    quantities[i] = []
    quantities = to_units(quantities, units, 'quantities')
    # Quantity assignment - straightforward cases
    for i in xrange(len(samples)):
        if i < len(quantities) and isinstance(quantities[i].magnitude, Number):
            # Divide sample quantity by its DNA fragments (linearly)
            sizes = [len(dna) for dna in samples[i]]
            Ltotal = sum(sizes)
            Qtotal = quantities[i].magnitude
            outQs.append(Q_([size*Qtotal/Ltotal for size in sizes], units))
            if max(outQs[i]) > maxQ: maxQ = max(outQs[i])
        elif i < len(quantities) and len(quantities[i]) == len(samples[i]):
            # Directly assigns each quantity to its corresponding DNA fragment
            outQs.append(quantities[i])
            if max(quantities[i]) > maxQ: maxQ = max(quantities[i])
        else:
            outQs.append([])
    # Quantity assignment - missing values
    if maxQ.magnitude == 0: maxQ = to_units(maxdef, units, 'maxdef')
    maxQ = maxQ.magnitude
    for i in xrange(len(samples)):
        if outQs[i] == []:
            # Linearly extrapolates each DNA fragment's quantity taking as
            # reference the maximum quantity registered (or the default)
            sizes = [len(dna) for dna in samples[i]]
            maxL = max(sizes)
            outQs[i] = Q_([size*maxQ/maxL for size in sizes], units)
    return outQs


def assign_quantitiesB(samples, maxdef=Q_(150,'ng')):
    '''
    Assigns quantities (masses in nanograms) to the DNA fragments without
    corresponding quantity assuming a linear relationship between the DNA
    length (in basepairs) and its mass. As if the fragments originated in
    a restriction procedure.
    For each sample takes the maximum quantity (either from the other samples
    or from the default) and assigns it to the fragment with greater length.
    '''
    quantities = []
    units = Vars['quantities']['units']
    maxQ = Q_(0, units)
    # Preprocessing and straightforward cases
    for sample in samples:
        sample_qts = []
        for qty in sample.quantities:
            if not np.isnan(qty.magnitude) and qty.magnitude is not None:
                sample_qts.append(qty)
                if qty > maxQ: maxQ = qty
        quantities.append(sample_qts)
    # Quantity assignment - missing values
    if maxQ.magnitude == 0: maxQ = to_units(maxdef, units, 'maxdef')
    maxQ = maxQ.magnitude
    for i, sample in enumerate(samples):
        if quantities[i] == []:
            # Linearly extrapolates each DNA fragment's quantity taking as
            # reference the maximum quantity registered (or the default)
            sizes = [len(dna) for dna in sample.solutes]
            maxL = max(sizes)
            quantities[i] = [size*maxQ/maxL for size in sizes]
    quantities = to_units(quantities, units, 'quantities')
    return quantities


def lindivQ(sample, quantity, criteria=len):
    """
    Linearly divides a quantity by the elements of sample considering a
    criteria. Criteria must by a function that returns a number upon being
    applied to each element of sample.
    """
    sizes = [criteria(dna) for dna in sample]
    return [size*quantity/sum(sizes) for size in sizes]


def size_to_mobility(dna_len, field, percentage,
                     mu_func = mu_funcs['vertical'],
                     dataset = datasets['vertical'],
                     method = 'linear',
                     replNANs = True):
    """
    At some point this will have a description...
    """
    mobility = griddata((dataset['E'], dataset['T']), mu_func(dna_len),
                        (field, percentage), method)
    if replNANs and np.isnan(mobility):
        # Replace NANs by 'nearest' interpolation
        print "WARNING: NAN replaced by 'nearest' interpolation." ####### ! ###
        mobility = griddata((dataset['E'], dataset['T']), mu_func(dna_len),
                            (field, percentage), method='nearest')
    return mobility.item()



def vWBRfit(field, percentage, DNAvals=np.linspace(100,50000,100),
            dataset = datasets['vertical'], mu_func = mu_funcs['vertical'],
            method = 'linear', replNANs = True, plot=True):
    """
    At some point this will have a description...
    """
    mu = np.zeros(len(DNAvals))
    vWBR = lambda L, muS, muL, gamma: (1/muS+(1/muL-1/muS)*(1-np.exp(-L/gamma)))**-1
    for i, Li in enumerate(DNAvals):
        mu[i] = size_to_mobility(Li, field, percentage, mu_func,
                                 dataset, method, replNANs)
    def residuals(pars, L, mu):
        return mu - vWBR(L, *pars)
    muS0 = 3.5E-4  # cm^2/(V.sec)  ############################################
    muL0 = 1.0E-4  # cm^2/(V.sec)  ############################################
    gamma0 = 8000  # bp            ############################################
    pars, cov, infodict, mesg, ier = leastsq(residuals, [muS0,muL0,gamma0],
                                             args=(DNAvals, mu),
                                             full_output=True)
    muS, muL, gamma = pars
    #print ('E=%.2f V/cm, T=%.1f %%, muS=%.3e, muL=%.3e cm^2/(V.s), gamma=%s bp'
    #       %(field, percentage, muS, muL, gamma))
    if plot:
        DNAmin = min(DNAvals)
        DNAmax = max(DNAvals)
        fig = plt.figure()
        ax = fig.add_subplot(111)
        ax.scatter(DNAvals, mu*1E4, color='blue')
        ax.plot(DNAvals, vWBR(DNAvals, muS, muL, gamma)*1E4, label='fit',
                linestyle='--', color='red')
        ax.set_xlim(DNAmin-0.1*DNAmin, DNAmax+0.1*DNAmax)
        ax.set_ylim((min(mu)-0.1*min(mu))*1E4, (max(mu)+0.1*max(mu))*1E4)
        ax.set_xscale('log')
        ax.xaxis.set_major_formatter(mtick.FormatStrFormatter('%d'))
        ax.tick_params(which='both', top='off', right='off')
        ax.set_xlabel('$\mathrm{DNA\,length\,(bp)}$', fontsize=14)
        ax.set_ylabel(r'$\mu\times{10^{8}}\,(\mathrm{m^{2}/V\cdot s})$',
                      fontsize=14)
        ax.set_title('$\mu_S=%.2e,\,\mu_L=%.2e\,\mathrm{cm^2/(V.s)},\,\gamma=%d \mathrm{bp}$'
                     %(muS, muL, gamma))
        ax.legend().draggable()
        plt.show()
    return pars, cov, infodict, mesg, ier



def ferguson_to_mu0(field, Tvals, DNAvals, dataset, mu_func,
                    adjmethod='linear', replNANs=True, plot=True):
    '''
    This function extrapolates the free solution mobility (mu0)
    for a specified electric field intensity (field), via Ferguson plot
    (ln(mobility) vs. %agarose).

    Mobiliy calculation method:
    [E,T,muS,muL,gamma] -> [E,T,mu(L)] -(L*)-> [E,T,mu] -(E*,T*,interp.)-> mu*
    '''
    #Mobility dependence on size (mu(L)) for each agarose percentage (Ti)
    ln_mu_LxT = []
    for Lj in DNAvals:
        ln_mu_T = []
        for Ti in Tvals:
            mu = size_to_mobility(Lj, field, Ti, mu_func,
                                  dataset, adjmethod, replNANs)
            ln_mu_T.append(np.log(mu))
        ln_mu_LxT.append(ln_mu_T)
    ln_mu_LxT = np.array(ln_mu_LxT)
    #Linear regression for each DNA size
    lregr_stats = []
    exclude = []
    for l in xrange(len(DNAvals)):
        not_nan = np.logical_not(np.isnan(ln_mu_LxT[l]))
        if sum(not_nan) > 1:
            #(enough points for linear regression)
            gradient, intercept, r_value, p_value, std_err =\
                      stats.linregress(Tvals[not_nan], ln_mu_LxT[l][not_nan])
            lregr_stats.append((gradient, intercept, r_value, p_value, std_err))
            exclude.append(False)
        else:
            exclude.append(True)
    exclude = np.array(exclude)
    DNAvals = DNAvals[~exclude]
    ln_mu_LxT = ln_mu_LxT[~exclude]
    if len(lregr_stats)>0:
        #Free solution mobility determination
        ln_mu0 = np.mean([row[1] for row in lregr_stats])  #mean of intercepts
        mu0 = np.exp(ln_mu0)  # cm^2/(V.seg)
    else:
        mu0 = None
    if plot and len(ln_mu_LxT)>0:
        #Ferguson Plot (ln(mu) vs. %T) --> mu0
        regline = lambda m, b, x: m*x+b #Line function (for the plot)
        colors = cm.rainbow(np.linspace(0, 1, len(DNAvals)))
        Tvals0 = np.concatenate([[0], Tvals])
        fig = plt.figure()
        ax = fig.add_subplot(111)
        for l in xrange(len(DNAvals)):
            ax.scatter(Tvals, ln_mu_LxT[l], label=DNAvals[l],
                       color=colors[l])
            m = lregr_stats[l][0]
            b = lregr_stats[l][1]
            ax.plot(Tvals0, [regline(m, b, t) for t in Tvals0],
                    color=colors[l])
        ax.set_xlim(0)
        #ax.set_ylim(-10, -7.5)
        ax.legend(title='$\mathrm{DNA size (bp)}$',
                  prop={'size':10}).draggable()
        ax.tick_params(which='both', top='off', right='off')
        ax.set_xlabel('$\%\,agarose$', fontsize=14)
        ax.set_ylabel('$\mathrm{ln(mobility\,[cm^{2}/V sec])}$',
                      fontsize=14)
        ax.set_title('$\mathrm{Ferguson\,plot}$'+'\n'+\
                     '$\mathrm{ln(mobility)\,vs.\,\%\,agarose\,}$'+\
                     '$\mathrm{(field=%s\,V/cm)}$' %field)
        plt.show()
    return mu0  # cm^2/(V.seg)



def gelplot_imshow(distances, bandwidths, intensities, lanes, names,
                   gel_len, wellx, welly, wellsep, res, cursor_ovr,
                   back_col, band_col, well_col, noise, Itol, title,
                   FWTM, show=True):
    """
    At some point this will have a description...
    """
    nlanes = len(lanes)
    gel_width = sum(wellx) + (nlanes+1)*wellsep  # cm
    res = res.to('px/cm')
    pxl_x = int(round(gel_width * res))
    pxl_y = int(round(gel_len * res))
    centers = [(l+1)*wellsep + sum(wellx[:l]) + 0.5*wellx[l]
               for l in xrange(nlanes)]
    rgb_arr = np.zeros(shape=(pxl_y, pxl_x, 3), dtype=np.float32)
    bandlengths = wellx
    # Paint the bands
    for i in xrange(nlanes):
        distXmid = centers[i]
        pxlXmid = distXmid * res
        bandlength = bandlengths[i]
        from_x = int(round((distXmid - bandlength/2.0) * res))
        to_x   = int(round((distXmid + bandlength/2.0) * res))
        for j in xrange(len(lanes[i])):
            distYmid = distances[i][j]
            pxlYmid = int(round(distYmid * res))
            bandwidth = bandwidths[i][j]  # w=FWHM or w=FWTM ???
            if FWTM:
                FWHM = Gauss_FWHM(bandwidth)
            else:
                FWHM = bandwidth
            std_dev = Gauss_dev(FWHM)
            maxI = intensities[i][j]
            midI = Gaussian(distYmid, maxI, distYmid, std_dev)
            if pxlYmid < len(rgb_arr):  # band within gel frontiers
                rgb_arr[pxlYmid, from_x:to_x] += midI
            bckwdYstop = False if pxlYmid > 0 else True
            forwdYstop = False if pxlYmid < len(rgb_arr)-1 else True
            pxlYbck = pxlYmid-1
            pxlYfor = pxlYmid+1
            while not bckwdYstop or not forwdYstop:
                if not bckwdYstop:
                    distYbck = Q_(pxlYbck,'px')/res
                    bckYI = Gaussian(distYbck, maxI, distYmid, std_dev)
                    if pxlYbck < len(rgb_arr):
                        rgb_arr[pxlYbck, from_x:to_x] += bckYI
                    pxlYbck -= 1
                    if bckYI <= Itol or pxlYbck == -1:
                        bckwdYstop = True
                if not forwdYstop:
                    distYfor = Q_(pxlYfor,'px')/res
                    forYI = Gaussian(distYfor, maxI, distYmid, std_dev)
                    rgb_arr[pxlYfor, from_x:to_x] += forYI
                    pxlYfor += 1
                    if forYI <= Itol or pxlYfor == pxl_y:
                        forwdYstop = True
    # Background color
    if noise is None or noise <= 0:
        rgb_arr += back_col
    else:
        bckg = np.random.normal(back_col, noise,
                                (len(rgb_arr), len(rgb_arr[0])))
        rgb_arr += bckg[:,:,np.newaxis]
    # Saturation
    rgb_arr[rgb_arr > 1] = 1
    rgb_arr[rgb_arr < 0] = 0
    #bands_arr = np.ma.masked_where(rgb_arr == back_col, rgb_arr)  #############
    bands_arr = rgb_arr
    # Plot
    gel_len = gel_len.magnitude
    gel_width = gel_width.magnitude
    wellx = wellx.magnitude
    welly = welly.magnitude
    wellsep = wellsep.magnitude
    centers = [c.magnitude for c in centers]
    bandlengths = bandlengths.magnitude
    bandwidths = [[bw.magnitude for bw in bwlane] for bwlane in bandwidths]
    fig = plt.figure()
    ax1 = fig.add_subplot(111, axisbg=str(back_col))
    ax1.xaxis.tick_top()
    ax1.yaxis.set_ticks_position('left')
    ax1.spines['left'].set_position(('outward', 8))
    ax1.spines['left'].set_bounds(0, gel_len)
    ax1.spines['right'].set_visible(False)
    ax1.spines['bottom'].set_visible(False)
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_color(str(back_col))
    ax1.spines['bottom'].set_color(str(back_col))
    ax1.xaxis.set_label_position('top')
    plt.xticks(centers, names)
    majorLocator = FixedLocator(range(int(gel_len+1)))
    minorLocator = FixedLocator([j/10.0 for k in range(0, int(gel_len+1)*10, 10)
                                 for j in range(1+k, 10+k, 1)])
    ax1.yaxis.set_major_locator(majorLocator)
    ax1.yaxis.set_minor_locator(minorLocator)
    ax1.tick_params(axis='x', which='both', top='off')
    bands_plt = ax1.imshow(bands_arr, extent=[0, gel_width, gel_len, 0],
                           interpolation='none')
    # Draw wells
    for i in xrange(nlanes):
        ctr = centers[i]
        wx = wellx[i]
        wy = welly[i]
        ax1.fill_between(x=[ctr-wx/2, ctr+wx/2], y1=[0,0],
                         y2=[-wy, -wy], color=str(well_col))
    # Invisible rectangles overlapping the bands for datacursor to detect
    bands = []
    for i in xrange(nlanes):
        bandlength = bandlengths[i]
        center = centers[i]
        x = center - bandlength/2.0
        for j in xrange(len(lanes[i])):
            dna_frag = lanes[i][j]
            bandwidth = bandwidths[i][j]
            dist = distances[i][j].magnitude
            y = dist - bandwidth/2.0
            band = plt.Rectangle((x,y), bandlength, bandwidth, fc='r',
                                 alpha=0, label='{} bp'.format(len(dna_frag)))
            plt.gca().add_patch(band)
            bands.append(band)
    plt.ylim(gel_len, -max(welly))
    xlim = sum(wellx) + (nlanes+1)*wellsep
    plt.xlim(0, xlim)
    plt.ylabel('Distance (cm)')
    plt.xlabel('Lanes')
    bbox_args = dict(boxstyle='round,pad=0.6', fc='none')
    an1 = plt.annotate(title, xy=(0,0),
                       xytext=(xlim+0.4, (gel_len+max(welly))/2.0),
                       va="center", bbox=bbox_args)
    an1.draggable()
    plt.gca().set_aspect('equal', adjustable='box')
    cursor_args = dict(display='multiple',
                       draggable=True,
                       hover = False,
                       bbox=dict(fc='white'),
                       arrowprops=dict(arrowstyle='simple',
                                       fc='white', alpha=0.5),
                       xytext=(15, -15),
                       formatter='{label}'.format)
    if cursor_ovr:
        for key in cursor_ovr:
            cursor_args[key] = cursor_ovr[key]
    if cursor_args['hover'] == True: cursor_args['display'] = 'single'
    datacursor(bands, **cursor_args)
    #fig.savefig('example.png', dpi=300)
    if show: plt.show()
    return plt



class Sample:
    '''
    A rudimentary sample object to serve as DNA container.
    Assumption:
        A1) Liquid state;
        A2) Homogeneous;
        A3) No chemical reaction;
        A4) Solvent not considered (mere abstraction from volume).
    '''
    ### Misses setters and getters

    def __init__(self,
                 solutes = [],
                 quantities = Q_([], 'ng'),
                 volume = Q_(10, 'ul'),
                 endless = False):
        #assert len(solutes) == len(quantities), "len(solutes) != len(quantities)"
        quantities = (quantities if isinstance(quantities, Q_) else
                      to_units(quantities, Vars['quantities']['units']))
        assert quantities.dimensionality == Q_(1, 'g').dimensionality or \
               quantities.dimensionality == Q_(1, 'mol').dimensionality, (
                   "Dimension of <quantities> must be [mass] or [substance]")
        volume = (volume if isinstance(volume, Q_) else
                  to_units(volume, Vars['volume']['units']))
        assert volume.dimensionality == Q_(1, 'L').dimensionality, (
            "Dimension of <volume> must be [length]**3")
        qty_list = quantities.tolist()
        for i, sol in enumerate(solutes):
            if i >= len(qty_list):
                qty_list.append(np.nan)
        quantities = to_units(qty_list, quantities.units, 'quantities')
        self.volume = volume
        self.endless = endless
        if len(solutes) > 0:
            uniqSols = []
            uniqQtis = []
            for i, sol in enumerate(solutes):
                if sol in uniqSols:
                    j = uniqSols.index(sol)
                    uniqQtis[j] += quantities[i].magnitude
                else:
                    uniqSols.append(sol)
                    uniqQtis.append(quantities[i].magnitude)
            solutes = uniqSols
            quantities = Q_(uniqQtis, quantities.units)
        self.solutes = solutes
        self.quantities = quantities

    def __repr__(self):
        return ("<sample: vol=%s%s, %d solutes (%s)>"
                %(self.volume, " (endless)" if self.endless else "",
                  len(self.solutes), sum(self.quantities))
                )

    def __str__(self):
        # This needs to be simplified...
        if self.solutes == []:
            Vunit = str(self.volume)
            Vunit = Vunit[Vunit.find(' ')+1:].replace(' ','')
            Vstr = ('| sample volume = %.1f %s%s (no solutes) |'
                    %(self.volume.magnitude, Vunit,
                      " (endless)" if self.endless else ""))
            string = ('+'+(len(Vstr)-2)*'-'+'+\n' + Vstr+'\n'
                      +'+'+(len(Vstr)-2)*'-'+'+')
            return string        
        #Sstr = [str(s) if len(str(s)) <= 10 else str(s)[0:10]+'...' for s in self.solutes]
        Sstr = [str(repr(s).replace('\n','/')) for s in self.solutes]
        Sstr.insert(0, "Solute")
        lS = len(max(Sstr, key=len))
        Sstr = [s.ljust(lS) for s in Sstr]
        Qstr = ['%.1f ' %q.magnitude for q in self.quantities]
        Qunit = str(self.quantities[0])
        Qunit = Qunit[Qunit.find(' ')+1:].replace(' ','')
        Qstr.insert(0, "Q (%s)" %Qunit)
        lQ = len(max(Qstr, key=len))
        Qstr = [s.rjust(lQ) for s in Qstr]
        concentrations = self.concentrations()
        Cstr = ['%.2f   ' %c.magnitude for c in concentrations]
        Cunit = str(concentrations[0])
        Cunit = Cunit[Cunit.find(' ')+1:].replace(' ','')
        Cstr.insert(0, "C (%s)" %Cunit)
        lC = len(max(Cstr, key=len))
        Cstr = [s.rjust(lC) for s in Cstr]
        prop = [q/sum(self.quantities)*100 for q in self.quantities]
        Pstr = [str(round(p.magnitude, 1)) for p in prop]
        Pstr.insert(0, "%  ")
        lP = len(max(Pstr, key=len))
        Pstr = [s.rjust(lP) for s in Pstr]
        Istr = [str(i) for i in xrange(len(self))]
        Istr.insert(0, "")
        lI = len(max(Istr, key=len))
        Istr = [s.rjust(lI) for s in Istr]
        wdts = [lI, lS, lQ, lC, lP]
        fullw = 2 + sum(wdts) + (len(wdts)-1)*2
        lines = ['  '.join([Istr[0], Sstr[0], Qstr[0], Cstr[0], Pstr[0]])]
        for i in xrange(1, len(Sstr)):
            line = '  '.join([Istr[i], Sstr[i], Qstr[i], Cstr[i], Pstr[i]])
            lines.append(line)
        Vunit = str(self.volume)
        Vunit = Vunit[Vunit.find(' ')+1:].replace(' ','')
        Vstr = (' sample volume = %.1f %s%s'
                %(self.volume.magnitude, Vunit,
                  " (endless)" if self.endless else ""))
        Vstr = Vstr.ljust(fullw)
        TQstr = ' solutes quantity = %.1f %s' %(sum(self.quantities.magnitude), Qunit)
        TQstr = TQstr.ljust(fullw)
        string = ('+' + fullw*'-'+'+\n' + '| %s |\n' %lines[0]
                  + '|%s|\n'%(fullw*'-')
                  + '\n'.join(['| %s |' %s for s in lines[1:]])
                  + '\n|%s|\n'%(fullw*'-') + '|%s|\n' %(Vstr)
                  + '|%s|\n'%(TQstr) + '+%s+'%(fullw*'-'))
        return string

    def __len__(self):
        """Return number of solutes in sample."""
        return len(self.solutes)

    def __eq__(self, other):
        if self.volume != other.volume or self.endless != other.endless:
            return False
        Sols, Qtis = zip(*sorted(zip(self.solutes, self.quantities)))
        otherSols, otherQtis = zip(*sorted(zip(other.solutes, other.quantities)))
        if Sols != otherSols or Qtis != otherQtis:
            return False
        return True

    def __ne__(self, other):
        if self == other:
            return False
        else:
            return True

    def __add__(self, other):
        totalVol = self.volume + other.volume
        endless = self.endless and other.endless
        solutes = self.solutes[:]
        quantities = self.quantities.tolist()
        for i, sol in enumerate(other.solutes):
            if sol in solutes:
                j = solutes.index(sol)
                quantities[j] += other.quantities[i]
            else:
                solutes.append(sol)
                quantities.append(other.quantities[i])
        quantities = to_units(quantities, self.quantities.units)
        return Sample(solutes, quantities, totalVol, endless)

    def __radd__(self, other):
        if other == 0:
            return self
        else:
            return self.__add__(other)

    def divide(self, k, endless=False):
        ### ERROR: Insufficient volume. ###
        """Divides the sample in k equal (sub)samples."""
        v = self.volume / k
        #vols = [v for i in xrange(k)]
        #vols[-1] = self.volume - sum(vols[:-1])
        if self.endless:
            return [self.aliquot(v, endless) for i in xrange(k)]
        else:
            samples = [self.aliquot(v, endless) for i in xrange(k-1)]
            samples.append(self.aliquot(self.volume, endless))
            return samples

    def total_qty(self):
        """Return sum of quantities."""
        return sum(self.quantities)

    def add_solute(self, solute, quantity):
        """Add a quantity of solute to the sample."""
        if solute in self.solutes:
            i = self.solutes.index(solute)
            self.quantities[i] += quantity
        else:
            self.solutes.append(solute)
            quantities = self.quantities.tolist()
            quantities.append(quantity)
            self.quantities = to_units(quantities, self.quantities.units)

    def aliquot(self, vol, endless=False):
        """Return a new sample corresponding to an aliquot of this sample."""
        vol = (vol if isinstance(vol, Q_) else
               to_units(vol, self.volume.units))
        assert vol.dimensionality == Q_(1, 'L').dimensionality, (
            "Dimension of volume must be [length]**3")
        if vol > self.volume and not self.endless:
            print "Insufficient volume."
        else:
            quantities = self.quantities * vol/self.volume
            endless = endless if endless is not None else self.endless
            if not self.endless:
                self.volume -= vol
                self.quantities -= quantities
            return Sample(self.solutes, quantities, vol, endless)

    def duplicate(self):
        """Return deep copy of sample."""
        return Sample(self.solutes, self.quantities, self.volume, self.endless)

    def stocksolution(self):
        """Return an endless deep copy of sample."""
        return Sample(self.solutes, self.quantities, self.volume, True)

    def concentrations(self):
        """Returns the concentration of every solute."""
        return self.quantities/self.volume

    def concentration(self, index=None, solute=None):
        """Returns the concentration a solute.
        If index and solute are not given, returns all concentrations.
        """
        if index is None and solute is not None:
            index = self.solutes.index(solute)
        if index is not None:
            return self.quantities[index]/self.volume
        else:
            return self.concentrations()

    def dilute(self, factor=None, finalVol=None,
               finalCon=None, index=None, solute=None):
        """Dilutes the sample to the intended concentration or volume by
        adding the necessary volume of solvent. This is done to this sample
        (in place).
        Note that <solute> or its <index> are only relevant as reference for
        <finalCon>. Both <factor> and <finalVol> are solute independent.
        If no index or solute is given, the first solute is taken as reference.
        Prioritizes <finalCon> over <factor> and <factor> over <finalVol>.
        """
        # ! Not yet implemented !
        # To determine the needed initial volume of a sample for a dilution see
        # function or method <vol4dilution>.
        # To generate a new diluted sample from an aliquot of an initial sample,
        # see function <gen_dilution>.
        condition = (factor is not None or finalCon is not None
                     or finalVol is not None)
        message = "Must provide <factor>, <finalCon> or <finalVol>."
        assert condition, message
        if finalVol is not None:
            finalVol = dim_or_units(finalVol, Q_(1, Vars['volume']['units']))
        if finalCon is not None:
            finalCon = dim_or_units(finalCon, Q_(1, 'ng/ul'))
        if index is None and finalCon is not None:
            if solute is not None:
                index = self.solutes.index(solute)
            else:
                index = 0
        if factor is not None:
            finalVol = self.volume / factor
        if finalCon is not None:
            iniCon = self.concentration(index)
            iniVol = self.volume
            finalVol = iniCon*iniVol/finalCon
        self.volume = finalVol



class Gel:
    '''
    At some point this will have a description...
    Notes:
    '''

    def __init__(self,
                 samples,
                 names = None,
                 percentgel = Q_(1.0,'(g/(100 mL))*100'),  # grams agarose/100 mL buffer * 100
                 electrfield = Q_(5.0, 'V/cm'),
                 temperature = Q_(295.15,'K'),
                 gel_len = Q_(8,'cm'),
                 wellx = Q_(7,'mm'),
                 welly = Q_(2,'mm'),
                 wellz = Q_(1,'mm'),   # mm   ######################### ??? ###
                 wellsep = Q_(2,'mm')  # mm
                 ):
        """
        default volume = 0.85 * well Volume
        default max quantity per band = 150 ng
        """
        
        self.samples = samples  # assumes len(DNA) in bp                        #
        self.names = names if names else ['lane'+str(i) for i in      #
                                          xrange(1, len(samples)+1)]  #
        self.percent = to_units(percentgel, '(g/(100 mL))*100', 'percentgel') # agarose percentage
        self.field = to_units(electrfield, 'V/cm', 'electrfield')  # electric field intensity
        self.temperature = to_units(temperature, 'K', 'temperature')  # absolute temperature
        self.gel_len = to_units(gel_len, 'cm', 'gel_len')  # lane length
        self.wellx = to_units(wellx, 'mm', 'wellx')  # well width
        self.welly = to_units(welly, 'mm', 'welly')  # well height
        self.wellz = (to_units(wellz, 'mm', 'wellz') if wellz is not None
                      else wellz)  # well depth
        self.wellsep = to_units(wellsep, 'mm', 'wellsep')  # separation between wells
        # Volumes
        wellVol = self.wellx * self.welly * self.wellz
        wellVol.ito('ul')
        defaulVol = 0.85 * wellVol
        volumes = []
        for sample in self.samples:
            vol = sample.volume
            if not np.isnan(vol) and vol is not None:
                volumes.append(vol)
            else:
                volumes.append(defaulVol)
        self.volumes = to_units(volumes, 'uL', 'volumes')
        # Quantities
        defaulQty = Q_(150,'ng')
        self.quantities = assign_quantitiesB(self.samples, defaulQty)
        #self.quantities = assign_quantities(self.samples, quantities, defaulQty)
        self.runtime = np.nan                                        ##########
        self.freesol_mob = None
        self.mobilities = []
        self.distances = []
        self.bandwidths0 = []
        self.bandwidthsI = []
        self.bandwidths = []
        self.intensities = []
        self.DNAspace_for_mu0 = logspace_int(100, 3000, 10)*ureg.bp  # exponential space of DNA sizes
        self.DNAspace_for_vWBRfit = np.linspace(100, 50000, 100)*ureg.bp
        self.Tvals_for_mu0 = []
        self.H2Oviscosity = None
        self.accel_to_plateau = None
        self.equil_to_accel = None
        self.Zimm_to_Rouse = None
        self.poresize = None
        self.poresize_fit = None
        self.vWBR_muS = None
        self.vWBR_muL = None
        self.vWBR_gamma = None

    def set_field(self, electrfield):
        '''At some point this will have a description...'''
        self.field = to_units(electrfield, 'V/cm', 'electrfield')

    def set_percentgel(self, percentgel):
        '''At some point this will have a description...'''
        self.percent = to_units(percentgel, '(g/(100 mL))*100', 'percentgel')

    def set_temperature(self, temperature):
        '''At some point this will have a description...'''
        self.temperature = to_units(temperature, 'K', 'temperature')

    def set_gelength(self, gel_len):
        '''At some point this will have a description...'''
        self.gel_len = to_units(gel_len, 'cm', 'gel_len')

    def set_wellx(self, wellx):
        '''At some point this will have a description...'''
        self.wellx = to_units(wellx, 'mm', 'wellx')

    def set_welly(self, welly):
        '''At some point this will have a description...'''
        self.welly = to_units(welly, 'mm', 'welly')

    def set_wellz(self, wellz):
        '''At some point this will have a description...'''
        self.wellz = to_units(wellz, 'mm', 'wellz')

    def set_wellsep(self, wellsep):
        '''At some point this will have a description...'''
        self.wellsep = to_units(wellsep, 'mm', 'wellsep')

    def set_DNAspace_for_mu0(self, DNA_space):
        '''At some point this will have a description...'''
        self.DNAspace_for_mu0 = to_units(DNA_space, 'bp', 'DNA_space')

    def set_Tvals_for_mu0(self, Tvals):
        '''At some point this will have a description...'''
        self.Tvals_for_mu0 = to_units(Tvals, '(g/(100 mL))*100', 'Tvals')

    def set_DNAspace_for_vWBRfit(self, DNA_space):
        '''At some point this will have a description...'''
        self.DNAspace_for_vWBRfit = to_units(DNA_space, 'bp', 'DNA_space')


    def run(self,
            till_len = 0.75,         # percent of gel_len
            till_time = None,        # hours
            exposure = 0.5,          # [0-1]
            geometry = 'horizontal',
            plot = True,
            res = Q_(500,'px/in'),
            cursor_ovr = dict(hover=False),
            back_col = 0.3,
            band_col = 1,
            well_col = 0.05,
            noise = 0.015,
            interpol = 'linear',     # 'cubic','nearest'
            dset_name = 'vertical',  # 'horizontal'
            replNANs = True          # replace NANs by 'nearest' interpolation
            ):
        '''
        At some point this will have a description...
        '''
        bandwidth = 2  # {0:'well_only', 1:'intrinsic_only', 2:'both'}
        Itol = 1E-5    # intensity tolerance
        FWTM = False   # bandwidth interpreted as FWTM instead of FWHM
        lanes = [sample.solutes for sample in self.samples]
        names = self.names
        field = self.field              # V/cm
        percentage = self.percent       # %agarose
        temperature = self.temperature  # K
        gel_len = self.gel_len          # cm
        wellx = self.wellx              # mm
        welly = self.welly              # mm
        wellz = self.wellz              # mm
        wellsep = self.wellsep          # mm
        volumes = self.volumes          # microliter
        quantities = self.quantities    # ng
        dataset = datasets[dset_name]
        mu_func = mu_funcs[dset_name]
        DNAspace_mu0 = self.DNAspace_for_mu0
        DNAspace_vWBRfit = self.DNAspace_for_vWBRfit
        if self.Tvals_for_mu0 == []:
            self.Tvals_for_mu0 = Q_(np.unique(dataset['T']),
                                    dataset['T'].units).to('(g/(100 mL))*100')
        else:
            self.Tvals_for_mu0 = to_units(self.Tvals_for_mu0,
                                          '(g/(100 mL))*100', 'Tvals_for_mu0')
        Tvals = self.Tvals_for_mu0
        nlanes = len(lanes)
        exposure = 0 if exposure < 0 else 1 if exposure > 1 else exposure #####
        if not hasattr(wellx.magnitude, '__iter__'):
            wellx = np.repeat(wellx, nlanes)
        wellx = wellx.to('cm')
        if not hasattr(welly.magnitude, '__iter__'):
            welly = np.repeat(welly, nlanes)
        welly = welly.to('cm')
        if wellz is not None:
            if not hasattr(wellz.magnitude, '__iter__'):
                wellz = np.repeat(wellz, nlanes)
            wellz = wellz.to('cm')
        wellsep = wellsep.to('cm')
        if volumes is not None:
        #    if not hasattr(volumes.magnitude, '__iter__'):
        #        volumes = np.repeat(volumes, nlanes)
            volumes = volumes.to('cm**3')
        till_len = abs(till_len) if till_len is not None else 1
        if till_time is not None:
            till_time = to_units(till_time, 'hr', 'till_time').to('s')
        res = to_units(res, 'px/cm', 'res')
        max_dist = till_len * gel_len

        # Electrophoretic Mobilities
        self.mobilities = []
        for lane in lanes:  ### self.mobs=[]+append  ou self.mobs=None + assign 
            lane_mobs = []
            for dna_frag in lane:
                dna_size = len(dna_frag) * ureg.bp # bp assumption ###### ! ###
                frag_mob = size_to_mobility(dna_size, field, percentage,
                                            mu_func, dataset, interpol,
                                            replNANs)
                lane_mobs.append(frag_mob)
            self.mobilities.append(lane_mobs * ureg('cm**2/V/s'))  ############
        #self.mobilities = Q_(self.mobilities, 'cm**2/V/s')
        mobilities = self.mobilities
        max_mob = max([max(lane_mobs) for lane_mobs in mobilities])

        # vWBR eq. parameters muL, muS, gamma
        output = vWBRfit(field, percentage, DNAspace_vWBRfit, dataset, mu_func,
                         interpol, replNANs, plot=False)
        muS, muL, gamma = output[0]
        muS = Q_(muS, 'cm**2/V/s')                                            #
        muL = Q_(muL, 'cm**2/V/s')                                            #
        gamma = Q_(gamma, 'bp')                                               #
        self.vWBR_muS = muS
        self.vWBR_muL = muL
        self.vWBR_gamma = gamma

        # vWBR
        #mu_func = vWBR(muS, muL, gamma)

        # Time limit
        time = runtime(max_dist, max_mob, field)  # sec
        if till_time is not None and till_time < time:
            time = till_time
        self.runtime = time
        
        # Distances
        distances = [rundistance(time, lane_mobs, field)
                     for lane_mobs in mobilities]
        self.distances = distances
        
        # Free solution mobility estimate
        mu0 = ferguson_to_mu0(field, Tvals, DNAspace_mu0, dataset, mu_func,
                              interpol, replNANs, plot=False)
        mu0 = Q_(mu0,'cm**2/V/s')  ############################################
        self.freesol_mob = mu0
        
        # Initial bandwidths
        if geometry == 'horizontal':
            dist0 = welly
        elif volumes is not None and wellz is not None: #vertical geometry
            dist0 = volumes/(wellx*wellz)
        else:
            dist0 = 0.5*welly  ### assumption #################################
        time0 = dist0/(mu0*field)
        bandwidths0 = [mobs*time0[l]*field for l, mobs in
                       enumerate(mobilities)]
        self.bandwidths0 = bandwidths0
        
        # Intrinsic diffusional bandwidths
        muS = muS.to('m**2/V/s')
        muL = muL.to('m**2/V/s')
        mu0 = mu0.to('m**2/V/s')
        lp = constants['lp'].to('m')
        l = constants['l'].to('m')
        b = constants['b'].to('m/bp')
        kB = constants['kB'].to('m**2*kg/s**2/K')
        qeff = constants['qeff'].to('A*s/bp')
        field = field.to('V/m')
        eta = H2Oviscosity(temperature)
        self.H2Oviscosity = eta
        a = pore_size(gamma, muL, mu0, lp, b)
        a_fit = pore_size_fit(percentage)  ####################################
        a_fit = a_fit.to('m')              ####################################
        self.poresize = a
        self.poresize_fit = a_fit
        epsilon = reduced_field(eta, a, mu0, field, kB, temperature)
        Db = Dblob(kB, temperature, eta, a)
        N_lim1 = accel_plateau(epsilon)    ####################################
        N_lim2 = equil_accel(epsilon)      ##   ***   Major problem    ***   ##
        N_lim3 = Zimm_Rouse(Q_(2E3,'bp'),  ####################################
                            [kB, temperature, qeff, eta, mu0, a, b, l, lp])
        #print 'N_lim1 = accel_plateau = %s (%s)' %(N_lim1,N_to_Nbp(N_lim1,a,b,l))
        #print 'N_lim2 = equil_accel = %s (%s)' %(N_lim2,N_to_Nbp(N_lim2,a,b,l))
        #print 'N_lim3 = Zimm_Rouse = %s (%s)' %(N_lim3,N_to_Nbp(N_lim3,a,b,l))
        self.accel_to_plateau = N_to_Nbp(N_lim1, a, b, l)
        self.equil_to_accel = N_to_Nbp(N_lim2, a, b, l)
        self.Zimm_to_Rouse = N_to_Nbp(N_lim3, a, b, l)
        for lane in lanes:
            lane_widths = []
            for dna_frag in lane:
                Nbp = len(dna_frag) * ureg.bp  ### assumption #################
                N = Nbp_to_N(Nbp, a, b, l)
                if N < N_lim3:
                    # Ogston-Zimm
                    L = contour_length(Nbp, b)   # (m)
                    Rg = radius_gyration(L, lp)  # (m)
                    D0 = free_solution(kB, temperature, eta, Rg)  # (m^2/s)
                    DRouse = Ogston_Rouse(Nbp, kB, temperature,
                                          a, eta, b, l)  # (m^2/s)
                    g = Zimm_g(Nbp, DRouse, qeff, mu0, kB, temperature)# to base
                    D = Ogston_Zimm(D0, g)                             # units??
                elif N < N_lim2:
                    # Rouse/Reptation-equilibrium
                    D = Db/N**2
                elif N > N_lim1:
                    # Reptation-plateau (reptation with orientation)
                    D = Db*epsilon**(3/2)
                else:
                    # Accelerated-reptation
                    D = Db*epsilon*N**(-1/2)
                frag_width = bandbroadening(D, time).to('cm')
                lane_widths.append(frag_width)
            self.bandwidthsI.append(lane_widths)
        bandwidthsI = self.bandwidthsI

        # Total bandwidths
        bandwidths = [[bandwidths0[i][j] + bandwidthsI[i][j] for j in xrange(len(lanes[i]))]
                      for i in xrange(nlanes)]
        self.bandwidths = bandwidths
        if bandwidth == 0: bandwidths = self.bandwidths0
        if bandwidth == 1: bandwidths = self.bandwidthsI
        
        # Max intensities
        raw_Is = []
        maxI = Q_(-np.inf, 'ng/cm')
        minI = Q_(np.inf, 'ng/cm')
        for i, lane in enumerate(lanes):
            lane_I = []
            for j in xrange(len(lane)):
                frag_Qty = quantities[i][j]
                frag_Wth = bandwidths[i][j]  # w=FWHM or w=FWTM ???
                if FWTM:
                    FWHM = Gauss_FWHM(frag_Wth)
                else:
                    FWHM = frag_Wth
                std_dev = Gauss_dev(FWHM)
                auc = frag_Qty  # area under curve proportional to DNA quantity
                frag_I = Gauss_hgt(auc, std_dev)  # peak height
                if frag_I > maxI:
                    maxI = frag_I
                if frag_I < minI:
                    minI = frag_I
                lane_I.append(frag_I)
            raw_Is.append(lane_I)

        # max intensity normalization
        satI = maxI+exposure*(minI-maxI)
        intensities = [[(1-back_col)/satI*fragI for fragI in lane]
                       for lane in raw_Is]
        self.intensities = intensities

        # Plot gel
        if plot:
            # Title
            mins, secs = divmod(time.to('s').magnitude, 60)  # time is in secs
            hours, mins = divmod(mins, 60)
            hours = Q_(hours, 'hr')
            mins = Q_(mins, 'min')
            secs = Q_(secs, 's')
            title = ('E = %.2f V/cm\n'
                     'C = %.1f %%\n'
                     'T = %.2f K\n'
                     't = %d h %02d m\n'
                     'expo = %.1f' %(field.to('V/cm').magnitude,
                                     percentage.magnitude,
                                     temperature.magnitude,
                                     hours.magnitude, mins.magnitude,
                                     exposure))
            # Plot
            gelpic = gelplot_imshow(distances, bandwidths, intensities, lanes,
                                    names, gel_len, wellx, welly, wellsep, res,
                                    cursor_ovr, back_col, band_col, well_col,
                                    noise, Itol, title, FWTM, False)
            return gelpic
        return None



if __name__=="__main__":
    from random import randint

    test_gel = True
    test_mu0 = True
    test_vWBRfit = True
    test_vWBRfit_comprehensive = False  # very time consuming
    test_samples = True
    check_ladders = True
    test_gen_ladder = True


    # Conditions
    electrfield  = 6.21    # V/cm
    percentgel   = 1.0     # %agarose
    temperature  = 295.15  # K

    # Gel length and geometry
    gel_len = 7.5  # cm
    geometry = 'vertical' #'horizontal'

    # Well dimensions
    wellx   = 7 #5    # mm
    welly   = 2 #1    # mm
    wellz   = 1 #3    # mm
    wellsep = 2    # mm

    # Length limit
    till_len  = 0.77

    # Time limit
    till_time = None #45/60.0

    # Exposure factor
    exposure = 0.4

    # Dataset and interpolation
    dset_name = 'vertical'
    dataset = datasets[dset_name]
    interpol  = 'linear'
    replNANs = True

    # Plot
    plot = True
    res = Q_(500, 'px/in')
    cursor_ovr = None #dict(hover=True)
    back_col = 0.33166993353685043  # 0.332  0.15 
    band_col = 1
    well_col = 0.05
    noise = 0.5*0.023400015217741609  # 0.015

    # Lane identifiers
    lanenames=['L1', 'S1', 'S2']

    # Samples
    ladder = ladder_from_info('1kb_GeneRuler')
    sample1 = Sample(randDNAseqs([561, 1302, 135, 5021]))
    sample2 = Sample(randDNAseqs([3000, 500, 1500]))
    samples = [ladder, sample1, sample2]

    # Volumes and Quantities
    volumes = 12  # microliter

    quantities = []
    #quantities.append([25, 25, 25, 60, 25, 25, 25, 70, 30, 30, 30, 70, 30, 30])
    #quantities.append([50]*4)
    #quantities.append([])
    #quantities.append(100)
    #quantities.append([120, 20, 60])
    #quantities = None

    # Data
    #DNAmin = 100
    #DNAmax = 20000
    #DNAdivs = 100
    DNAvals = np.linspace(100, 20000, 100) * ureg.bp
    DNAspace = logspace_int(100, 3000, 10) * ureg.bp
    divsE = 10
    divsT = 10
    Evals = sorted(list(set(datasets[dset_name]['E'])))  # why sorted and listed???
    minE = min(Evals)
    maxE = max(Evals)
    E_space = list(np.linspace(minE.magnitude, maxE.magnitude, divsE))*ureg(str(minE.units))
    Tvals = sorted(list(set(datasets[dset_name]['T'])))
    minT = min(Tvals)
    maxT = max(Tvals)
    T_space = list(np.linspace(minT.magnitude, maxT.magnitude, divsT))*ureg(str(minT.units))

    if test_gel:
        ### Instantiate Gel ###
        G = Gel(samples, lanenames, percentgel, electrfield, temperature,
                gel_len, wellx, welly, wellz, wellsep)

        ### Run Gel ###
        pic = G.run(till_len, till_time, exposure, geometry, plot, res,
                    cursor_ovr, back_col, band_col, well_col, noise,
                    interpol, dset_name, replNANs)
        if plot:
            pic.savefig('gelplot.jpg', dpi=300)
            pic.show()


    if test_mu0:
        ### Test <ferguson_to_mu0> ### ----------------------------------------
        print '\n'+80*'#'
        print '( Free Solution Mobility from Ferguson Plot )'.center(80, '#')
        print 80*'#'+'\n'
        plot = True
        for Ei in E_space:
            mu0 = ferguson_to_mu0(Ei, T_space, DNAspace, dataset,
                                  mu_funcs[dset_name], interpol, replNANs, plot)
            if mu0 is None: print mu0
            else: print 'mu0= %.3e cm^2/(V.seg)' %mu0


    if test_vWBRfit:
        ### Test <vWBRfit> ### ------------------------------------------------
        print '\n'+80*'#'
        print ("( Non-linear Least Squares Fitting"
               " with vWBR's Eq. )".center(80, '#'))
        print 80*'#'+'\n'
        plot = True
        output = vWBRfit(electrfield, percentgel, DNAvals,
                         datasets[dset_name], mu_funcs[dset_name],
                         interpol, replNANs, plot)
        #print output


    if test_vWBRfit_comprehensive:
        ### Test <vWBRfit comprehensively> ### --------------------------------
        print '\n'+80*'#'
        print ("( Non-linear Least Squares Fitting with vWBR's Eq."
               "- comprehensive )".center(80, '#'))
        print 80*'#'+'\n'
        for Ei in E_space:
            for Ti in T_space:
                output = vWBRfit(Ei, Ti, DNAvals,
                                 dataset=datasets[dset_name],
                                 mu_func=mu_funcs[dset_name],
                                 method=interpol, replNANs=replNANs, plot=plot)


    if test_samples:
        ## Test Sample class ### ----------------------------------------------
        print '\n'+80*'#'
        print '( Sample Class Demonstration )'.center(80, '#')
        print 80*'#'+'\n'
        dseqs1 = randDNAseqs([500, 1000, 5000])
        qts1 = lindivQ(dseqs1, 200)
        dseqs2 = randDNAseqs([3000, 1500])
        qts2 = lindivQ(dseqs2, 150)
        s1 = Sample(dseqs1, qts1, 20)
        s2 = Sample(['dna1','dna2','dna3'], qts1, 20)
        s3 = Sample(dseqs2, qts2)
        s4 = Sample()
        print ' Sample representation '.center(80, '#')
        print repr(s1)
        print s1
        print repr(s2)
        print s2
        print repr(s3)
        print s3
        print repr(s4)
        print s4
        print ' Sample mixing (addition) '.center(80, '#')
        s14 = s1 + s4
        s41 = s4 + s1
        print "s1 + s4:", repr(s14)
        print "s4 + s1:", repr(s41)
        print ' Sample duplicate and aliquot '.center(80, '#')
        s1d = s1.duplicate()
        s5 = s1d.aliquot(15)
        print repr(s1)
        print s1
        print repr(s5)
        print s5
        print repr(s1d)
        print s1d
        print ' Sample divide '.center(80, '#')
        s1d = s1.duplicate()
        print repr(s1d)
        print s1d
        r = s1d.divide(3)
        for s in r: print repr(s)
        print repr(s1d)
        print s1d
        print ' Sample stocksolution (endless) and aliquot '.center(80, '#')
        S1 = s1.stocksolution()
        s6 = S1.aliquot(50)
        print repr(S1)
        print S1
        print repr(s6)
        print s6
        print ' Sample concentrations '.center(80, '#')
        print s1
        print s1.concentrations()
        print s1.concentration(solute=s1.solutes[1])
        print s1.concentrations()[1]
        print s1.concentration(1)
        print ' Sample dilution (in place) '.center(80, '#')
        s1d = s1.duplicate()
        print s1d
        s1d.dilute(finalCon=0.35, solute=s1.solutes[0])
        print s1d
        s1d = s1.duplicate()
        print s1d
        s1d.dilute(finalCon=s1d.concentration(1)*0.01, index=1)
        print s1d
        s1d = s1.duplicate()
        print s1d
        s1d.dilute(0.1)
        print s1d
        s1d = s1.duplicate()
        print s1d
        s1d.dilute(finalVol=50)
        print s1d
        print ' Dilution used to concentrate sample (in place) '.center(80, '#')
        s1d = s1.duplicate()
        print s1d
        s1d.dilute(finalCon=35, solute=s1.solutes[0])
        print s1d
        s1d = s1.duplicate()
        print s1d
        s1d.dilute(10)
        print s1d
        s1d = s1.duplicate()
        print s1d
        s1d.dilute(finalVol=10)
        print s1d
        print ' Add solute (in place) '.center(80, '#')
        s1d = s1.duplicate()
        sol = s1.solutes[1]
        solQ = Q_(10, 'ng')
        print s1d
        s1d.add_solute(sol, solQ)
        print s1d
        s1d = s1.duplicate()
        sol = s3.solutes[0]
        solQ = Q_(10, 'ng')
        print s1d
        s1d.add_solute(sol, solQ)
        print s1d

    if check_ladders:
        ### Verify and print ladders info ### ---------------------------------
        print '\n'+80*'#'
        print '( DNA Ladder Info )'.center(80, '#')
        print 80*'#'
        for k in ladders:
            sizes = ladders[k]['sizes']
            fracs = ladders[k]['percent']
            total = Q_(0.5, 'ug')
            masses = total * fracs
            assert len(sizes) == len(fracs), 'ladder: %s, len(sizes) != len(percent)' %k
            assert round(sum(fracs), 5) == 1, 'ladder: %s, sum(percent) != 1' %k
            print '\n', k, '\n', '-'*80
            print 'size \t\t mass/%s \t fraction' % total
            print '-'*80
            for i in xrange(len(sizes)):
                print sizes[i], '  \t ', masses[i], ' \t ', fracs[i]
            print '-'*80

    if test_gen_ladder:
        ### Generate ladder (Sample) from ladder info ### ---------------------
        print '\n'+80*'#'
        print '( Sample From DNA Ladder Info )'.center(80, '#')
        print 80*'#'+'\n'
        print "ladder_from_info('1kb_GeneRuler')"
        l1 = ladder_from_info('1kb_GeneRuler')
        print repr(l1)
        print l1
        print "\nladder_from_info('1kb_GeneRuler', 1000)"
        l2 = ladder_from_info('1kb_GeneRuler', 1000)
        print repr(l2)
        print l2
        print "\nladder_from_info('1kb_GeneRuler', 1000, 24)"
        l3 = ladder_from_info('1kb_GeneRuler', 1000, 24)
        print repr(l3)
        print l3
        



# References (very incomplete)
#=============================================================================#
# 1. Van Winkle, D.H., Beheshti, A., Rill, R.L.: DNA electrophoresis in       #
# agarose gels: A simple relation describing the length dependence of         #
# mobility. ELECTROPHORESIS 23(1), 15–19 (2002)                               #
#                                                                             #
# 2. Rill, R.L., Beheshti, A., Van Winkle, D.H.: DNA electrophoresis in       #
# agarose gels: Effects of field and gel concentration on the exponential     #
# dependence of reciprocal mobility on DNA length. ELECTROPHORESIS 23(16),    #
# 2710–2719 (2002)                                                            #
#                                                                             #
# 3. Beheshti, A.: DNA Electrophoresis in th Agarose Gels: A New Mobility vs. #
# DNA Length Dependence. Electronic Theses, Treatises and Dissertations       #
# (Paper 1207)(2002)                                                          #
#=============================================================================#

# Bugs
#=============================================================================#
# - Error when zooming and hovering cursor.                                   #
# - Imperfect conversion from array to image!?                                #
#   While in the array the band broadness didn't vary more than one "pixel",  #
#   in the plot the difference was greater and more  noticeable.              #
#       ? imshow options ?                                                    #
#       ? Resolution ?                                                        #
#       ? Only in "show" not in "save" ?                                      #
#       ? Interference of other plot parameters ?                             #
# - The hoovering mode of the datacursor is slow.                             #
# - Error when till_length is 1: IndexError: index 3150 is out of bounds for  #
#   axis 0 with size 3150                                                     #
#=============================================================================#

# Questions for Professor Björn
#=============================================================================#
# - Ask for guidance for the simple SAMPLE objects and basic operations.      #
# - Ask for guidance for the default values.                                  #
# - Ask for guidance for the user friendliness from the standpoint of a       #
#   researcher.                                                               #
# - Would an "excise band" method be useful?                                  #
#=============================================================================#

# To-do list
#=============================================================================#
# - Band convolution (https://en.wikipedia.org/wiki/Convolution);             #
# - Qualitative and quantitative validation;                                  #
# - Comparison with other softwares;                                          #
# - Gather more data (obtained at well controlled conditions);                #
#       + Professor Beheshti's Phd thesis                                     #
#       + Extend the dataset with new experimental data                       #
# - Study extrapolation options beyond the data range:                        #
#       + parameters dependence on gel concentration equations (at low field) #
# - Train and validate a regression predictive model;                         #
# - Interpolation of user's experimental data with vWBR equation;             #
#-----------------------------------------------------------------------------#
# - Documentation (Numpy style);                                              #
# - Code readability and conformity to standards and style guides;            #
# - User friendliness;                                                        #
# - Testing module;                                                           #
# - Sharing on GitHub;                                                        #
# - Integration with pydna;                                                   #
# - Application exemples and guide in IPython Notebook;                       #
# - <mu_func> as module variable??                                            #
# - self.runtime = np.nan??                                                   #
# - Data and mu_funcs as module variables or class variables??                #
# - Keep most values in numpy arrays?? (may be helpful to implement units)    #
# - Experimental conditions on the plot's title;                              #
# - Keep and return the plots objects;                                        #
# - Passing the matplotlib's **keyargs;                                       #
# - Additional plots;                                                         #
# - Variable mapping:                                                         #
#       {'var':'meaning'}{'var':'units'}                                      #
#       {'E':'Electric field intensity (V/cm)', ...}                          #
# - Internal objects to organize information (LANE, BAND, SAMPLE);            #
# - Simple SAMPLE object:                                                     #
#       + concentration per DNA fragment                                      #
#       + total volume                                                        #
#       + sample operations                                                   #
#       + absolute/relative quantities                                        #
# - Recognize unequivocal initials: 'v':'vertical', 'h':'horizontal', etc.;   #
# - There should be a single (Pint) UnitRegistry for the entire project.      #
# - Show DNA size in matplotlib coordinate viewer:                            #
#       "http://stackoverflow.com/questions/14754931/matplotlib-values-under- #
#        cursor"                                                              #
# - Click band to print DNA fragment data in console;                         #
# - Defaults, Assertions, warnings, errors, etc.                              #
# - Assert dimension concordance:                                             #
#       if wellx is iterable: len(wellx) == len(lanes)                        #
# - Combine gels;                                                             #
# - Mosaic of gels: same samples, different conditions;                       #
# - Method <save_with_resolution>;                                            #
# - Attention to pixel [0], in pixel->cm / cm->pixel conversions;             #
# - Study more carefully the distance <-> pixel conversion;                   #
# - Volumes are being used to estimate the initial bandwidths but are not     #
#   related to the quantity of DNA, since that is taken as input              #
#   independently. Perhaps it would be more user friendly to input volumes    #
#   and concentrations, and not volumes and quantities.                       #
# - At this point, the "exposure time" is being optimized so that no band's   #
#   intensity saturates (reaches white color) before it's peak. All curves    #
#   are perfect Gaussians. This benefites the highest curves in detriment of  #
#   the wider ones. It may be better for visualization to allow saturation    #
#   basing the "exposure time" on a parameter, maximizing the average hight   #
#   band or assuring that no peak falls bellow a certain level.               #
# - There is pehaps a wiser way to perform peak convolution.                  #
# - The stoping condition for the evaluation of the intensity function is too #
#   strick. "color <= background" goes till the order of 1E-16. A toletance   #
#   is needed.                                                                #
# - Peak convolution in the perpendicular direction.                          #
# - premade Ladder addition.                                                  #
# - Dimension concordance, data type and missing values verification on input.#
# - Full spell check.                                                         #
# - Most assert statements must be replaced with proper errors.               #
#=============================================================================#

# Random notes
#=============================================================================#
# - Avoid integer division: from __future__ import division                   #
# - Careful: Operations with unitary numpy arrays return numeric data types:  #
#       + type(np.array(2)*np.array(2)) --> <'numpy.int32'>                   #
#       + type(np.array(2)*np.array(2)/np.array(5)) --> <'numpy.int32'>       #
#       + from __future__ import division                                     #
#         type(np.array(2)*np.array(2)/np.array(5)) --> <'numpy.float64'>     #
#       + np.asarray(np.array(2)*np.array(2)/np.array(5)) --> array(0.8)      #
# - The pore size in the diffusion coefficient equations might not be an      #
#   "effective" pore size as that defined by Slater as function of muL, mu0   #
#   and gamma. Note that Viovy defined the interval 200-500 nm as the         #
#   consensus regarding pore size in 1% agarose gel. Yet, using Slater's      #
#   method we arrive at an effective pore size of 135.4 nm.                   #
# - I'm getting a smaller free solution mobility than the muS parameter.      #
#   I think it should be the other way around!...                             #
# - Is it better to never have unused lanes (as it is now) or to build a gel  #
#   with a chosen dimension and number of wells (used or not)?                #
# - The one thing that causes troubles with quantities is to assign a         #
#   quantity to a list of quantities. Ex: Q_([Q_(1, 'nm')], 'nm')             #
#   With that in mind, there might be simpler ways to implement the           #
#   functionality of "to_units".                                              #
# - mpldatacursor use:                                                        #
#       + right-click on annotation box to hide it;                           #
#       + press "d" on the keyboard to hide all annotation boxes;             #
#       + press "t" (toogle) to disable or re-enable interactive datacursors. #
#=============================================================================#
