import cPickle

import numpy as np
import matplotlib.pyplot as plt

import _mypath
import chroma

hist_axes_range = [0.19, 0.15, 0.1, 0.8]
scatter_axes_range = [0.29, 0.15, 0.5, 0.8]
colorbar_axes_range = [0.82, 0.15, 0.04, 0.8]

def hist_with_peak(x, bins=None, range=None, ax=None, orientation='vertical',
                   histtype=None, **kwargs):
    if ax is None:
        ax = plt.gca()
    hist, bin_edges = np.histogram(x, bins=bins, range=range)
    hist_n = hist * 1.0/hist.max()
    width = bin_edges[1] - bin_edges[0]
    x = np.ravel(zip(bin_edges[:-1], bin_edges[:-1]+width))
    y = np.ravel(zip(hist_n, hist_n))
    if histtype == 'step':
        if orientation == 'vertical':
            plt.plot(x, y, **kwargs)
        elif orientation == 'horizontal':
            plt.plot(y, x, **kwargs)
        else:
            raise ValueError
    elif histtype == 'stepfilled':
        if orientation == 'vertical':
            plt.fill(x, y, **kwargs)
        elif orientation == 'horizontal':
            plt.fill(y, x, **kwargs)
        else:
            raise ValueError
    else:
        raise ValueError

def set_range(x):
    xs = sorted(x)
    n = len(xs)
    low = xs[int(0.005*n)]
    high = xs[int(0.995*n)]
    span = high-low
    return [low - 0.3*span, high + 0.3*span]

def R_vs_redshift(gals, stars, band, cband1, cband2, **kwargs):
    data_dir = '../../data/'
    filter_file = data_dir+'filters/{}.dat'.format(band)
    star_SED_file = data_dir+'SEDs/ukg5v.ascii'
    swave, sphotons = chroma.utils.get_photons(star_SED_file, filter_file, 0.0)
    smom = chroma.disp_moments(swave, sphotons, zenith=np.pi/6)
    R0 = smom[0] * 180/np.pi * 3600

    f = plt.figure(figsize=(8, 5))

    # scatter plot
    ax = f.add_axes(scatter_axes_range)
    x = gals.redshift
    y = gals['R'][band] * np.tan(np.pi/6) * 180/np.pi * 3600 - R0
    c = gals['magCalc'][cband1] - gals['magCalc'][cband2]
    clim = set_range(c)
    clim[1] += 0.1 * (clim[1]-clim[0])
    im = ax.scatter(x, y, c=c, vmin=clim[0], vmax=clim[1], zorder=4, **kwargs)
    ax.set_xlabel('redshift', fontsize=18)
    ax.yaxis.set_ticklabels([])
    xlim = (0,3)
    ax.set_xlim(xlim)
    ylim = set_range(y)
    ax.set_ylim(ylim)
    ax.fill_between(xlim, [ylim[0]]*2, [ylim[1]]*2, color='#AAAAAA', zorder=1)
    for label in ax.get_xticklabels():
        label.set_fontsize(18)
    # requirements
    ax.fill_between(xlim, [-0.025]*2, [0.025]*2, color='#999999', zorder=2)
    ax.fill_between(xlim, [-0.01]*2, [0.01]*2, color='#888888', zorder=3)

    # star histogram
    hist_ax = f.add_axes(hist_axes_range)
    hist_with_peak(stars['R'][band] * np.tan(np.pi/6) * 180/np.pi * 3600 - R0, bins=200,
                   range=ylim, orientation='horizontal', histtype='stepfilled', color='blue')
    hist_ax.xaxis.set_ticklabels([])
    hist_ax.set_ylim(ylim)
    xlim = hist_ax.get_xlim()
    hist_ax.set_xlim(xlim)
    hist_ax.fill_between(xlim, [ylim[0]]*2, [ylim[1]]*2, color='white', zorder=1)
    hist_ax.set_ylabel('$\Delta$ PSF centroid (arcsec)', fontsize=18)
    hist_with_peak(gals['R'][band] * np.tan(np.pi/6) * 180/np.pi * 3600 - R0, bins=200,
                   range=ylim, orientation='horizontal', histtype='step', color='red')
    hist_ax.text(xlim[0] + (xlim[1]-xlim[0])*0.2, ylim[1] - (ylim[1]-ylim[0])*0.08,
                 'stars', fontsize=18, color='blue')
    hist_ax.text(xlim[0] + (xlim[1]-xlim[0])*0.2, ylim[1] - (ylim[1]-ylim[0])*0.16,
                 'gals', fontsize=18, color='red')
    for label in hist_ax.get_yticklabels():
        label.set_fontsize(18)

    # colorbar
    cbar_ax = f.add_axes(colorbar_axes_range)
    cbar = plt.colorbar(im, cax=cbar_ax)
    cbar_ax.set_ylabel('{} - {}'.format(cband1.replace('LSST_',''), cband2.replace('LSST_','')), fontsize=18)
    for label in cbar_ax.get_yticklabels():
        label.set_fontsize(18)

    f.savefig('output/dR_z_stars.{}.png'.format(band), dpi=300)

def V_vs_redshift(gals, stars, band, cband1, cband2, **kwargs):
    data_dir = '../../data/'
    filter_file = data_dir+'filters/{}.dat'.format(band)
    star_SED_file = data_dir+'SEDs/ukg5v.ascii'
    swave, sphotons = chroma.utils.get_photons(star_SED_file, filter_file, 0.0)
    smom = chroma.disp_moments(swave, sphotons, zenith=np.pi/6)
    V0 = smom[1] * (180/np.pi * 3600)**2

    f = plt.figure(figsize=(8, 5))

    # scatter plot
    ax = f.add_axes(scatter_axes_range)
    x = gals.redshift
    y = gals['V'][band] * (np.tan(np.pi/6) * 180/np.pi * 3600)**2 - V0
    c = gals['magCalc'][cband1] - gals['magCalc'][cband2]
    clim = set_range(c)
    im = ax.scatter(x, y, c=c, vmin=clim[0], vmax=clim[1], zorder=4, **kwargs)
    ax.set_xlabel('redshift', fontsize=18)
    ax.yaxis.set_ticklabels([])
    xlim = (0,3)
    ax.set_xlim(xlim)
    ylim = set_range(y)
    ax.set_ylim(ylim)
    ax.fill_between(xlim, [ylim[0]]*2, [ylim[1]]*2, color='#AAAAAA', zorder=1)
    for label in ax.get_xticklabels():
        label.set_fontsize(18)
    # requirements
    ax.fill_between(xlim, [-0.0006]*2, [0.0006]*2, color='#999999', zorder=2)
    ax.fill_between(xlim, [-0.0001]*2, [0.0001]*2, color='#888888', zorder=3)

    # star histogram
    hist_ax = f.add_axes(hist_axes_range)
    hist_with_peak(stars['V'][band] * (np.tan(np.pi/6) * 180/np.pi * 3600)**2 - V0, bins=200,
                   range=ylim, orientation='horizontal', histtype='stepfilled', color='blue')
    hist_ax.xaxis.set_ticklabels([])
    hist_ax.set_ylim(ylim)
    xlim = hist_ax.get_xlim()
    hist_ax.set_xlim(xlim)
    hist_ax.fill_between(xlim, [ylim[0]]*2, [ylim[1]]*2, color='white', zorder=1)
    hist_ax.set_ylabel('$\Delta$ PSF second moment (arcsec$^2$)', fontsize=18)
    hist_with_peak(gals['V'][band] * (np.tan(np.pi/6) * 180/np.pi * 3600)**2 - V0, bins=200,
                   range=ylim, orientation='horizontal', histtype='step', color='red')
    hist_ax.text(xlim[0] + (xlim[1]-xlim[0])*0.2, ylim[1] - (ylim[1]-ylim[0])*0.08,
                 'stars', fontsize=18, color='blue')
    hist_ax.text(xlim[0] + (xlim[1]-xlim[0])*0.2, ylim[1] - (ylim[1]-ylim[0])*0.16,
                 'gals', fontsize=18, color='red')
    # hist_ax.ticklabel_format(style='sci', axis='y', scilimits=(0,0))
    for label in hist_ax.get_yticklabels():
        label.set_fontsize(18)

    # colorbar
    cbar_ax = f.add_axes(colorbar_axes_range)
    cbar = plt.colorbar(im, cax=cbar_ax)
    cbar_ax.set_ylabel('{} - {}'.format(cband1.replace('LSST_',''), cband2.replace('LSST_','')), fontsize=18)
    for label in cbar_ax.get_yticklabels():
        label.set_fontsize(18)

    f.savefig('output/dV_z_stars.{}.png'.format(band), dpi=300)

def S_vs_redshift(gals, stars, band, cband1, cband2, n=-0.2, **kwargs):
    data_dir = '../../data/'
    filter_file = data_dir+'filters/{}.dat'.format(band)
    star_SED_file = data_dir+'SEDs/ukg5v.ascii'
    swave, sphotons = chroma.utils.get_photons(star_SED_file, filter_file, 0.0)
    S0 = chroma.relative_second_moment_radius(swave, sphotons, n=n)

    f = plt.figure(figsize=(8, 5))

    # scatter plot
    ax = f.add_axes(scatter_axes_range)
    x = gals.redshift
    if n == -0.2:
        data_field = 'S_m02'
    elif n == 0.6:
        data_field = 'S_p06'
    elif n == 1.0:
        data_field = 'S_p10'
    else:
        raise ValueError
    y = np.log(gals[data_field][band] / S0 )
    c = gals['magCalc'][cband1] - gals['magCalc'][cband2]
    clim = set_range(c)
    im = ax.scatter(x, y, c=c, vmin=clim[0], vmax=clim[1], zorder=4, **kwargs)
    ax.set_xlabel('redshift', fontsize=18)
    ax.yaxis.set_ticklabels([])
    xlim = (0,3)
    ax.set_xlim(xlim)
    ylim = set_range(y)
    ax.set_ylim(ylim)
    ax.fill_between(xlim, [ylim[0]]*2, [ylim[1]]*2, color='#AAAAAA', zorder=1)
    for label in ax.get_xticklabels():
        label.set_fontsize(18)
    # requirements
    if n == -0.2:
        ax.fill_between(xlim, [-0.0025]*2, [0.0025]*2, color='#999999', zorder=2)
        ax.fill_between(xlim, [-0.0004]*2, [0.0004]*2, color='#888888', zorder=3)
    elif n == 0.6:
        ax.fill_between(xlim, [-0.002]*2, [0.002]*2, color='#999999', zorder=2)
    elif n == 1.0:
        ax.fill_between(xlim, [-0.002]*2, [0.002]*2, color='#999999', zorder=2)
    else:
        raise ValueError

    # star histogram
    hist_ax = f.add_axes(hist_axes_range)
    hist_with_peak(np.log(stars[data_field][band] / S0), bins=200,
                   range=ylim, orientation='horizontal', histtype='stepfilled', color='blue')
    hist_ax.xaxis.set_ticklabels([])
    hist_ax.set_ylim(ylim)
    xlim = hist_ax.get_xlim()
    hist_ax.set_xlim(xlim)
    hist_ax.fill_between(xlim, [ylim[0]]*2, [ylim[1]]*2, color='white', zorder=1)
    hist_ax.set_ylabel('$\Delta$ PSF area / PSF area', fontsize=18)
    hist_with_peak(np.log(gals[data_field][band] / S0), bins=200,
                   range=ylim, orientation='horizontal', histtype='step', color='red')
    hist_ax.text(xlim[0] + (xlim[1]-xlim[0])*0.2, ylim[1] - (ylim[1]-ylim[0])*0.08,
                 'stars', fontsize=18, color='blue')
    hist_ax.text(xlim[0] + (xlim[1]-xlim[0])*0.2, ylim[1] - (ylim[1]-ylim[0])*0.16,
                 'gals', fontsize=18, color='red')
    for label in hist_ax.get_yticklabels():
        label.set_fontsize(18)

    # colorbar
    cbar_ax = f.add_axes(colorbar_axes_range)
    cbar = plt.colorbar(im, cax=cbar_ax)
    cbar_ax.set_ylabel('{} - {}'.format(cband1.replace('LSST_',''), cband2.replace('LSST_','')), fontsize=18)
    for label in cbar_ax.get_yticklabels():
        label.set_fontsize(18)

    f.savefig('output/dS_z_stars.{}.{}.png'.format(band, data_field), dpi=300)


if __name__ == '__main__':
    gals = cPickle.load(open('corrected_galaxy_data.pkl'))
    stars = cPickle.load(open('corrected_star_data.pkl'))
    R_vs_redshift(gals, stars, 'LSST_r', 'LSST_r', 'LSST_i', s=2)
    V_vs_redshift(gals, stars, 'LSST_r', 'LSST_r', 'LSST_i', s=2)
    S_vs_redshift(gals, stars, 'LSST_r', 'LSST_r', 'LSST_i', s=2)
    S_vs_redshift(gals, stars, 'Euclid_350', 'LSST_r', 'LSST_i', n=0.6, s=2)
