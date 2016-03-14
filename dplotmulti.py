from __future__ import division

import sys
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.dates import DayLocator, DateFormatter
import time
import datetime

def get_data(path):
    return np.genfromtxt(path, delimiter=' ')

# empty data with 5 columns
data = np.empty((0, 5))

for day in range(8, 14):
    day_str = "2016-03-{0:02d}".format(day)
    
    data_today = get_data("data/2016/03/{0}.txt".format(day_str))
    
    # add timestamp to each day
    data_today[:, 0] += 1000*time.mktime(datetime.datetime.strptime(day_str, "%Y-%m-%d").timetuple())
    
    data = np.append(data, data_today, axis=0)

# plot date
plt.plot_date([datetime.datetime.fromtimestamp(t / 1000) for t in data[:, 0]], data[:, int(sys.argv[1])], ms=0.1)
plt.xlabel('Time since midnight [h]')
plt.ylabel('Field [nT]')
plt.legend(['East-West', 'North-South', 'Up-Down'])
plt.show()