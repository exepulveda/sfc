'''
This script perform WFC and SWFC for many clusters and calculate DB and Silhouette indices
'''

import sys
import collections
import sys
import random

sys.path += ['..']

import clusteringlib as cl
import numpy as np
import scipy.stats

import clustering_ga

from scipy.spatial.distance import pdist
from sklearn.cluster import KMeans
from cluster_utils import fix_weights

from graph_labeling import graph_cut, make_neighbourhood
from scipy.spatial import cKDTree

CHECK_VALID = False

from case_study_bm import attributes,setup_case_study_ore,setup_case_study_all,setup_distances

if __name__ == "__main__":
    locations,data,min_values,max_values,scale,var_types,categories = setup_case_study_ore(a=0.999)
    N,ND = data.shape

    print(N,ND)
    #print(min_values)
    #print(max_values)
    #print(scale)

    seed = 1634120

    #if args.target:
    #    targets = np.asfortranarray(np.percentile(values[:,-1], [25,50,75]),dtype=np.float32)
    #    var_types[-1] = 2
    
    m = 2.0
    verbose=0
    lambda_value = 0.25
    
    filename_template = "../results/bm_{tag}_wfc_{nc}.csv"

    ngen=200
    npop=200
    cxpb=0.8
    mutpb=0.4
    stop_after=40

    targets = np.asfortranarray(np.percentile(data[:,-1], [15,50,85]),dtype=np.float32)
    var_types[-1] = 2

    force = (ND-1,0.15) #weight to target 15%

    knn = 15
    kdtree = cKDTree(locations)
    neighbourhood,distances = make_neighbourhood(kdtree,locations,knn,max_distance=2.0)
    distances = np.array(distances)


    for NC in range(2,11):
        np.random.seed(seed)
        random.seed(seed)
        cl.utils.set_seed(seed)
        
        setup_distances(scale,var_types,use_cat=True,targets=targets)

        #initial centroids
        kmeans_method = KMeans(n_clusters=NC,random_state=seed)
        kmeans_method.fit(data)
        
        current_centroids = np.asfortranarray(np.empty((NC,ND)))
        current_centroids[:,:] = kmeans_method.cluster_centers_

        #initial weights are uniform
        weights = np.asfortranarray(np.ones((NC,ND),dtype=np.float32)/ ND)
        
        #if args.target:
        #    for c in range(NC):
        #        weights[c,:] = fix_weights(weights[c,:],force=force)
                
        for k in range(20):
            best_centroids,best_u,best_energy_centroids,best_jm,current_temperature,evals = clustering_ga.optimize_centroids(
                    data,
                    current_centroids,
                    weights,
                    m,
                    lambda_value,
                    var_types,
                    {},
                    ngen=ngen,npop=npop,cxpb=cxpb,mutpb=mutpb,stop_after=stop_after,
                    min_values = min_values,
                    max_values = max_values,
                    verbose=verbose)

            #print("centroids",best_centroids,best_energy_centroids,"jm",best_jm)
                    
                    
            u = best_u
            N,NC = u.shape
            
            clusters = np.argmax(u,axis=1)
            
            centroids = best_centroids.copy()
            
            #print("centroids",centroids)
            #print("u",u)
            #counter = collections.Counter(clusters)
            #print("number of clusters: ",counter.most_common())

            best_weights,best_u,best_energy_weights,evals = clustering_ga.optimize_weights(
                    data,
                    centroids,
                    weights,
                    m,
                    lambda_value,
                    ngen=ngen,npop=npop,cxpb=cxpb,mutpb=mutpb,stop_after=stop_after,
                    force=force,
                    verbose=verbose)

            clusters = np.argmax(best_u,axis=1)

            weights = best_weights.copy()

            current_centroids = best_centroids.copy()
            #print(lambda_value,k,best_energy_centroids,best_energy_weights,"jm",best_jm)

            print('iteration',k,best_energy_centroids,best_energy_weights)

            #save data
            new_data = np.c_[locations,clusters]
            
            
            np.savetxt(filename_template.format(tag='clusters',nc=NC),new_data,delimiter=",",fmt="%.4f")
            np.savetxt(filename_template.format(tag='centroids',nc=NC),current_centroids,delimiter=",",fmt="%.4f")
            np.savetxt(filename_template.format(tag='u',nc=NC),best_u,delimiter=",",fmt="%.4f")
            np.savetxt(filename_template.format(tag='weights',nc=NC),best_weights,delimiter=",",fmt="%.4f")
            
            if abs(best_energy_centroids - best_energy_weights) < 1e-2:
                break


        centroid = np.asfortranarray(best_centroids,dtype=np.float32)
        weights = np.asfortranarray(best_weights,dtype=np.float32)
        clusters = np.asfortranarray(clusters,dtype=np.int8)
        
        ret_fc = cl.clustering.dbi_index(centroid,data,clusters,weights)
        ret_sill= cl.clustering.silhouette_index(data,clusters,weights)
        
        print("WFC: DB,Sil:",NC,ret_fc,ret_sill,sep=',')

        #Spatial correction
        clusters_graph = np.int32(graph_cut(locations,neighbourhood,best_u,unary_constant=70.0,smooth_constant=15.0,verbose=0))
        centroids_F = np.asfortranarray(np.empty((NC,ND)),dtype=np.float32)
        
        #calculate centroids back 
        for k in range(NC):
            indices = np.where(clusters_graph == k)[0]
            centroids_F[k,:] = np.mean(data[indices,:],axis=0)
        
        clusters = np.asfortranarray(clusters_graph,dtype=np.int8)
        ret_swfc_dbi = cl.clustering.dbi_index(centroids_F,data,clusters,weights)
        ret_swfc_sill= cl.clustering.silhouette_index(data,clusters,weights)
        print("SWFC: DB,Sil:",NC,ret_swfc_dbi,ret_swfc_sill,sep=',')
        
        cl.distances.reset()
        
        
