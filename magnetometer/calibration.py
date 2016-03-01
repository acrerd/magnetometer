from __future__ import print_function, division

"""Calibration scripts for University of Glasgow Observatory magnetometer"""

def scale_magnetometer_data(readings):
    """Scales voltages from magnetometer to nanotesla and degrees

    Based on Matlab code by Hugh Potts.
    """

    if len(readings) is not 4:
        raise Exception("Readings must be an iterable with 4 items")

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
    readings[2] = readings[2] / pot_div_fraction

    # sum up measured voltages
    v_measured_sum = sum(readings)

    # channel voltage correction factor
    v_measured_correction = v_measured_sum * r_wires / r_in

    # readings correction
    v_reading_correction = [reading * (1 + r_wires / r_in) \
    for reading in readings]

    # corrected voltages
    v_corrected = [v_reading + v_measured_correction \
    for v_reading in v_reading_correction]

    # now convert to physical units
    v_corrected[0:3] = [v * b_scale for v in v_corrected[0:3]]
    v_corrected[3] = v_corrected[3] * t_scale

    # return calibrated data
    return v_corrected
