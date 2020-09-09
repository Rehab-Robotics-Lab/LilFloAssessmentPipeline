#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Aug 14 18:24:36 2020

@author: gsuveer
"""

import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits import mplot3d

file_data_path= "test_data/sample.xyz"
point_cloud= np.loadtxt(file_data_path,skiprows=1)
mean_Z=np.mean(point_cloud,axis=0)[2]
spatial_query=point_cloud[abs( point_cloud[:,2]-mean_Z)<1]
xyz=spatial_query[:,:3]
rgb=spatial_query[:,3:]
ax = plt.axes(projection='3d')
ax.scatter(xyz[:,0], xyz[:,1], xyz[:,2], c = rgb/255, s=0.01)
plt.show()

from scipy.spatial import ConvexHull, convex_hull_plot_2d
hull = ConvexHull(xyz)

print(hull.good)
print(hull.volume)

idx = hull.vertices
print(xyz.shape)
print(rgb.shape)
ax = plt.axes(projection='3d')
ax.scatter(xyz[idx,0], xyz[idx,1], xyz[idx,2], c = rgb[idx]/255, s=0.01)
plt.show()