import numpy as np
import pandas as pd
from astropy.io import fits

with fits.open(r'C:\Users\fatem\LALInference_v2.fits.gz') as hdul:
    data = hdul[1].data
    prob = np.array(data['PROB']).byteswap().view(np.float64)
    nside = int(hdul[1].header['NSIDE'])

print(f"Original NSIDE: {nside}, NPIX: {len(prob)}")

# Downsample to lower resolution (bigger pixels)
nside_new = 32  # much coarser resolution, bigger tiles
npix_new = 12 * nside_new * nside_new

# Sum probabilities into coarser pixels
ratio = (nside // nside_new) ** 2
prob_coarse = np.array([
    prob[i*ratio:(i+1)*ratio].sum()
    for i in range(npix_new)
])

print(f"New NSIDE: {nside_new}, NPIX: {len(prob_coarse)}")

# Now convert coarse pixels to RA/Dec using RING scheme
# At nside=32 it's small enough to be roughly RING-like
npix = len(prob_coarse)
indices = np.arange(npix)
ncap = 2 * nside_new * (nside_new - 1)

theta = np.zeros(npix)
phi = np.zeros(npix)

# North polar cap
mask = indices < ncap
ip = indices[mask]
i = (np.sqrt(ip / 2.0 + 0.5)).astype(int) + 1
j = ip - 2 * i * (i - 1)
theta[mask] = np.arccos(1 - i**2 / (3 * nside_new**2))
phi[mask] = (j + 0.5) * np.pi / (2 * i)

# Equatorial
mask = (indices >= ncap) & (indices < npix - ncap)
ip = indices[mask]
i = (ip - ncap) // (4 * nside_new) + nside_new
j = (ip - ncap) % (4 * nside_new)
s = (i - nside_new + 1) % 2
theta[mask] = np.arccos((2 - i / nside_new) * 2 / 3)
phi[mask] = (j + s / 2.0) * np.pi / (2 * nside_new)

# South polar cap
mask = indices >= npix - ncap
ip = npix - indices[mask] - 1
i = (np.sqrt(ip / 2.0 + 0.5)).astype(int) + 1
j = ip - 2 * i * (i - 1)
theta[mask] = np.arccos(-1 + i**2 / (3 * nside_new**2))
phi[mask] = (j + 0.5) * np.pi / (2 * i)

ra = np.degrees(phi)
dec = 90 - np.degrees(theta)

df = pd.DataFrame({'ra': ra, 'dec': dec, 'prob': prob_coarse})
df = df.nlargest(500, 'prob')

# Normalise so probabilities sum to 1
df['prob'] = df['prob'] / df['prob'].sum()

df.to_csv(r'C:\Users\fatem\PycharmProjects\PythonProject\tests\gw170817_skymap.csv', index=False)
print(f'Saved {len(df)} tiles')
print(f'RA range: {df.ra.min():.1f} to {df.ra.max():.1f}')
print(f'Dec range: {df.dec.min():.1f} to {df.dec.max():.1f}')