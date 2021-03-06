# -*- coding: utf-8 -*-
"""
Functions for bowtie and filter computations.
Tensorflow version.

Functions
-----------
        color_1pixel_on_block    :  returns a block with central pixel to one and others to zero
        color_1pixel_on_wavelet  :  returns wavelet coefficients where only one pixel is put to one 
        from_pixel_to_bowtie     :  computes the filters of the convolutional kernel (cf fig.4 of article)
        creation_dict_bowties    :  gathers all the convolutional filters in a dictionary
        initialize_filters_F     :  initialises the filters to be learnt for the Filter-based implementation
        initialize_filters_O     :  initialises the filters to be learnt for the Operator-based implementation
        separate_dict_hole_NN    :  separates filters to be learnt from fixed filters for the Filter-based implementation            
        initialise_parameters    :  initialises all the parameters to be trained 
        restore_parameters       :  restores the parameters of a trained model.
@author: Mathilde Galinier
@date: 29/09/2020
"""
import numpy as np
import pywt
from skimage.transform import radon, iradon

import tensorflow as tf

def color_1pixel_on_block(size_block):
    """
    Returns a block with central pixel to one and others to zero
    Parameters
    -----------
       size_block (int)       : dimension of the block (multiple of 2)
    Returns
    -----------        
       block_pix(numpy array) : block with central pixel to one and others to zero, shape size_block*size_block 
    """
    block_pix = np.zeros((size_block,size_block))
    half_block = int(size_block/2)
    block_pix[half_block,half_block] = 1
    return block_pix
 
def color_1pixel_on_wavelet(size_image, level, position):
   """
   Returns wavelet coefficients where only the central pixel of one subband is set to one 
   Parameters
   -----------
      size_image (int)   : object dimension (multiple of 2)
      level (int)        : level (or scale) of the wavelet subband where the central pixel is to be set to one
      position (string)  : 'h', 'v', 'd', 'l' depending on the kind of wavelet subband 
                            where the pixel is to be set to one    
   Returns
   -----------        
      im_pix(numpy array): wavelet coefficients where only one pixel is put to one (placed at the center 
                           of the block defined by 'position' and 'level'), size size_image*size_image 
   """    
   if size_image % 2 > 0 :
       raise Exception('size_image should be a multiple of 2.' + \
                       'The value of size_image was : {}'.format(size_image))
   if level < 0:
       raise Exception('level should be positive.')
   elif level ==0:
       im_pix = color_1pixel_on_block(size_image)
   else:    
       im_pix = np.zeros((size_image,size_image))
    
       size_4blocks = int(size_image/(2.**(level-1))) 
       size_block = int(size_4blocks/2.)
       indices_aux = np.linspace(0,size_block-1,size_block).astype(int)
       
       if position == 'h':
           indices_pos_x = indices_aux
           indices_pos_y = indices_aux + size_block 
       elif position == 'v':    
           indices_pos_x = indices_aux + size_block  
           indices_pos_y = indices_aux 
       elif position == 'd':    
           indices_pos_x = indices_aux + size_block 
           indices_pos_y = indices_aux + size_block  
       elif position == 'l':
           indices_pos_x = indices_aux
           indices_pos_y = indices_aux
       
       im_pix[indices_pos_x[0]:indices_pos_x[-1]+1, \
              indices_pos_y[0]:indices_pos_y[-1]+1] = color_1pixel_on_block(size_block)
   
   return im_pix

def from_pixel_to_bowtie(size_image, level_pix, position_pix, angles, level_decomp, wavelet_type):
    """
    Computes the filters of the convolutional kernel as shown on fig.4 of article
    Parameters
    -----------
      size_image (int)          : object dimension (multiple of 2)
      level_pix (int)           : level (or scale) of the wavelet subband where the central pixel is to be set to one
      position_pix(string)      : 'h', 'v', 'd', 'l' depending on the kind of wavelet subband 
                                  where the pixel is to be set to one   
      angles(numpy array)       : angles of the 'seen' projections
      level_decomp (int)        : number of wavelet scales (J-J0-1 in the article)      
      wavelet_type (string)     : type of wavelets                 
    Returns
    -----------        
       wave_bowtie_coeffs(list) : bowtie-shaped filters (generated by back-projection transform
                                  applied to one colored pixel
    """    
    # Color on pixel in the wavelet domain
    wave_1pix = color_1pixel_on_wavelet(size_image, level_pix, position_pix)
    _, coeff_slices = pywt.coeffs_to_array(pywt.wavedecn(np.zeros((size_image,size_image)), wavelet_type, \
                                                        mode='periodization', level=level_decomp))
    
    # Convert it into the spatial domain
    coeffs_from_arr = pywt.array_to_coeffs(wave_1pix, coeff_slices)
    im_1pix = pywt.waverecn(coeffs_from_arr, wavelet=wavelet_type, mode = 'periodization')
    
    # Compute the back projection
    radon_im = radon(im_1pix, theta=angles, circle=False)
    BP_im = iradon(radon_im, theta=angles, circle=False, filter=None)
    
    # Convert it into the wavelet domain
    wave_bowtie_coeffs = pywt.wavedec2(BP_im, wavelet_type, mode='periodization', level=level_decomp)
    #wave_bowtie, _ = pywt.coeffs_to_array(wave_bowtie_coeffs)
    
    return wave_bowtie_coeffs

def creation_dict_bowties(size_image, level_decomp, angles, wavelet_type):
    """
    Gathers all the convolutional filters in a dictionary.
    Parameters
    -----------
      size_image (int)          : object dimension (multiple of 2)
      level_decomp (int)        : number of wavelet scales (J-J0-1 in the article)    
      angles(numpy array)       : angles of the 'seen' projections
      wavelet_type (string)     : type of wavelets   
    Returns
    -----------        
       dict_bowties (dict)      : dictionary containing all the filters of the convolutional kernel 
    """  
    if size_image % 2 > 0 :
       raise Exception('size_image should be a multiple of 2.' + \
                       'The value of size_image was : {}'.format(size_image))    
    dict_bowties = {}

    if level_decomp == 0:
       wave_bowtie_coeffs = from_pixel_to_bowtie(size_image*2, 0, 0, angles, 0, wavelet_type)  
       bowtie_block = np.flip(np.flip(wave_bowtie_coeffs[0],axis=0),axis=1)
       dict_bowties['F_0_0_0']  = bowtie_block[:,:,np.newaxis,np.newaxis]    
    else:
        for level_pix in range(1,level_decomp+1):
            for position_pix in ['l','v','d','h']:
                if level_pix < level_decomp and position_pix == 'l':
                    continue
                else:
                    key_pix = str(level_pix)+ '_' + position_pix
                    
                    wave_bowtie_coeffs = from_pixel_to_bowtie(size_image*2, level_pix,\
                                                                position_pix, angles, level_decomp, wavelet_type)  
                    for level_filt in range(1,level_decomp+1):
                        for p,position_filt in enumerate(['v','h','d','l']):
                            key = key_pix + '_' + str(level_filt)+'_'+position_filt
                            if level_filt < level_decomp and position_filt == 'l':
                                continue
                            elif level_filt == level_decomp and position_filt == 'l':
                               bowtie_block = np.flip(np.flip(wave_bowtie_coeffs[0],axis=0),axis=1)
                               dict_bowties['F_'+ key] = bowtie_block[:,:,np.newaxis,np.newaxis] 
                            else:
                               bowtie_block = np.flip(np.flip(wave_bowtie_coeffs[level_decomp-level_filt+1][p],axis=0),axis=1)
                               dict_bowties['F_'+ key] = bowtie_block[:,:,np.newaxis,np.newaxis]  
         
    return dict_bowties

def initialize_filters_F(bowtie_dict, num_dict, to_be_learnt, np_prec, tf_prec):
    """
    Initialises the filters to be learnt for the Filter-based implementation
    Parameters
    -----------
        dict_bowties (dict)       : dictionary containing all the filters of the convolutional kernel 
        num_dict (int)            : number identifying the dictionary (i.e. number of the block in the unrolled algorithm)
        to_be_learnt (int)        : 0 if parameters are fixed, 1 if the are to be learnt during the training
        np_prec(type)             : numpy type corresponding to the desired machine precision    
        tf_prec(tensorflow.dtype) : tensorflow type corresponding to the desired machine precision      
    Returns
    -----------        
        dict_filters (dict)       : dictionary containing the convolutional filters (tensorflow variables)
    """
    dict_filters = {}
    for key in bowtie_dict.keys():
        dict_filters[key] = tf.get_variable('D_'+str(num_dict)+'_'+key, dtype = tf_prec,\
                                            initializer = np_prec(bowtie_dict[key]), trainable = to_be_learnt) 
        
    return dict_filters

def initialize_filters_O(filter_size, level_decomp, num_dict, tf_prec=tf.float32):
    """
    Initialises the filters to be learnt for the Operator-based implementation
    Parameters
    -----------
        filter_size (int)         : size of each trainable filter
        level_decomp (int)        : number of wavelet scales (J-J0-1 in the article)  
        num_dict (int)            : number identifying the dictionary (i.e. number of the block in the unrolled algorithm)
        tf_prec(tensorflow.dtype) : tensorflow type corresponding to the desired machine precision      
    Returns
    -----------        
        dict_filters (dict)      : dictionary containing the convolutional filters (tensorflow variables)
    """    
    compteur = 0
    dict_filters = {}
    for level_pix in range(1,level_decomp+1):
        for position_pix in ['h', 'd', 'v', 'l']:
            if level_pix < level_decomp and position_pix == 'l':
                continue
            else:
                for level_filt in range(1,level_decomp+1):
                    for position_filt in ['h', 'd', 'v', 'l']:
                        if level_filt < level_decomp and position_filt == 'l':
                            continue
                        else:
                            key = 'F_'+ str(level_pix)+'_'+position_pix + '_' + str(level_filt)+'_'+position_filt
                            dict_filters[key] = tf.get_variable('D_'+str(num_dict)+'_' + key,\
                                                shape = [filter_size,filter_size,1,1],\
                                                dtype =tf_prec,\
                                                initializer = tf.contrib.layers.xavier_initializer(seed = compteur),\
                                                trainable = True)
                            compteur += 1 
    return dict_filters

def separate_dict_hole_NN(complete_dict, level_decomp, filter_size):
    """
    Separates filters to be learnt from fixed filters for the Filter-based implementation (cf fig.8 of article)          
    Parameters
    -----------
        complete_dict (dict)      : dictionary containing the complete bowtie filters 
        level_decomp (int)        : number of wavelet scales (J-J0-1 in the article)  
        filter_size (int)         : size of each trainable filter
    Returns
    -----------        
        dict_hole (dict)          : dictionary containing the bowtie filters with zero coefficients at the center
        dict_center_shrink (dict) : dictionary containing the center of the bowtie filters.
    """
    dict_hole = {}
    dict_center = {}
    for level_pix in range(1,level_decomp+1):
        for position_pix in ['h', 'd', 'v', 'l']:
            if level_pix < level_decomp and position_pix == 'l':
                continue
            else:
                for level_filt in range(1,level_decomp+1):
                    for position_filt in ['h', 'd', 'v', 'l']:
                        if level_filt < level_decomp and position_filt == 'l':
                            continue
                        else:
                            key = 'F_'+ str(level_pix)+'_'+position_pix + '_' + str(level_filt)+'_'+position_filt
                            size_complete_filter = complete_dict[key].shape[0]
                            absc_av = (size_complete_filter - filter_size)//2
                            absc_ap = (size_complete_filter + filter_size)//2
                            dict_hole[key] =  np.zeros((size_complete_filter,size_complete_filter,1,1))
                            dict_hole[key][:absc_av,:,:,:] = complete_dict[key][:absc_av,:,:,:] 
                            dict_hole[key][:,:absc_av,:,:] = complete_dict[key][:,:absc_av,:,:] 
                            dict_hole[key][absc_ap:,:,:,:] = complete_dict[key][absc_ap:,:,:,:] 
                            dict_hole[key][:,absc_ap:,:,:] = complete_dict[key][:,absc_ap:,:,:]
                            dict_center[key] =  complete_dict[key][absc_av:absc_ap,absc_av:absc_ap]
    return dict_hole, dict_center

def initialise_parameters(filter_size, mu, L, nb_unrolledBlocks, model_unrolling, \
                        size_image, angles, level_decomp, tf_prec, np_prec, wavelet_type):
    """
    Initialises all the parameters to be trained. 
    Parameters
    -----------
        filter_size (int)         : size of each trainable filter
        mu (float)                : standard ISTA regularisation parameter
        L (float)                 : standard ISTA constant
        nb_unrolledBlocks (int)   : number of different set of trainable parameters 
        model_unrolling (string)  : name of the version of PsiDONet used to train/test the model
                                    ('PSIDONetO', 'PSIDONetOplus', 'PSIDONetF' or 'PSIDONetFplus')    
        size_image (int)          : image dimension (multiple of 2)
        angles(numpy array)       : angles of the 'seen' projections
        level_decomp (int)        : number of wavelet scales (J-J0-1 in the article)      
        np_prec(type)             : numpy type corresponding to the desired machine precision    
        tf_prec(tensorflow.dtype) : tensorflow type corresponding to the desired machine precision  
        wavelet_type (string)     : type of wavelets
    Returns
    -----------        
       dictionaries_tf(list)      : list of trainable dictionaries (tensorflow variables) 
       thetas_tf(list)            : list of trainable theta parameters (tensorflow variables) 
       alphas_tf(list)            : list of trainable alpha parameters (tensorflow variables) 
       betas_tf(list)             : list of trainable beta parameters (tensorflow variables) 
    """    
    dictionaries_tf = []
    thetas_tf = []
    alphas_tf = []
    betas_tf = []

    if "plus" in model_unrolling:
        init_theta= np.log10(mu/L)
    else:
        init_theta= mu/L

    if "F" in model_unrolling:
        init_beta= 1
    else:
        init_beta= 0
        
    for i in range(1,nb_unrolledBlocks+1):
        if 'F' in model_unrolling: # for Filter-based implementation
            # Creation of the bowties to initialize the fixed filters
            dict_filters = creation_dict_bowties(size_image, level_decomp, angles, wavelet_type)
            # Separation between the fixed operator (border of the filters) and the learnt operator (center of the filters)
            _, dict_centers = separate_dict_hole_NN(dict_filters,level_decomp,filter_size)
            dict_filters_i = initialize_filters_F(dict_centers, i, True, np_prec, tf_prec) 
        else: # for Operator-based implementation
            dict_filters_i = initialize_filters_O(filter_size, level_decomp, i, tf_prec)
        dictionaries_tf.append(dict_filters_i)

        # Coefficients to learn : 
        theta_i = tf.compat.v1.get_variable('theta_%d' %i, dtype=tf_prec, initializer = np_prec(init_theta))
        alpha_i = tf.compat.v1.get_variable('alpha_%d' %i, dtype=tf_prec, initializer = np_prec(1/L))
        beta_i = tf.compat.v1.get_variable('beta_%d' %i, dtype=tf_prec, initializer = np_prec(init_beta)) 
        thetas_tf.append(theta_i)
        alphas_tf.append(alpha_i)
        betas_tf.append(beta_i)
    return dictionaries_tf, thetas_tf, alphas_tf, betas_tf

def restore_parameters(path_to_restore, nb_unrolledBlocks, tf_prec, np_prec, train):
    """
    Restores the parameters of a trained model.
    Parameters
    -----------
        path_to_restore (string)  : path to model to be restored
        nb_unrolledBlocks (int)   : number of different set of trainable parameters 
        tf_prec(tensorflow.dtype) : tensorflow type corresponding to the desired machine precision  
        np_prec(type)             : numpy type corresponding to the desired machine precision  
        train (int)               : 1 if parameters are to be trained, 0 otherwise   
    Returns
    -----------        
       dictionaries_tf(list)      : list of trainable dictionaries (tensorflow variables) 
       thetas_tf(list)            : list of trainable theta parameters (tensorflow variables) 
       alphas_tf(list)            : list of trainable alpha parameters (tensorflow variables) 
       betas_tf(list)             : list of trainable beta parameters (tensorflow variables) 
    """       
    # Loading dictionaries and coefficients (npy files)
    dictionaries = np.load(path_to_restore + '/dictionaries.npy',allow_pickle=True)
    thetas = np.load(path_to_restore + '/thetas.npy')
    alphas = np.load(path_to_restore + '/alphas.npy')
    betas = np.load(path_to_restore + '/betas.npy')

    # Coverting the dictionaires and coefficients into list of tensors, learnable if train==1
    dictionaries_tf = []
    thetas_tf = []
    alphas_tf = []
    betas_tf = []
    for i in range(nb_unrolledBlocks):
        dict_filters = {}
        for key in dictionaries[i].keys():    
            dict_filters[key] = tf.compat.v1.get_variable('D_'+str(i+1)+'_'+key, dtype = tf_prec,\
                                                initializer =  np_prec(dictionaries[i][key]), trainable = train) 
        dictionaries_tf.append(dict_filters)
        
        theta_i = tf.compat.v1.get_variable('theta_' + str(i+1), dtype = tf_prec, initializer = thetas[i], trainable = train) 
        alpha_i = tf.compat.v1.get_variable('alpha_' + str(i+1), dtype = tf_prec, initializer = alphas[i], trainable = train) 
        beta_i  = tf.compat.v1.get_variable('beta_'  + str(i+1), dtype = tf_prec, initializer = betas[i],  trainable = train) 
        thetas_tf.append(theta_i)
        alphas_tf.append(alpha_i)
        betas_tf.append(beta_i)     

    return dictionaries_tf, thetas_tf, alphas_tf, betas_tf


