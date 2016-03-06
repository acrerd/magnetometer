from __future__ import division

import sys
import numpy as np
import matplotlib.pyplot as plt

data = np.genfromtxt(sys.argv[1], delimiter=' ')

plt.plot(data[:, 0] / (60*60*1000), data[:, int(sys.argv[2])])
plt.xlabel('Time since midnight [h]')
plt.ylabel('Field [nT]')
plt.legend(['East-West', 'North-South', 'Up-Down'])
plt.show()