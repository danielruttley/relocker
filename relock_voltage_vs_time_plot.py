# -*- coding: utf-8 -*-
"""
Created on Mon Mar 29 09:53:33 2021

@author: Dan
"""


import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter
import numpy as np
import pandas as pd
import datetime

plt.style.use(r'Z:\Tweezer\People\Dan\code\dan.mplstyle')
output_to_mhz = 2157/10 #using measured 2.157GHz/V and then dividing by 10 due to IO board

df = pd.read_csv(r"Z:\Tweezer\People\Dan\code\RedPitaya autorelockbox\logs\D1 ECDL\2021\03\26\173829.csv")
unlocked_df = pd.read_csv(r"Z:\Tweezer\People\Dan\code\RedPitaya autorelockbox\logs\D1 ECDL\2021\03\26\173829_unlocked.csv")
df['datetimes'] = pd.to_datetime(df['datetime'], format='%Y%m%d%H%M%S')
unlocked_df['datetimes'] = pd.to_datetime(unlocked_df['datetime'], format='%Y%m%d%H%M%S')
plt.scatter(df['datetimes'],df['mean output voltage [V]'],alpha=0.8,label='locked')
plt.scatter(unlocked_df['datetimes'],unlocked_df['mean output voltage [V]'],alpha=0.8,label='unlocked')
merged_df = df.append(unlocked_df)
merged_df.set_index('datetimes',inplace=True)
merged_df.sort_index(inplace=True)
plt.plot(merged_df.index,merged_df['relock voltage [V]'],alpha=0.8,label='relocking voltage',color='#00AEEF')
plt.xlim([datetime.datetime(2021,3,26,20,10), datetime.datetime(2021,3,26,20,20)])
plt.gca().xaxis.set_major_formatter(DateFormatter("%H:%M"))
#plt.gcf().autofmt_xdate()
plt.xlabel('time')
plt.ylabel('RedPitaya output voltage [V]')
plt.legend(loc='lower right')
ax = plt.gca()
ax.yaxis.set_ticks_position('left')
#ax.set_axisbelow(True)
#ax.xaxis.grid()
#ax.yaxis.grid()
secax = ax.secondary_yaxis('right', functions=(lambda x: x*output_to_mhz,
                                                lambda x: x/output_to_mhz))
secax.set_ylabel('transition drift [MHz]')
plt.title('relocker voltage output 26/03/2021')

plt.show()