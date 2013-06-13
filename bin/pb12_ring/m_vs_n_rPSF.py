import os

import numpy
import scipy.integrate
import lmfit
import astropy.utils.console

import _mypath
import chroma

def fiducial_galaxy():
    gparam = lmfit.Parameters()
    gparam.add('x0', value=0.1)
    gparam.add('y0', value=0.3)
    gparam.add('n', value=0.5, vary=False)
    gparam.add('r_e', value=1.0)
    gparam.add('flux', value=1.0, vary=False)
    gparam.add('gmag', value=0.2)
    gparam.add('phi', value=0.0)
    return gparam

def make_PSF(wave, photons, PSF_ellip, PSF_phi, PSF_model):
    PSF = PSF_model(wave, photons, zenith=45.0 * numpy.pi / 180.0,
                    gauss_ellip=PSF_ellip, gauss_phi=PSF_phi,
                    FWHM=3.0)
    return PSF

def measure_shear_calib(gparam, gal_PSF, star_PSF, s_engine):

    stool = chroma.GalTools.SGalTool(s_engine)

    def gen_target_image(gamma, beta):
        ring_param = stool.get_ring_params(gparam, gamma, beta)
        return s_engine.get_image(ring_param, gal_PSF)

    # function to measure ellipticity of target_image by trying to match the pixels
    # but using the "wrong" PSF (from the stellar SED)
    def measure_ellip(target_image, init_param):
        def resid(param):
            im = s_engine.get_image(param, star_PSF)
            return (im - target_image).flatten()
        result = lmfit.minimize(resid, init_param)
        gmag = result.params['gmag'].value
        phi = result.params['phi'].value
        c_ellip = gmag * complex(numpy.cos(2.0 * phi), numpy.sin(2.0 * phi))
        return c_ellip

    def get_ring_params(gamma, beta):
        return stool.get_ring_params(gparam, gamma, beta)

    gamma0 = 0.0 + 0.0j
    gamma0_hat = chroma.utils.ringtest(gamma0, 3,
                                       gen_target_image,
                                       get_ring_params,
                                       measure_ellip, silent=True)
    c = gamma0_hat.real, gamma0_hat.imag

    gamma1 = 0.01 + 0.02j
    gamma1_hat = chroma.utils.ringtest(gamma1, 3,
                                       gen_target_image,
                                       get_ring_params,
                                       measure_ellip, silent=True)
    m0 = (gamma1_hat.real - c[0])/gamma1.real - 1.0
    m1 = (gamma1_hat.imag - c[1])/gamma1.imag - 1.0
    m = m0, m1
    return m, c

def m_vs_n_rPSF():
    s_engine = chroma.ImageEngine.GalSimSEngine(size=41, oversample_factor=41)
    PSF_model = chroma.PSF_model.GSGaussAtmPSF

    PSF_ellip = 0.0
    PSF_phi = 0.0
    filter_file = '../../data/filters/LSST_r.dat'
    gal_SED_file = '../../data/SEDs/CWW_E_ext.ascii'
    star_SED_file = '../../data/SEDs/ukg5v.ascii'
    z = 1.2

    swave, sphotons = chroma.utils.get_photons(star_SED_file, filter_file, 0.0)
    sphotons /= scipy.integrate.simps(sphotons, swave)
    star_PSF = make_PSF(swave, sphotons, PSF_ellip, PSF_phi, PSF_model)
    smom = chroma.disp_moments(swave, sphotons, zenith=45.0 * numpy.pi / 180)

    if not os.path.isdir('output/'):
        os.mkdir('output/')
    fil = open('output/m_vs_n_rPSF.dat', 'w')


    r2s = (numpy.linspace(0.2, 0.5, 21) / 0.2)**2 #arcsec -> pixels
    ns = numpy.linspace(0.5, 4.0, 21)
    gwave, gphotons = chroma.utils.get_photons(gal_SED_file, filter_file, z)
    gphotons /= scipy.integrate.simps(gphotons, gwave)
    gal_PSF = make_PSF(gwave, gphotons, PSF_ellip, PSF_phi, PSF_model)

    stool = chroma.GalTools.SGalTool(s_engine)

    with astropy.utils.console.ProgressBar(len(r2s) * len(ns)) as bar:
        for r2 in r2s:
            for n in ns:
                gparam = fiducial_galaxy()
                gparam['n'].value = n
                gparam = stool.set_uncvl_r2(gparam, r2)

                m, c = measure_shear_calib(gparam, gal_PSF, star_PSF, s_engine)

                gmom = chroma.disp_moments(gwave, gphotons, zenith=45.0 * numpy.pi / 180)
                fil.write('{} {} : {} {}\n'.format(r2, n, c, m))
                bar.update()

    fil.close()

if __name__ == '__main__':
    m_vs_n_rPSF()
