"""
Some tools to conveniently transform lmfit.Parameters into GalSim.Image's.
"""

import copy

import numpy as np
from scipy.optimize import newton
import galsim

import chroma

class GalTool(object):
    """ Some generic utilities for drawing ringtest images using GalSim and measuring second moment
    radii.
    """
    def __init__(self):
        # Subclasses of GalTool must initialize the following:
        #
        #   attributes
        #   ----------
        #   stamp_size - Integer number of pixels in which to draw images
        #   pixel_scale - arcsec / pixel
        #   PSF - either a ChromaticObject or an effective PSF as a GSObject.
        #   offset - tuple defining subpixel offset of image origin from center
        #   gsparams - galsim.GSParams instance defining parameters for GalSim.
        #
        #   methods
        #   -------
        #   _gparam_to_galsim - turn lmfit.Parameters into a galsim.GSObject or
        #                       galsim.ChromaticObject
        raise NotImplementedError("ABC GalTool must be instatiated through a subclass.")

    def get_image(self, gparam, ring_beta=None, ring_shear=None, oversample=1):
        """ Draw a galaxy image using GalSim.  Potentially rotate and shear the galaxy as part of a
        ring test.  Optionally draw a high-resolution image.

        @param gparam      An lmfit.Paramters object that will be used to initialize a GalSim object.
        @param ring_beta   Angle around ellipticity ring in ring test.
        @param ring_shear  Shear to apply after rotation as part of ring test. (type=?)
        @param oversample  Integer factor by which to scale output image resolution and size.
        @returns  galsim.Image
        """
        stamp_size = self.stamp_size * oversample
        pixel_scale = self.pixel_scale / float(oversample)
        im = galsim.ImageD(stamp_size, stamp_size, scale=pixel_scale)
        gal = self._gparam_to_galsim(gparam)
        pix = galsim.Pixel(pixel_scale)
        if ring_beta is not None:
            gal = gal.rotate(ring_beta / 2.0 * galsim.radians)
        if ring_shear is not None:
            gal = gal.shear(ring_shear)
        final = galsim.Convolve(gal, self.PSF, pix)
        if isinstance(final, galsim.ChromaticObject):
            final.draw(self.bandpass, image=im, offset=self.offset)
        elif isinstance(final, galsim.GSObject):
            final.draw(image=im, offset=self.offset)
        else:
            raise ValueError("Don't recognize galaxy object type in GalTool.")
        return im

    def get_PSF_image(self, oversample=1):
        """ Draw an image of the effective PSF.  Note that we choose to convolve by the pixel
        response function too here.

        @param oversample  Integer factor by which to scale output image resolution and size.
        """
        stamp_size = self.stamp_size * oversample
        pixel_scale = self.pixel_scale / float(oversample)
        im = galsim.ImageD(stamp_size, stamp_size, scale=pixel_scale)
        pix = galsim.Pixel(pixel_scale)
        if isinstance(self.PSF, galsim.ChromaticObject):
            star = galsim.Gaussian(fwhm=1.e-8) * self.SED
            final = galsim.Convolve(star, self.PSF, pix)
            final.draw(self.bandpass, image=im)
        elif isinstance(self.PSF, galsim.GSObject):
            final = galsim.Convolve(self.PSF, pix)
            final.draw(image=im)
        else:
            raise ValueError("Don't recognize galaxy object type in GalTool.")
        return im

    def get_r2(self, gparam, oversample=1):
        """ Compute object second moment radius sqrt(r^2) directly from image.  This may be biased
        if the object wings are significant or the postage stamp size is too small.

        @param gparam   An lmfit.Parameters object that will be used to initialize a GalSim object.
        @returns        Second moment radius (in arcsec)
        """
        im = self.get_image(gparam, oversample=oversample)
        mx, my, mxx, myy, mxy = chroma.moments(im)
        return np.sqrt(mxx + myy)

    def get_uncvl_image(self, gparam, ring_beta=None, ring_shear=None, oversample=1, center=False):
        """ Draw a galaxy image, not convolved with a PSF, using GalSim.  Potentially rotate and
        shear the galaxy as part of a ring test.  Optionally draw a high-resolution image.

        @param gparam      An lmfit.Paramters object that will be used to initialize a GalSim object.
        @param ring_beta   Angle around ellipticity ring in ring test.
        @param ring_shear  Shear to apply after rotation as part of ring test. (type=?)
        @param oversample  Integer factor by which to scale output image resolution and size.
        @param center      Force center of profile to (0,0).
        @returns  galsim.Image
        """
        stamp_size = self.stamp_size * oversample
        pixel_scale = self.pixel_scale / float(oversample)
        im = galsim.ImageD(stamp_size, stamp_size, scale=pixel_scale)
        gal = self._gparam_to_galsim(gparam)
        if center:
            centroid = gal.centroid()
            gal = gal.shift(-centroid)
        pix = galsim.Pixel(pixel_scale)
        if ring_beta is not None:
            gal = gal.rotate(ring_beta / 2.0 * galsim.radians)
        if ring_shear is not None:
            gal = gal.shear(ring_shear)
        final = galsim.Convolve(gal, pix)
        if isinstance(final, galsim.ChromaticObject):
            final.draw(self.bandpass, image=im, offset=self.offset)
        elif isinstance(final, galsim.GSObject):
            final.draw(image=im, offset=self.offset)
        else:
            raise ValueError("Don't recognize galaxy object type in GalTool.")
        return im

    def get_uncvl_r2(self, gparam, oversample=1):
        """ Compute object second moment radius directly from image.  This may be biased if the
        object wings are significant or the postage stamp size is too small.

        @param gparam   An lmfit.Parameters object that will be used to initialize a GalSim object.
        @returns        Second moment radius (in arcsec)
        """
        im = self.get_uncvl_image(gparam, oversample=oversample)
        mx, my, mxx, myy, mxy = chroma.moments(im)
        return np.sqrt(mxx + myy)

    def compute_AHM(self, gparam, oversample=4):
        """ Compute the area above half maximum of the convolved image.
        """
        original_offset = self.offset
        original_scale = self.pixel_scale
        ahms = []
        for i in range(10):
            itry = 0
            while itry < 10:
                xdither = np.random.uniform(-0.5, 0.5, 1)[0]
                ydither = np.random.uniform(-0.5, 0.5, 1)[0]
                rescale = np.random.uniform(0.9, 1.1, 1)[0]
                self.offset = (xdither, ydither)
                self.pixel_scale = original_scale * rescale
                try:
                    im = self.get_image(gparam, oversample=oversample)
                except RuntimeError:
                    itry += 1
                else:
                    break
            if itry >= 10:
                raise RuntimeError("Unable to create image to estimate AHM")
            mx = im.array.max()
            ahms.append(self.pixel_scale**2 * (im.array > mx/2.0).sum() / oversample**2)
        self.offset = original_offset
        self.pixel_scale = original_scale
        return np.mean(ahms), np.std(ahms)/np.sqrt(len(ahms))

    def compute_FWHM(self, gparam, oversample=4):
        """ Compute FWHM of the convolved galaxy image.
        """
        ahm, err = self.compute_AHM(gparam, oversample=oversample)
        fwhm = np.sqrt(4.0/np.pi * ahm)
        return fwhm, fwhm * err/ahm * 0.5

class SersicTool(GalTool):
    """ABC to handle both chromatic and monochromatic single Sersic galaxies.
    """
    def __init__(self):
        raise NotImplementedError("Cannot instantiate ABC SersicTool.")

    def _gparam_to_galsim(self, gparam):
        # Turn lmfit.Parameters into a galsim.ChromaticObject
        gal = galsim.Sersic(n=gparam['n'].value,
                            half_light_radius=gparam['hlr'].value,
                            gsparams=self.gsparams)
        gal = gal.shear(g=gparam['gmag'].value, beta=gparam['phi'].value * galsim.radians)
        gal = gal.shift(gparam['x0'].value, gparam['y0'].value)
        gal.setFlux(gparam['flux'].value)
        return gal

    def set_FWHM(self, gparam, FWHM, oversample=4):
        """ Set the galaxy PSF-convolved FWHM.
        """
        def FWHM_resid(scale):
            g1 = copy.deepcopy(gparam)
            g1['hlr'].value *= scale
            current_FWHM = self.compute_FWHM(g1, oversample=oversample)
            return current_FWHM[0] - FWHM
        scale = newton(FWHM_resid, 1.0, tol=0.001)
        gparam['hlr'].value *= scale
        return gparam

    def set_r2(self, gparam, r2, oversample=4):
        """ Set the second moment radius sqrt(r^2).

        @param gparam      lmfit.Parameters object describing galaxy.
        @param r2          Target second moment radius sqrt(r^2)
        @param oversample  Factor by which to oversample drawn image for computation.
        @returns           New lmfit.Parameters object.
        """
        def r2_resid(scale):
            g1 = copy.deepcopy(gparam)
            g1['hlr'].value *= scale
            current_r2 = self.get_r2(g1, oversample=oversample)
            return current_r2 - r2
        scale = newton(r2_resid, 1.0)
        gparam['hlr'].value *= scale
        return gparam

    def get_uncvl_r2(self, gparam):
        """ Get second moment radius sqrt(r^2) of pre-PSF-convolved profile using polynomial
        approximation.
        @gparam   lmfit.Parameters
        """
        return gparam['hlr'].value * chroma.Sersic_r2_over_hlr(gparam['n'].value)

    def set_uncvl_r2(self, gparam, r2):
        """ Set the second moment radius sqrt(r^2) of the pre-PSF-convolved profile using
        polynomial approximation.

        @param gparam      lmfit.Parameters object describing galaxy.
        @param r2          Target second moment square radius
        @param oversample  Factor by which to oversample drawn image for r2 computation.
        @returns           New lmfit.Parameters object.
        """
        gparam1 = copy.deepcopy(gparam)
        r2_now = self.get_uncvl_r2(gparam)
        scale = r2 / r2_now
        gparam1['hlr'].value = gparam['hlr'].value * scale
        return gparam1

    def get_ring_params(self, gparam, ring_beta, ring_shear):
        """ Compute initial guess parameters for given angle around ellipticity ring during a ring
        test.

        @param gparam      lmfit.Parameters object describing galaxy.
        @param ring_beta   Angle around ellipticity ring in ring test.
        @param ring_shear  Shear to apply after rotation as part of ring test. (type=?)
        @returns           New lmfit.Parameters object.
        """
        gparam1 = copy.deepcopy(gparam)
        rot_phi = gparam['phi'].value + ring_beta/2.0
        # complex ellipticity
        c_ellip = gparam['gmag'].value * \
          complex(np.cos(2.0 * rot_phi), np.sin(2.0 * rot_phi))
        c_gamma = ring_shear.g1 + 1j * ring_shear.g2
        # sheared complex ellipticity
        s_c_ellip = chroma.apply_shear(c_ellip, c_gamma)
        s_gmag = abs(s_c_ellip)
        s_phi = np.angle(s_c_ellip) / 2.0

        gparam1['x0'].value \
          = gparam['x0'].value * np.cos(ring_beta / 2.0) \
          - gparam['y0'].value * np.sin(ring_beta / 2.0)
        gparam1['y0'].value \
          = gparam['x0'].value * np.sin(ring_beta / 2.0) \
          + gparam['y0'].value * np.cos(ring_beta / 2.0)
        gparam1['gmag'].value = s_gmag
        gparam1['phi'].value = s_phi
        return gparam1


class MonoSersicTool(SersicTool):
    """A GalTool to represent single Sersic profile with a monochromatic PSF.
    """
    def __init__(self, PSF, stamp_size, pixel_scale, offset=(0,0), gsparams=None):
        """ Initialize a single Sersic profile achromatic galaxy/PSF.

        @param PSF     galsim.GSObject for the PSF
        @param stamp_size   Draw images this many pixels square
        @param pixel_scale  Pixels are this wide in arcsec.
        """
        self.PSF = PSF
        self.stamp_size = stamp_size
        self.pixel_scale = pixel_scale
        self.offset = offset
        self.gsparams = gsparams


class ChromaticSersicTool(SersicTool):
    """ A GalTool to represent single Sersic profile chromatic galaxies.
    """
    def __init__(self, SED, bandpass, PSF, stamp_size, pixel_scale, offset=(0,0), gsparams=None):
        """ Initialize a single Sersic profile chromatic galaxy.

        @param SED          galsim.SED galaxy spectrum
        @param bandpass     galsim.Bandpass to represent filter being imaged through.
        @param PSF          galsim.ChromaticObject representing chromatic PSF
        @param stamp_size   Draw images this many pixels square
        @param pixel_scale  Pixels are this wide in arcsec.
        """
        self.SED = SED
        self.bandpass = bandpass
        self.PSF = PSF
        self.stamp_size = stamp_size
        self.pixel_scale = pixel_scale
        self.offset = offset
        self.gsparams = gsparams

    def _gparam_to_galsim(self, gparam):
        # Turn lmfit.Parameters into a galsim.ChromaticObject
        mono_gal = SersicTool._gparam_to_galsim(self, gparam)
        chromatic_gal = mono_gal * self.SED
        return chromatic_gal


class FastChromaticSersicTool(SersicTool):
    def __init__(self, SED, bandpass, PSF, stamp_size, pixel_scale, offset=(0,0), gsparams=None):
        """ Initialize a single Sersic profile chromatic galaxy.  Internally use some trickery to
        speed up image drawing by cacheing an effective PSF.

        @param SED          galsim.SED galaxy spectrum
        @param bandpass     galsim.Bandpass to represent filter being imaged through.
        @param PSF          galsim.ChromaticObject representing chromatic PSF
        @param stamp_size   Draw images this many pixels square
        @param pixel_scale  Pixels are this wide in arcsec.
        """
        self.stamp_size = stamp_size
        self.pixel_scale = pixel_scale
        # now create the effective PSF!
        star = galsim.Gaussian(fwhm=1.e-8) * SED
        prof = galsim.Convolve(star, PSF)
        prof0 = prof.evaluateAtWavelength(bandpass.effective_wavelength)
        scale = prof0.nyquistDx()
        N = prof0.SBProfile.getGoodImageSize(scale,1.0)
        im = galsim.ImageD(N, N, scale=scale)
        prof.draw(bandpass, image=im)
        self.PSF = galsim.InterpolatedImage(im) # remember the effective PSF
        self.offset = offset
        self.gsparams = gsparams

class PerturbFastChromaticSersicTool(SersicTool):
    """ Similar to ChromaticSersicTool, but add ability to perturb the effective PSF by convolving
    (or deconvolving) by a Gaussian with center $\Delta \bar{R}$ and variance $\Delta V$, and
    dilating by sqrt(r^2_{gal}/r^2_{psf}).  Alternatively, for DCR I could deconvolve by the stellar
    contribution and then reconvolve by the expected galactic contribution.
    """
    def __init__(self, SED, bandpass, PSF, stamp_size, pixel_scale,
                 r2byr2=None, deltaRbar=None, deltaV=None, parang=0,
                 offset=(0,0), gsparams=None):
        """ Initialize a single Sersic profile chromatic galaxy.  Internally use some trickery to
        speed up image drawing by cacheing an effective PSF.

        @param SED          galsim.SED galaxy spectrum
        @param bandpass     galsim.Bandpass to represent filter being imaged through.
        @param PSF          galsim.ChromaticObject representing chromatic PSF
        @param stamp_size   Draw images this many pixels square
        @param pixel_scale  Pixels are this wide in arcsec.
        @param r2ybr2       r^2_{PSF, gal} / r^2_{PSF, *} for chromatic seeing correction.
        @param deltaRbar    First moment of DCR difference kernel.
        @param deltaV       Second moment of DCR difference kernel.
        @param parang       Parallactic angle of DCR difference kernel.
        """
        self.stamp_size = stamp_size
        self.pixel_scale = pixel_scale
        # Create the unperturbed effective PSF:
        star = galsim.Gaussian(fwhm=1.e-8) * SED
        prof = galsim.Convolve(star, PSF)
        prof0 = prof.evaluateAtWavelength(bandpass.effective_wavelength)
        scale = prof0.nyquistDx()
        N = prof0.SBProfile.getGoodImageSize(scale, 1.0)
        im = galsim.ImageD(N, N, scale=scale)
        # chromatic seeing correction
        if r2byr2 is None:
           r2byr2 = 1.0
        prof = prof.dilate(np.sqrt(r2byr2))
        # DCR correction
        if deltaV is None:
            kernel = galsim.Gaussian(fwhm=1.e-8)
        else:
            # Axes ratio of Gaussian representing DCR kernel.  In principle, this is 0.0, but
            # we need to set it to some small value for computability.
            q = 1.e-3
            sigma = (q * abs(deltaV))**0.5
            kernel = galsim.Gaussian(sigma=sigma)
            kernel = kernel.shear(g1=-(1-q)/(1+q))
            kernel = kernel.rotate(parang * galsim.degrees)
            if deltaV < 0.0:
                kernel = galsim.Deconvolve(kernel)

        final = galsim.Convolve(prof, kernel)
        # and draw into an InterpolatedImage
        final.draw(bandpass, image=im)
        self.PSF = galsim.InterpolatedImage(im)
        self.offset = offset
        self.gsparams = gsparams


# Note that DoubleSersicTool and FastDoubleSersicTool are both currently untested.

class DoubleSersicTool(GalTool):
    """ A GalTool to represent a sum of two chroma Sersic profiles.
    """
    def __init__(self, SED1, SED2, bandpass, PSF, stamp_size, pixel_scale, offset=(0,0),
                 gsparams=None):
        """ Initialize a single Sersic profile chromatic galaxy.

        @param SED1         galsim.SED galaxy spectrum for first component
        @param SED2         galsim.SED galaxy spectrum for second component
        @param bandpass     galsim.Bandpass to represent filter being imaged through.
        @param PSF          galsim.ChromaticObject representing chromatic PSF
        @param stamp_size   Draw images this many pixels square
        @param pixel_scale  Pixels are this wide in arcsec.
        """
        self.SED1 = SED1
        self.SED2 = SED2
        self.bandpass = bandpass
        self.PSF = PSF
        self.stamp_size = stamp_size
        self.pixel_scale = pixel_scale
        self.offset = offset
        self.gsparams = gsparams

    def _gparam_to_galsim(self, gparam):
        # Turn lmfit.gparam into a galsim.ChromaticObject
        mono_gal1 = galsim.Sersic(n=gparam['n_1'].value,
                                  half_light_radius=gparam['hlr_1'].value,
                                  gsparams=self.gsparams)
        mono_gal1 = mono_gal1.shear(
            g=gparam['gmag_1'].value, beta=gparam['phi_1'].value * galsim.radians)
        mono_gal1 = mono_gal1.shift(gparam['x0_1'].value, gparam['y0_1'].value)
        mono_gal1.setFlux(gparam['flux_1'].value)

        mono_gal2 = galsim.Sersic(n=gparam['n_2'].value,
                                  half_light_radius=gparam['hlr_2'].value,
                                  gsparams=self.gsparams)
        mono_gal2 = mono_gal2.shear(
            g=gparam['gmag_2'].value, beta=gparam['phi_2'].value * galsim.radians)
        mono_gal2 = mono_gal2.shift(gparam['x0_2'].value, gparam['y0_2'].value)
        mono_gal2.setFlux(gparam['flux_2'].value)

        gal1 = galsim.Chromatic(mono_gal1, self.SED1)
        gal2 = galsim.Chromatic(mono_gal2, self.SED2)
        return gal1 + gal2

    def get_PSF_image(self, oversample=1):
        """ Draw an image of both effective PSFs.  Note that we choose to convolve by the pixel
        response function too here.

        @param oversample  Integer factor by which to scale output image resolution and size.
        @returns (im1, im2)  Both effective PSFs corresponding to both component SEDs.
        """
        stamp_size = self.stamp_size * oversample
        pixel_scale = self.pixel_scale / float(oversample)
        im1 = galsim.ImageD(stamp_size, stamp_size, scale=pixel_scale)
        im2 = galsim.ImageD(stamp_size, stamp_size, scale=pixel_scale)
        pix = galsim.Pixel(pixel_scale)
        star1 = galsim.Gaussian(fwhm=1.e-8) * self.SED1
        final1 = galsim.Convolve(star1, self.PSF, pix)
        final1.draw(self.bandpass, image=im1)
        star2 = galsim.Gaussian(fwhm=1.e-8) * self.SED2
        final2 = galsim.Convolve(star2, self.PSF, pix)
        final2.draw(self.bandpass, image=im2)
        return im1, im2

    def set_FWHM(self, gparam, FWHM, oversample=4):
        """ Set the galaxy PSF-convolved FWHM.
        """
        def FWHM_resid(scale):
            g1 = copy.deepcopy(gparam)
            g1['hlr_1'].value *= scale
            g1['hlr_2'].value *= scale
            current_FWHM = self.compute_FWHM(g1, oversample=oversample)
            return current_FWHM[0] - FWHM
        scale = newton(FWHM_resid, 1.0, tol=0.01)
        gparam['hlr_1'].value *= scale
        gparam['hlr_2'].value *= scale
        return gparam

    def set_r2(self, gparam, r2, oversample=4):
        """ Set the second moment radius sqrt(r^2).

        @param gparam      lmfit.Parameters object describing galaxy.
        @param r2          Target second moment radius sqrt(r^2)
        @param oversample  Factor by which to oversample drawn image for r2 computation.
        @returns           New lmfit.Parameters object.
        """
        def r2_resid(scale):
            g1 = copy.deepcopy(gparam)
            g1['hlr_1'].value *= scale
            g1['hlr_2'].value *= scale
            current_r2 = self.get_r2(g1, oversample=oversample)
            return current_r2 - r2
        scale = newton(r2_resid, 1.0)
        gparam['hlr_1'].value *= scale
        gparam['hlr_2'].value *= scale
        return gparam

    def get_uncvl_r2(self, gparam):
        """ Get second moment radius of pre-PSF-convolved profile using polynomial approximation.
        @gparam   lmfit.Parameters
        """
        return chroma.component_Sersic_r2([gparam['n_1'].value, gparam['n_2'].value],
                                          [gparam['flux_1'].value, gparam['flux_2'].value],
                                          [gparam['hlr_1'].value, gparam['hlr_2'].value])

    def set_uncvl_r2(self, gparam, r2):
        """ Set the second moment square radius of the pre-PSF-convolved profile using polynomial
        approximation.

        @param gparam      lmfit.Parameters object describing galaxy.
        @param r2          Target second moment radius sqrt(r^2)
        @param oversample  Factor by which to oversample drawn image for computation.
        @returns           New lmfit.Parameters object.
        """
        gparam1 = copy.deepcopy(gparam)
        r2_now = self.get_uncvl_r2(gparam)
        scale = np.sqrt(r2 / r2_now)
        gparam1['hlr_1'].value *= scale
        gparam1['hlr_2'].value *= scale
        return gparam1

    def get_ring_params(self, gparam, ring_beta, ring_shear):
        """ Compute initial guess parameters for given angle around ellipticity ring during a ring
        test.

        @param gparam      lmfit.Parameters object describing galaxy.
        @param ring_beta   Angle around ellipticity ring in ring test.
        @param ring_shear  Shear to apply after rotation as part of ring test. (type=?)
        @returns           New lmfit.Parameters object.
        """
        gparam1 = copy.deepcopy(gparam)

        rot_phi1 = gparam['phi_1'].value + ring_beta/2.0
        # complex ellipticity
        c_ellip1 = gparam['gmag_1'].value * \
          complex(np.cos(2.0 * rot_phi1), np.sin(2.0 * rot_phi1))
        c_gamma1 = ring_shear.g1 + 1j * ring_shear.g2
        # sheared complex ellipticity
        s_c_ellip1 = chroma.apply_shear(c_ellip1, c_gamma)
        s_gmag1 = abs(s_c_ellip1)
        s_phi1 = np.angle(s_c_ellip1) / 2.0

        gparam1['x0_1'].value \
          = gparam['x0_1'].value * np.cos(ring_beta / 2.0) \
          - gparam['y0_1'].value * np.sin(ring_beta / 2.0)
        gparam1['y0_1'].value \
          = gparam['x0_1'].value * np.sin(ring_beta / 2.0) \
          + gparam['y0_1'].value * np.cos(ring_beta / 2.0)
        gparam1['gmag_1'].value = s_gmag1
        gparam1['phi_1'].value = s_phi1

        rot_phi2 = gparam['phi_2'].value + ring_beta/2.0
        # complex ellipticity
        c_ellip2 = gparam['gmag_2'].value * \
          complex(np.cos(2.0 * rot_phi2), np.sin(2.0 * rot_phi2))
        c_gamma2 = ring_shear.g2 + 1j * ring_shear.g2
        # sheared complex ellipticity
        s_c_ellip2 = chroma.apply_shear(c_ellip2, c_gamma)
        s_gmag2 = abs(s_c_ellip2)
        s_phi2 = np.angle(s_c_ellip2) / 2.0

        gparam1['x0_2'].value \
          = gparam['x0_2'].value * np.cos(ring_beta / 2.0) \
          - gparam['y0_2'].value * np.sin(ring_beta / 2.0)
        gparam1['y0_2'].value \
          = gparam['x0_2'].value * np.sin(ring_beta / 2.0) \
          + gparam['y0_2'].value * np.cos(ring_beta / 2.0)
        gparam1['gmag_2'].value = s_gmag2
        gparam1['phi_2'].value = s_phi2

        return gparam1


class FastDoubleSersicTool(DoubleSersicTool):
    def __init__(self, SED1, SED2, bandpass, PSF, stamp_size, pixel_scale, offset=(0,0),
                 gsparams=None):
        """ Initialize a 2 component chromatic Sersic profile.  Internally use some trickery to
        speed up image drawing by cacheing two effective PSFs.

        @param SED1         galsim.SED galaxy spectrum for first component
        @param SED2         galsim.SED galaxy spectrum for second component
        @param bandpass     galsim.Bandpass to represent filter being imaged through.
        @param PSF          galsim.ChromaticObject representing chromatic PSF
        @param stamp_size   Draw images this many pixels square
        @param pixel_scale  Pixels are this wide in arcsec.
        """
        self.stamp_size = stamp_size
        self.pixel_scale = pixel_scale
        # now create the effective PSFs
        star1 = galsim.Gaussian(fwhm=1.e-8) * SED1
        prof1 = galsim.Convolve(star1, PSF)
        prof10 = prof1.evaluateAtWavelength(bandpass.effective_wavelength)
        scale = prof10.nyquistDx()
        N = prof10.SBProfile.getGoodImageSize(scale,1.0)
        im = galsim.ImageD(N, N, scale=scale)
        prof1.draw(bandpass, image=im)
        self.PSF1 = galsim.InterpolatedImage(im) # remember the effective PSF

        star2 = galsim.Gaussian(fwhm=1.e-8) * SED2
        prof2 = galsim.Convolve(star2, PSF)
        prof20 = prof2.evaluateAtWavelength(bandpass.effective_wavelength)
        scale = prof20.nyquistDx()
        N = prof10.SBProfile.getGoodImageSize(scale,1.0)
        im = galsim.ImageD(N, N, scale=scale)
        prof2.draw(bandpass, image=im)
        self.PSF2 = galsim.InterpolatedImage(im2) # remember the effective PSF

        self.offset = offset
        self.gsparams = gsparams

    def _gparam_to_galsim(self, gparam):
        # Turn lmfit.gparam into a galsim.ChromaticObject
        mono_gal1 = galsim.Sersic(n=gparam['n_1'].value,
                                  half_light_radius=gparam['hlr_1'].value,
                                  gsparams=self.gsparams)
        mono_gal1 = mono_gal1.shear(
            g=gparam['gmag_1'].value, beta=gparam['phi_1'].value * galsim.radians)
        mono_gal1 = mono_gal1.shift(gparam['x0_1'].value, gparam['y0_1'].value)
        mono_gal1.setFlux(gparam['flux_1'].value)

        mono_gal2 = galsim.Sersic(n=gparam['n_2'].value,
                                  half_light_radius=gparam['hlr_2'].value,
                                  gsparams=self.gsparams)
        mono_gal2 = mono_gal2.shear(
            g=gparam['gmag_2'].value, beta=gparam['phi_2'].value * galsim.radians)
        mono_gal2 = mono_gal2.shift(gparam['x0_2'].value, gparam['y0_2'].value)
        mono_gal2.setFlux(gparam['flux_2'].value)

        return gal1, gal2

    def get_image(self, param, ring_beta=None, ring_shear=None, oversample=1):
        """ Draw a galaxy image using GalSim.  Potentially rotate and shear the galaxy as part of a
        ring test.  Optionally draw a high-resolution image.

        @param gparam      An lmfit.Paramters object that will be used to initialize a GalSim object.
        @param ring_beta   Angle around ellipticity ring in ring test.
        @param ring_shear  Shear to apply after rotation as part of ring test. (type=?)
        @param oversample  Integer factor by which to scale output image resolution and size.
        @returns  galsim.Image
        """
        stamp_size = self.stamp_size * oversample
        pixel_scale = self.pixel_scale / float(oversample)
        im = galsim.ImageD(stamp_size, stamp_size, scale=pixel_scale)
        gal1, gal2 = self._gparam_to_galsim(gparam)
        pix = galsim.Pixel(pixel_scale)
        if ring_beta is not None:
            gal1 = gal1.rotate(ring_beta / 2.0 * galsim.radians)
            gal2 = gal2.rotate(ring_beta / 2.0 * galsim.radians)
        if ring_shear is not None:
            gal1 = gal1.shear(ring_shear)
            gal2 = gal2.shear(ring_shear)
        final1 = galsim.Convolve(gal1, self.PSF1, pix)
        final2 = galsim.Convolve(gal2, self.PSF2, pix)
        final1.draw(image=im, offset=self.offset)
        final2.draw(image=im, add_to_image=True, offset=self.offset)
        return im

    def get_PSF_image(self, oversample=1):
        """ Draw an image of both effective PSFs.  Note that we choose to convolve by the pixel
        response function too here.

        @param oversample  Integer factor by which to scale output image resolution and size.
        @returns (im1, im2)  Both effective PSFs corresponding to both component SEDs.
        """
        stamp_size = self.stamp_size * oversample
        pixel_scale = self.pixel_scale / float(oversample)
        im1 = galsim.ImageD(stamp_size, stamp_size, scale=pixel_scale)
        im2 = galsim.ImageD(stamp_size, stamp_size, scale=pixel_scale)
        pix = galsim.Pixel(pixel_scale)
        final1 = galsim.Convolve(self.PSF1, pix)
        final1.draw(self.bandpass, image=im1)
        final2 = galsim.Convolve(self.PSF2, pix)
        final2.draw(self.bandpass, image=im2)
        return im1, im2

    def get_uncvl_image(self, gparam, ring_beta=None, ring_shear=None, oversample=1, center=False):
        return NotImplementedError("Unconvolved image impossible for inseparable chromatic profile.")
