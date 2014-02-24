import numpy as np

import galsim

import dcr

class SED(galsim.SED):
    """ Subclass galsim.SED to add a few additional methods for calculating magnitudes and
    chromatic biases.
    """
    def createWithMagnitude(self, bandpass, target_magnitude):
        """ Return a new SED with AB Magnitude through `bandpass` set to `target_magnitude`.
        """
        current_mag = self.getMagnitude(bandpass)
        scale = 10**(-0.4 * (target_magnitude - current_mag))
        return self * scale

    def getMagnitude(self, bandpass):
        """ Return AB magnitude of SED measured through `bandpass`.
        """
        wave_list = np.array(bandpass.wave_list)
        flux = np.trapz(bandpass(wave_list) * self(wave_list), wave_list)
        return -2.5 * np.log10(flux) - bandpass.getABZeropoint()

    def getDCRMomentShifts(self, bandpass, zenith, **kwargs):
        """ Calculates shifts in first and second moments of surface brightness profile due to
        differential chromatic refraction (DCR)."""
        wave_list = np.array(bandpass.wave_list)
        R = dcr.get_refraction(wave_list, zenith, **kwargs)
        photons = bandpass(wave_list) * self(wave_list)
        norm = np.trapz(photons, wave_list)
        Rbar = np.trapz(R * photons, wave_list) / norm
        V = np.trapz((R-Rbar)**2 * photons, wave_list) / norm
        return Rbar, V

    def getSeeingShift(self, bandpass, alpha=-0.2):
        """ Calculates relative size of PSF compared to PSF size at 500 nm.
        """
        wave_list = np.array(bandpass.wave_list)
        photons = bandpass(wave_list) * self(wave_list)
        return (np.trapz(photons * (wave_list/500.0)**(2*alpha), wave_list) /
                np.trapz(photons, wave_list))


class Bandpass(galsim.Bandpass):
    """ Subclass galsim.Bandpass to add zeropoints
    """
    def getABZeropoint(self):
        if not (hasattr(self, 'zp')):
            AB_source = 3631e-23 # 3631 Jy -> erg/s/Hz/cm^2
            c = 29979245800.0 # speed of light in cm/s
            nm_to_cm = 1.0e-7
            wave_list = np.array(self.wave_list)
            # convert AB source from erg/s/Hz/cm^2*cm/s/nm^2 -> erg/s/cm^2/nm
            AB_flambda = AB_source * c / wave_list**2 / nm_to_cm
            AB_photons = AB_flambda * wave_list * self(wave_list)
            AB_flux = np.trapz(AB_photons, wave_list)
            self.zp = -2.5 * np.log10(AB_flux)
        return self.zp

    def createTruncated(self, relative_throughput=None, blue_limit=None, red_limit=None):
        ret = galsim.Bandpass.createTruncated(self, relative_throughput, blue_limit, red_limit)
        ret.__class__ = Bandpass
        return ret

    def createThinned(self, step):
        ret = galsim.Bandpass.createThinned(self, step)
        ret.__class__ = Bandpass
        return ret
