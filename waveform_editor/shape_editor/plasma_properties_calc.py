"""Pure calculations for plasma profiles, with no Panel dependency."""

import numpy as np
import scipy


def compute_profiles_from_params(r0, alpha, beta, gamma):
    """Compute plasma profiles from parametric inputs.

    Args:
        r0: Reference major radius [m].
        alpha: Alpha shape parameter.
        beta: Beta shape parameter.
        gamma: Gamma shape parameter.

    Returns:
        Tuple of (psi_norm, dpressure_dpsi, f_df_dpsi) numpy arrays.
    """
    psi_norm = np.linspace(0, 1, 50)
    dpressure_dpsi = beta / r0 * (1 - psi_norm**alpha) ** gamma
    mu_0 = scipy.constants.mu_0
    f_df_dpsi = (1 - beta) * mu_0 * r0 * (1 - psi_norm**alpha) ** gamma
    return psi_norm, dpressure_dpsi, f_df_dpsi
