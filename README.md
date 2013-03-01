spectral_profiler
=================

Tools to work with the Kaguya Spectral Profiler

Usage:

Download and unzip an SP observation.  It is necessary to rename the FILENAME.sl2 to FILENAME.zip.  Then point the script at the observation spc and specifiy which of the observations to visualize.  '--help' provides the command line arguments to do this.

The observation is photometrically corrected, the continuum slope is calculated, and a continuum removed spectra is provided.  

Note that we clean the data, prior to performing any correct, and remove the sensor spike that occurs in the VNIR sensor.
