import os
import sys
import copy

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
    gparam.add('n', value=4.0, vary=False)
    gparam.add('r_e', value=1.0)
    gparam.add('flux', value=1.0, vary=False)
    gparam.add('gmag', value=0.2)
    gparam.add('phi', value=0.0)
    return gparam

def make_PSF(wave, photons, PSF_model, zenith):
    PSF = PSF_model(wave, photons, zenith=zenith)
    return PSF

def measure_shear_calib(gparam, gal_PSF, star_PSF, s_engine):
    stool = chroma.GalTools.SGalTool(s_engine)

    def gen_target_image(gamma, beta):
        ring_gparam = stool.get_ring_params(gparam, gamma, beta)
        return s_engine.get_image(ring_gparam, gal_PSF)

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

def m_vs_redshift(filter_name, gal, star, n, zenith=30*numpy.pi/180):
    s_engine = chroma.ImageEngine.GalSimSEngine()#size=41, oversample_factor=41)
    PSF_model = chroma.PSF_model.GSGaussAtmPSF
    PSF_ellip = 0.0
    PSF_phi = 0.0
    data_dir = '../../data/'
    filter_file = data_dir+'filters/LSST_{}.dat'.format(filter_name)
    gal_SED_file = data_dir+'SEDs/{}.ascii'.format(gal)
    star_SED_file = data_dir+'SEDs/{}.ascii'.format(star)

    swave, sphotons = chroma.utils.get_photons(star_SED_file, filter_file, 0.0)
    sphotons /= scipy.integrate.simps(sphotons, swave)
    star_PSF = make_PSF(swave, sphotons, PSF_model, zenith)
    smom = chroma.disp_moments(swave, sphotons, zenith=zenith)

    if not os.path.isdir('output/'):
        os.mkdir('output/')
    outfile = 'output/m_vs_redshift.{}.{}.{}.{}.z{:02d}.dat'
    outfile = outfile.format(filter_name, gal, star, n, int(round(zenith*180/numpy.pi)))
    fil = open(outfile, 'w')
    gparam = fiducial_galaxy()
    gparam['n'].value = n
    stool = chroma.GalTools.SGalTool(s_engine)

    # normalize size to second moment (before PSF convolution)
    print 'n: {}'.format(gparam['n'].value)
    print 'fiducial r_e: {}'.format(gparam['r_e'].value)
    print 'setting second moment radius to 0.27 arcseconds = 1.35 pixels'
    gparam = stool.set_uncvl_r2(gparam, (0.27/0.2)**2) # (0.27 arcsec)^2 -> pixels^2
    print 'output r2: {}'.format(stool.get_uncvl_r2(gparam))
    print 'output r: {}'.format(numpy.sqrt(stool.get_uncvl_r2(gparam)))
    print 'output r_e:{}'.format(gparam['r_e'].value)

    with astropy.utils.console.ProgressBar(100) as bar:
        for z in numpy.arange(0.0, 3.0, 0.03):
            gwave, gphotons = chroma.utils.get_photons(gal_SED_file, filter_file, z)
            gphotons /= scipy.integrate.simps(gphotons, gwave)
            gal_PSF = make_PSF(gwave, gphotons, PSF_model, zenith)
            gparam1 = copy.deepcopy(gparam)
            m, c = measure_shear_calib(gparam1, gal_PSF, star_PSF, s_engine)

            gmom = chroma.disp_moments(gwave, gphotons, zenith=zenith)
            m_analytic = (smom[1] - gmom[1]) * (3600 * 180 / numpy.pi)**2 / (0.27**2)
            fil.write('{} {} {} {}\n'.format(z, c, m, m_analytic))
            bar.update()
        fil.close()

def main(argv):
    m_vs_redshift('r', 'CWW_E_ext', 'ukg5v', 0.5)
    m_vs_redshift('r', 'CWW_E_ext', 'ukg5v', 1.0)
    m_vs_redshift('r', 'CWW_E_ext', 'ukg5v', 4.0)

if __name__ == '__main__':
    main(sys.argv)