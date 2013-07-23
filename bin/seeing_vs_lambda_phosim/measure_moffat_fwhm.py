import sys

import numpy
import lmfit

import matplotlib.pyplot as plt
from astropy import wcs
from astropy.io import fits

def encode_obshistid(mode, mono_wave, filter_name, zenith, seed):
    mode_digits = str(mode)
    wave_digits = '{:04d}'.format(int(round(mono_wave)))
    filter_number = {'u':'0','g':'1','r':'2','i':'3','z':'4','Y':'5'}
    filter_digit = filter_number[filter_name]
    zenith_digit = str(int(round((zenith / 10.0))))
    seed_digit = '{:03d}'.format(seed - 1000)
    return mode_digits + wave_digits + filter_digit + zenith_digit + seed_digit

def moffat2d(params):
    fwhm_x = params['fwhm_x'].value
    fwhm_y = params['fwhm_y'].value
    beta = params['beta'].value
    peak = params['peak'].value
    x0 = params['x0'].value
    y0 = params['y0'].value

    alpha_x = fwhm_x / (2.0 * numpy.sqrt(2.0**(1.0 / beta) - 1.0))
    alpha_y = fwhm_y / (2.0 * numpy.sqrt(2.0**(1.0 / beta) - 1.0))
    def f(y, x):
        u = ((x - x0) / alpha_x)**2.0 + ((y - y0) / alpha_y)**2.0
        p = 1.0 / ((u + 1.0)**beta)
        return peak*p/p.max()
    return f

def moments(data, pixsize=1.0):
    '''Compute first and second (quadrupole) moments of `data`.  Scales result by `pixsize` for
    non-unit width pixels.

    Arguments
    ---------
    data -- array to analyze
    pixsize -- linear size of a pixel
    '''
    ys, xs = numpy.mgrid[0:data.shape[0], 0:data.shape[1]] * pixsize
    total = data.sum()
    xbar = (data * xs).sum() / total
    ybar = (data * ys).sum() / total
    Ixx = (data * (xs-xbar)**2).sum() / total
    Iyy = (data * (ys-ybar)**2).sum() / total
    Ixy = (data * (xs - xbar) * (ys - ybar)).sum() / total
    return xbar, ybar, Ixx, Iyy, Ixy

def measure_moffat_fwhm(mode, mono_wave, filter_name, zenith, seed):
    if mode > 2:
        print 'invalid mode'
        sys.exit()

    filter_number = {'u':'0','g':'1','r':'2','i':'3','z':'4','Y':'5'}
    obshistid = encode_obshistid(mode, mono_wave, filter_name, zenith, seed)
    image_file = 'output/eimage_{}_f{}_R22_S11_E000.fits.gz'
    image_file = image_file.format(obshistid, filter_number[filter_name])

    try:
        hdulist = fits.open(image_file)
    except:
        return (numpy.nan, numpy.nan, numpy.nan, numpy.nan, numpy.nan, numpy.nan)
    w = wcs.WCS(hdulist[0].header)

    RAs = [-0.035, -0.025, -0.015, -0.005, 0.005, 0.015, 0.025, 0.035]
    DECs = [-0.035, -0.025, -0.015, -0.005, 0.005, 0.015, 0.025, 0.035]

    values = numpy.empty(len(RAs) * len(DECs),
                         dtype=[('fwhm_x','f4'), ('fwhm_y','f4'), ('beta', 'f4')])

    i=0
    for RA in RAs:
        for DEC in DECs:
            center = w.wcs_world2pix(numpy.array([[RA, DEC]], numpy.float_),0)
            thumb = hdulist[0].data[center[0,1]-30:center[0,1]+30, center[0,0]-30:center[0,0]+30]
            xbar, ybar, Ixx, Iyy, Ixy = moments(thumb)

            params = lmfit.Parameters()
            params.add('fwhm_x', value=numpy.sqrt(Ixx))
            params.add('fwhm_y', value=numpy.sqrt(Iyy))
            params.add('beta', value=2.5)
            params.add('peak', value=thumb.max())
            params.add('x0', xbar)
            params.add('y0', ybar)

            def resid(p):
                xs, ys = numpy.meshgrid(numpy.arange(thumb.shape[1]), numpy.arange(thumb.shape[0]))
                return (thumb - moffat2d(p)(ys, xs)).flatten()
            result = lmfit.minimize(resid, params)
            values[i] = (result.params['fwhm_x'].value,
                         result.params['fwhm_y'].value,
                         result.params['beta'].value)
            i += 1

    print mono_wave
    outstring = 'fwhm_x = {:5.3f} +/- {:5.3f}, ' \
      + 'fwhm_y = {:5.3f} +/- {:5.3f}, ' \
      + 'beta = {:5.3f} +/- {:5.3f}'
    outstring = outstring.format(numpy.mean(values['fwhm_x']), numpy.std(values['fwhm_x']),
                                 numpy.mean(values['fwhm_y']), numpy.std(values['fwhm_y']),
                                 numpy.mean(values['beta']), numpy.std(values['beta']))
    print outstring
    return (numpy.mean(values['fwhm_x']), numpy.mean(values['fwhm_y']), numpy.mean(values['beta']),
            numpy.std(values['fwhm_x']), numpy.std(values['fwhm_y']), numpy.std(values['beta']))

# start script

waves = {'u': numpy.arange(325, 401, 25),
         'g': numpy.arange(400, 551, 25),
         'r': numpy.arange(550, 701, 25),
         'i': numpy.arange(675, 826, 25),
         'z': numpy.arange(800, 951, 25),
         'Y': numpy.arange(900, 1100, 25)}
colors = {'u':'violet',
          'g':'blue',
          'r':'green',
          'i':'yellow',
          'z':'red',
          'Y':'black'}

nfiles = sum(map(len, waves.values()))

values = numpy.empty(nfiles,
                     dtype=[('wave', 'i4'),
                            ('filter', 'a1'),
                            ('fwhm_x', 'f4'),
                            ('fwhm_y', 'f4'),
                            ('beta', 'f4'),
                            ('fwhm_x_err', 'f4'),
                            ('fwhm_y_err', 'f4'),
                            ('beta_err', 'f4')])
values[:] = numpy.nan

i = 0
for f, ws in waves.iteritems():
    for w in ws:
        result = measure_moffat_fwhm(1, w, f, 0, 1000)
        values[i] = (w, f,
                     result[0], result[1], result[2],
                     result[3], result[4], result[5])
        i += 1

# ignore 500nm beta since spectrum here is wrong.
values['beta'][values['wave'] == 500] = numpy.nan

# fwhm plot
fig = plt.figure()
ax = plt.subplot(111)
for k in waves.keys():
    ind = values['filter'] == k
    ax.errorbar(values[ind]['wave'], values[ind]['fwhm_x'], values[ind]['fwhm_x_err'],
                ls='none', marker='o', color=colors[k])
    ax.errorbar(values[ind]['wave'], values[ind]['fwhm_y'], values[ind]['fwhm_y_err'],
                ls='none', marker='o', color=colors[k])
ax.set_xlabel('wavelength (nm)')
ax.set_ylabel('FWHM (pixels)')

x=numpy.linspace(300, 1100, 100)
y=values[numpy.where(values['wave'] == 550)[0][0]]['fwhm_x'] * (x/550.)**(-0.2)
ax.plot(x, y)
plt.show()

# beta plot
fig2 = plt.figure()
ax = plt.subplot(111)
for k in waves.keys():
    ind = values['filter'] == k
    ax.errorbar(values[ind]['wave'], values[ind]['beta'], values[ind]['beta_err'],
                ls='none', marker='o', color=colors[k])
ax.set_xlabel('wavelength (nm)')
ax.set_ylabel(r'$\beta$')
plt.show()

# telescopemode 0 analysis
#---------------------------------------------------------------------------------------------------
values = numpy.empty(nfiles,
                     dtype=[('wave', 'i4'),
                            ('filter', 'a1'),
                            ('fwhm_x', 'f4'),
                            ('fwhm_y', 'f4'),
                            ('beta', 'f4'),
                            ('fwhm_x_err', 'f4'),
                            ('fwhm_y_err', 'f4'),
                            ('beta_err', 'f4')])
values[:] = numpy.nan

i = 0
for f, ws in waves.iteritems():
    for w in ws:
        result = measure_moffat_fwhm(2, w, f, 0, 1000)
        values[i] = (w, f,
                     result[0], result[1], result[2],
                     result[3], result[4], result[5])
        i += 1

# ignore 500nm beta since spectrum here is wrong.
values['beta'][values['wave'] == 500] = numpy.nan

# fwhm plot
fig = plt.figure()
ax = plt.subplot(111)
ax.set_title('telescopemode 0')
for k in waves.keys():
    ind = values['filter'] == k
    ax.errorbar(values[ind]['wave'], values[ind]['fwhm_x'], values[ind]['fwhm_x_err'],
                ls='none', marker='o', color=colors[k])
    ax.errorbar(values[ind]['wave'], values[ind]['fwhm_y'], values[ind]['fwhm_y_err'],
                ls='none', marker='o', color=colors[k])
ax.set_xlabel('wavelength (nm)')
ax.set_ylabel('FWHM (pixels)')

x=numpy.linspace(300, 1100, 100)
y=values[numpy.where(values['wave'] == 550)[0][0]]['fwhm_x'] * (x/550.)**(-0.2)
ax.plot(x, y)
plt.show()

# beta plot
fig2 = plt.figure()
ax = plt.subplot(111)
ax.set_title('telescopemode 0')
for k in waves.keys():
    ind = values['filter'] == k
    ax.errorbar(values[ind]['wave'], values[ind]['beta'], values[ind]['beta_err'],
                ls='none', marker='o', color=colors[k])
ax.set_xlabel('wavelength (nm)')
ax.set_ylabel(r'$\beta$')
plt.show()

# loop over different atmospheres
#---------------------------------------------------------------------------------------------------
values = numpy.empty(100,
                     dtype=[('fwhm_x', 'f4'),
                            ('fwhm_y', 'f4')])
values[:] = numpy.nan

i = 0
for sd in numpy.arange(1000, 1100):
    print i
    result = measure_moffat_fwhm(1, 600, 'r', 0, sd)
    values[i] = (result[0], result[1])
    i += 1

# fwhm_x vs fwhm_y plot
fig = plt.figure()
ax = plt.subplot(111)
ax.scatter(values['fwhm_x'], values['fwhm_y'])
ax.set_xlabel('x FWHM (pixels)')
ax.set_ylabel('y FWHM (pixels)')
ax.plot([numpy.nanmin(values['fwhm_x']), numpy.nanmax(values['fwhm_x'])],
        [numpy.nanmin(values['fwhm_x']), numpy.nanmax(values['fwhm_x'])])
plt.show()