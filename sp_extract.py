from __future__ import division

from struct import unpack, unpack_from

import sys
import numpy as np
from matplotlib.collections import LineCollection
from pylab import *
import argparse
import os
import math

parser = argparse.ArgumentParser(description='Spectral Profiler Reflectance Extraction Tool')

parser.add_argument('input_data', action='store', help='The ".spc" file shipped with the SP data.')
parser.add_argument('albedo_tab', action='store', help='The albedo table for the chosen overall reflectance (high, medium, or low).')
parser.add_argument('-w', action='store',dest='wv_limits', default=1652, nargs=1, help='The limit wavelength to visualize to.')
parser.add_argument('-s', action='store_true', dest='save', help='Save output to a CSV file.')
parser.add_argument('observation', default=0,type=int, nargs='+', help='The range of observations to visualize.')
args = parser.parse_args()


def openspc(input_data, save):

    """
    Parameters:
    
    input file     type .spc
                   This is the .spc file that contains the label and data.    
    
    Returns:
    wavelength     type: ndarray
                   An array of wavelengths from all 3 detectors
                   
    radiance       type: ndarray
                   An array of radiance values over the image.  This is binned into n observations.  In tests we have generally seen 44 observations per image.
                   
    reflectance    type: ndarray
                   An array of reflectance values over the image.
                   This is binned into n observations.  In tests we have generally seen 44 observations per image.
    """
    
    
    label = open(input_data, 'r+b')
    for line in label:
        if "^SP_SPECTRUM_WAV" in line:
            wav_offset = int(line.split('=')[1].split(" ")[1])
        if "^SP_SPECTRUM_RAD" in line:
            rad_offset = int(line.split('=')[1].split(" ")[1])
        if "^SP_SPECTRUM_REF" in line:
            ref_offset = int(line.split('=')[1].split(" ")[1])        
        if "OBJECT                               = SP_SPECTRUM_RAD" in line:
            line = label.next()
            rad_lines = int(line.split('=')[1])
        if "OBJECT                               = SP_SPECTRUM_REF" in line:
            line = label.next()
            ref_lines = int(line.split('=')[1])
        if 'NAME                         = "EMISSION_ANGLE"' in line:
            line = label.next();line = label.next(); line=label.next()
            emission_offset = int(line.split("=")[1])
        if 'NAME                         = "INCIDENCE_ANGLE"' in line:
            line = label.next();line = label.next(); line=label.next()
            incidence_offset = int(line.split("=")[1])   
        if 'NAME                         = "PHASE_ANGLE"' in line:
            line = label.next();line = label.next(); line=label.next()
            phase_offset = int(line.split("=")[1]) 
        if 'NORMAL_SP_POINT_NUM' in line:
            num_observations = int(line.split("=")[1])
        if 'ROW_BYTES' in line:
            row_bytes = int(line.split("=")[1])
        if "^ANCILLARY_AND_SUPPLEMENT_DATA" in line:
            ancillary_offset = int(line.split("=")[1].split("<")[0])
        if "OBJECT                               = SP_SPECTRUM_QA" in line:
            #We only need ~20 lines, break before binary starts
            break
        
    #Wavelength
    label.seek(wav_offset-1) #Seek to the wavelength section
    array = np.fromstring(label.read(296*2), dtype='>H')
    wv_array = array.astype('float')
    wv_array *= 0.1

    #Radiance
    label.seek(rad_offset-1)
    array = np.fromstring(label.read(rad_lines*296*2), dtype='>H')
    rad_array = array.astype('float')
    rad_array *= 0.01
    rad_array = rad_array.reshape(rad_lines,296)
    #print rad_array
    
    #Reflectance
    label.seek(ref_offset-1) #Seek to the wavelength section
    array = np.fromstring(label.read(ref_lines*296*2), dtype='>H')
    ref_array = array.astype('float')
    ref_array *= 0.0001
    ref_array = ref_array.reshape(ref_lines,296)

    #Parse the binary to get i, e, and phase for each observation
    angles = []
    for n in range(num_observations):
        #Emission Angle
        label.seek(ancillary_offset + (n*row_bytes-1) +  (emission_offset-1))
        emission_angle = unpack('>f', label.read(4))[0]
        #Incidence Angle
        label.seek(ancillary_offset + (n*row_bytes-1) + (incidence_offset-1))
        incidence_angle = unpack('>f', label.read(4))[0]
        #Phase Angle
        label.seek(ancillary_offset + (n*row_bytes-1) + (phase_offset-1))
        phase_angle = unpack('>f', label.read(4))[0]
        angles.append([incidence_angle, emission_angle,  phase_angle])
    angles = np.asarray(angles)

    if save == True:
        #print wv_array.shape, ref_array.T.shape
        #print np.concatenate((np.reshape(wv_array,(296,1)), ref_array.T), axis=1)
        np.savetxt('reflectance_csv.txt', np.concatenate((np.reshape(wv_array,(296,1)), ref_array.T), axis=1), delimiter=',')
    
    return wv_array, rad_array, ref_array, angles
    

def clean_data(array):
    """
    Parameters:
    
    array          type: ndarray
                   This is an array that needs to be cleaned, i.e. the data spike around 1 micron us removed and the data is clipped at 1.7 microns.  
    
    Returns:
    cleaned array  type: ndarray
                   A 161 element array (indexed from 0 to 160).  If this is relfectance or radiance, it contains one row per observation.
    """
    try: 
        #If this does not fail we have a multi-dimensional array that is either reflectance or radiance
        array.shape[1]
        mask = np.asarray(np.concatenate((np.ones(61),np.zeros(23),np.ones(212))), dtype = bool)
        array_out = array[:,mask]
        return array_out
    except:
        #We have the wavelength array
        array_out = np.delete(array, range(61,84))
        return array_out

def getbandnumbers(wavelengths, *args):
    '''
    This parses the wavelenth list,finds the mean wavelength closest to the 
    provided wavelength, and returns the index of that value.  One (1) is added
    to the index to grab the correct band.
    
    Parameters
    ----------
    wavelengths: A list of wavelengths, 0 based indexing
    *args: A variable number of input wavelengths to map to bands
    
    Returns
    -------
    bands: A variable length list of bands.  These are in the same order they are
    provided in.  Beware that altering the order will cause unexpected results.
    
    '''
    bands = []
    for x in args:
        bands.append(min(range(len(wavelengths)), key=lambda i: abs(wavelengths[i]-x)))
    return bands

def parse_coefficients(coefficient_table):
    '''
    Parameters
    ----------
    
    coefficient_table     type: file path
                          The CSV file to be parsed
                          
    Returns
    -------
    supplemental          type: list of lists
                          List of coefficients where index is the sequentially increasing wavelength.  This data is 'cleaned'.  The r_{mean} at 1003.6 is set to -999, a NoDataValue.
    '''
    d = open(coefficient_table)
    supplemental = []
    for line in d:
        line = line.split(",")
        supplemental.append([float(s) for s in line[1:]])    

    return supplemental

def photometric_correction(wv, ref_vec,coefficient_table, angles, xl_fixed,c1,c2,c3):
    '''
    TODO: Docs here
    This function performs the photometric correction.
    '''
    incidence_angle = angles[:,0]
    emission_angle = angles[:,1]
    phase_angle = angles[:,2]
 
    
    def _phg(g, phase_angle):
        '''This function allows positive and neg. g to be passed in'''
        phg = (1.0-g**2) / (1.0+g**2-2.0*g*np.cos(np.radians(phase_angle))**(1.5))
        return phg    

    #The ref_array runs to the detector limit, but the coefficient table truncates at 1652.1, we therefore only correct the wavelengths that we know the coefficents for.
    #Column  = ref_array[:,wv]
    b_naught = coefficient_table[wv][0]
    h = coefficient_table[wv][1]
    c = coefficient_table[wv][2]
    g = coefficient_table[wv][3]
    
    #Compute the phase function with fixed values
    p = ((1-c)/2) * _phg(g,30) + ((1+c)/2) * _phg((-1 * g),30)
    b = b_naught / (1+(np.tan(np.radians(30/2.0))/h))
    f_fixed = (1+b)*p 

    #Compute the phase function with the observation phase
    p = (((1-c)/2) * _phg(g,phase_angle)) + (((1+c)/2)* _phg((-1 * g),phase_angle))
    b = b_naught / (1+(np.tan(np.radians(phase_angle/2.0))/h))
    f_observed = (1+b)*p

    f_ratio = f_fixed / f_observed
    
    #Compute the lunar lambert function
    l = 1.0 + (c1*phase_angle) + (c2*phase_angle**2) + (c3*phase_angle**3)
    cosi = np.cos(np.radians(incidence_angle))
    cose = np.cos(np.radians(emission_angle))
    xl_observed = 2 * l * (cosi / (cosi + cose)) + ((1-l)*cosi)
    xl_ratio = xl_fixed / xl_observed

    #Compute the photometrically corrected reflectance
    ref_vec = ref_vec * xl_ratio * f_ratio
    return ref_vec

def continuum_correction(bands, ref_array, obs_id):
    y2 = ref_array[obs_id][bands[1]]
    y1 = ref_array[obs_id][bands[0]]
    wv2 = wv_array[bands[1]]
    wv1 = wv_array[bands[0]]

    m = (y2-y1) / (wv2 - wv1)
    b =  y1 - (m * wv1)
    y = m * wv_array + b

    continuum_corrected_ref_array = ref_array[obs_id] / y    
    return continuum_corrected_ref_array, y

#Read in the spc file, extract necessary info, and clean the data
wv_array, rad_array, ref_array, angles = openspc(args.input_data, args.save)
wv_array = clean_data(wv_array)
ref_array = clean_data(ref_array)
maxwv = int(args.wv_limits)
extent = np.where(wv_array <= maxwv)

#Parse the supplemental table to get photometric correction coefficients
coefficient_table = parse_coefficients(args.albedo_tab)

#Perform the photometric correction on the reflectance values
#Compute the 'static' lunar lambert function for r(30,0,30).
c1 = -0.019
c2 = 0.000242	
c3 = -.00000146
l = 1.0 + (c1*(30)) + (c2*(30**2)) + (c3*(30**3))
cosi = math.cos(math.radians(30))
cose = math.cos(math.radians(0))
xl_constant = ((2*l*(cosi /(cosi + cose)))) + ((1-l)*cosi)

#Copy the unphotometrically corrected array
input_refarray = np.copy(ref_array)

#Perform the photometric correction
for wv in range(len(coefficient_table)):
    ref_array[:,wv] = photometric_correction(wv, ref_array[:,wv], coefficient_table, angles, xl_constant,c1,c2,c3)

#Copy the photometrically corrected array
photometrically_corrected_ref_array = np.copy(ref_array)
continuum_slope_array = np.empty(ref_array.shape)

#Continuum correction
bands = getbandnumbers(wv_array, 752.8,1547.7)

#Continuum correct all observations
for obs_id in range(len(ref_array)): 
    ref_array[obs_id],continuum_slope_array[obs_id] = continuum_correction(bands, ref_array, obs_id)
    
#TODO If the save flag is true we could save out all observations to CSV

for obs in range(len(args.observation)):
    #Do the plotting
    fig = plt.figure(args.observation[obs], figsize=(12,12))
    fig.subplots_adjust(hspace=0.75)
    
    ax1 = subplot(411)
    grid(alpha=.5)
    plot(wv_array[extent],input_refarray[obs][extent], linewidth=1.5)
    xlabel('Wavelength', fontsize=10)
    ax1.set_xticks(wv_array[extent][::4])
    ax1.set_xticklabels(wv_array[extent][::4], rotation=45, fontsize=8)
    ax1.set_xlim(wv_array[extent].min()-10, wv_array[extent].max()+10)
    ylabel('Reflectance', fontsize=10)
    ax1.set_yticklabels(input_refarray[obs][extent],fontsize=8)
    title('Level 2B2 Data', fontsize=12)
    
    ax2 = subplot(412)
    grid(alpha=.5)
    plot(wv_array[extent],photometrically_corrected_ref_array[obs][extent], linewidth=1.5)
    xlabel('Wavelength', fontsize=10)
    ax2.set_xticks(wv_array[extent][::4])
    ax2.set_xticklabels(wv_array[extent][::4], rotation=45, fontsize=8)
    ax2.set_xlim(wv_array[extent].min()-10, wv_array[extent].max()+10)
    ylabel('Reflectance', fontsize=10)
    ax2.set_yticklabels(input_refarray[obs][extent],fontsize=8)
    title('Photometrically Corrected Data', fontsize=12)
    
    ax3 = subplot(413)
    grid(alpha=.5)
    plot(wv_array[extent],photometrically_corrected_ref_array[obs][extent], label='Photometrically Corrected Spectrum', linewidth=1.5)
    plot(wv_array[extent], continuum_slope_array[obs][extent],'r--', label='Spectral Continuum', linewidth=1.5)
    xlabel('Wavelength', fontsize=10)
    ax3.set_xticks(wv_array[extent][::4])
    ax3.set_xticklabels(wv_array[extent][::4], rotation=45, fontsize=8)
    ax3.set_xlim(wv_array[extent].min()-10, wv_array[extent].max()+10)
    ylabel('Reflectance', fontsize=10)
    ax3.set_yticklabels(input_refarray[obs][extent],fontsize=8)
    title('Continuum Slope', fontsize=12)
    
    ax4 = subplot(414)
    grid(alpha=.5)
    plot(wv_array[extent], ref_array[obs][extent], linewidth=1.5)
    xlabel('Wavelength', fontsize=10)
    ax4.set_xticks(wv_array[extent][::4])
    ax4.set_xticklabels(wv_array[extent][::4], rotation=45, fontsize=8)
    ax4.set_xlim(wv_array[extent].min()-10, wv_array[extent].max()+10)
    ylabel('Reflectance', fontsize=10)
    ax4.set_yticklabels(input_refarray[obs][extent],fontsize=8)
    title('Continuum Removed Spectrum', fontsize=12)
    
    draw()
    
show()