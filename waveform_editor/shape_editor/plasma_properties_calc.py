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


def tf_turns(tf):
    """The number of turns of all TF coils together, N_coils * N_turns.

    Args:
        tf: The tf machine description IDS.
    """
    if tf.is_periodic == 1:
        return tf.coils_n * tf.coil[0].turns
    return sum(coil.turns for coil in tf.coil)


def toroidal_field(tf, current, r):
    """The vacuum toroidal field B(R) = μ0 / (2πR) * N_coils * N_turns * I_tor.

    Args:
        tf: The tf machine description IDS.
        current: The current in each TF coil turn [A].
        r: The major radius to compute the field at [m].
    """
    return scipy.constants.mu_0 * tf_turns(tf) * current / (2 * np.pi * r)


def tf_current(tf, b0, r):
    """The current in each TF coil turn that gives toroidal field ``b0`` at ``r``.

    Args:
        tf: The tf machine description IDS.
        b0: The vacuum toroidal field [T].
        r: The major radius of the field [m].
    """
    return b0 * 2 * np.pi * r / (scipy.constants.mu_0 * tf_turns(tf))
