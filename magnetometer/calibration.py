"""Calibration scripts for University of Glasgow Observatory magnetometer"""

# conversion factors for each channel
CONVERSION = []

def set_conversion(factors):
    global CONVERSION

    CONVERSION = list(factors)

def scale_counts_to_volts(sample_values):
    return [int(sample) * factor
            for sample, factor in zip(sample_values, CONVERSION)]

def scale_volts_to_nt_and_degrees(sample_values):
    """Scales voltages from magnetometer to nanotesla and degrees

    Based on Matlab code by Hugh Potts.
    """

    if len(sample_values) is not 4:
        raise Exception("There must be 4 samples specified")

    # wire resistance between magnetometer and A/D
    r_wires = 2.48

    # input resistance seen by signal
    r_in = 10000

    # potential divider fraction for up-down field
    pot_div_fraction = 3.01 / (6.98 + 3.01)

    # nanotesla per volt scale
    b_scale = 1e6 / 143

    # temperature sensor degrees per volt, based on LM35's 10mV / degC
    t_scale = 100

    ###
    # Scale voltages to nanotesla.
    #
    # Need to take into account the voltage drop in the wires. This not only
    # reduces the apparent voltage but also introduces crosstalk between the
    # channels.
    #
    # v_true = v_measured(1 + r_wires / r_in) + sum(v_measured) * r_wires / r_in

    # first we need to multiply up the z channel (3th item in list) to its true
    # value
    sample_values[2] = sample_values[2] / pot_div_fraction

    # sum up measured voltages
    v_measured_sum = sum(sample_values)

    # channel voltage correction factor
    v_measured_correction = v_measured_sum * r_wires / r_in

    # sample correction
    v_sample_correction = [value * (1 + r_wires / r_in)
                           for value in sample_values]

    # corrected voltages
    v_corrected = [v_sample + v_measured_correction
                   for v_sample in v_sample_correction]

    # now convert to physical units
    v_corrected[0:3] = [v * b_scale for v in v_corrected[0:3]]
    v_corrected[3] = v_corrected[3] * t_scale

    # return calibrated values
    return v_corrected
