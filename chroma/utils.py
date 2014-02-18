import numpy as np

import astropy.utils.console

def Sersic_r2_over_hlr(n):
    """ Factor to convert the half light radius `hlr` to the 2nd moment radius `r^2` defined as
    sqrt(Ixx + Iyy) where Ixx and Iyy are the second central moments of a distribution in
    perpendicular directions.  Depends on the Sersic index n.  The polynomial below is derived from
    a Mathematica fit to the exact relation, and should be good to ~(0.01 - 0.04)% over the range
    0.2 < n < 8.0.

    @param n Sersic index
    @returns ratio r^2  / hlr
    """
    return 0.98544 + n * (0.391015 + n * (0.0739614 + n * (0.00698666 + n * (0.00212443 + \
                     n * (-0.000154064 + n * 0.0000219636)))))

def component_Sersic_r2(ns, weights, hlrs):
    """ Calculate second moments of concentric multi-Sersic galaxy.

    @param  ns       List of Sersic indices in model.
    @param  weights  Relative flux of each component
    @param  hrls     List of half-light-radii of each component
    @returns         Second moment radius.
    """
    t = np.array(weights).sum()
    ws = [w / t for w in weights]
    r2s = [Sersic_r2_over_hlr(n) * r_e for n, r_e in zip(ns, r_es)]
    return np.sqrt(reduce(lambda x,y:x*y, [r2**2 * w for r2, w in zip(r2s, ws)]))

def apply_shear(c_ellip, c_gamma):
    """Compute complex ellipticity after shearing by complex shear `c_gamma`."""
    return (c_ellip + c_gamma) / (1.0 + c_gamma.conjugate() * c_ellip)

def ringtest(gamma, n_ring, gen_target_image, gen_init_param, measure_ellip, silent=False,
             diagnostic=None):
    """ Performs a shear calibration ringtest.

    Produces "true" images uniformly spread along a ring in ellipticity space using the supplied
    `gen_target_image` function.  Then tries to fit these images, (returning ellipticity estimates)
    using the supplied `measure_ellip` function with the fit initialized by the supplied
    `gen_init_param` function.

    The "true" images are sheared by `gamma` (handled by passing through to `gen_target_image`).
    Images are generated in pairs separated by 180 degrees on the ellipticity plane to minimize shape
    noise.

    Ultimately returns an estimate of the applied shear (`gamma_hat`), which can then be compared to
    the input shear `gamma` in an external function to estimate shear calibration parameters.
    """

    betas = np.linspace(0.0, 2.0 * np.pi, n_ring, endpoint=False)
    ellip0s = []
    ellip180s = []

    def work():
        #measure ellipticity at beta along the ring
        target_image0 = gen_target_image(gamma, beta, diagnostic)
        init_param0 = gen_init_param(gamma, beta)
        ellip0 = measure_ellip(target_image0, init_param0, diagnostic)
        ellip0s.append(ellip0)

        #repeat with beta on opposite side of the ring (i.e. +180 deg)
        target_image180 = gen_target_image(gamma, beta + np.pi, diagnostic)
        init_param180 = gen_init_param(gamma, beta + np.pi)
        ellip180 = measure_ellip(target_image180, init_param180, diagnostic)
        ellip180s.append(ellip180)

    # Use fancy console updating if astropy is installed and not silenced
    if not silent:
        try:
            import astropy.utils.console
            with astropy.utils.console.ProgressBar(n_ring) as bar:
                for beta in betas:
                    work()
                    bar.update()
        except:
            for beta in betas:
                work()
    else:
        for beta in betas:
            work()

    gamma_hats = [0.5 * (e0 + e1) for e0, e1 in zip(ellip0s, ellip180s)]
    gamma_hat = np.mean(gamma_hats)
    return gamma_hat

def moments(image):
    """Compute first and second (quadrupole) moments of `image`.  Scales result for non-unit width
    pixels.

    @param image   galsim.Image to analyze
    @returns       x0, y0, Ixx, Iyy, Ixy - first and second moments of image.
    """
    data = image.array
    scale = image.scale
    xs, ys = np.meshgrid(np.arange(data.shape[0], dtype=np.float64) * scale,
                            np.arange(data.shape[0], dtype=np.float64) * scale)
    total = data.sum()
    xbar = (data * xs).sum() / total
    ybar = (data * ys).sum() / total
    Ixx = (data * (xs-xbar)**2).sum() / total
    Iyy = (data * (ys-ybar)**2).sum() / total
    Ixy = (data * (xs - xbar) * (ys - ybar)).sum() / total
    return xbar, ybar, Ixx, Iyy, Ixy

def my_imshow(im, ax=None, **kwargs):
    import matplotlib.pyplot as plt
    if ax is None:
        ax = plt.gca()
    def format_coord(x, y):
        x = int(x + 0.5)
        y = int(y + 0.5)
        try:
            return '%8e @ [%4i, %4i]' % (im[y, x], x, y)
        except IndexError:
            return ''
    img = ax.imshow(im, **kwargs)
    ax.format_coord=format_coord
    return img

# def FWHM(data, pixsize=1.0):
#     """Compute the full-width at half maximum of a symmetric 2D distribution.  Assumes that measuring
#     along the x-axis is sufficient (ignores all but one row, the one containing the distribution
#     maximum).  Scales result by `pixsize` for non-unit width pixels.

#     Arguments
#     ---------
#     data -- array to analyze
#     pixsize -- linear size of a pixel
#     """
#     height = data.max()
#     w = np.where(data == height)
#     y0, x0 = w[0][0], w[1][0]
#     xs = np.arange(data.shape[0], dtype=np.float64) * pixsize
#     low = np.interp(0.5*height, data[x0, 0:x0], xs[0:x0])
#     high = np.interp(0.5*height, data[x0+1, -1:x0:-1], xs[-1:x0:-1])
#     return abs(high-low)

# def AHM(data, pixsize=1.0, height=None):
#     """ Compute area above half maximum as a potential replacement for FWHM.

#     Arguments
#     ---------
#     data -- array to analyze
#     pixsize -- linear size of a pixel
#     height -- optional maximum height of data (defaults to sample maximum).
#     """
#     if height is None:
#         height = data.max()
#     return (data > (0.5 * height)).sum() * scale**2
