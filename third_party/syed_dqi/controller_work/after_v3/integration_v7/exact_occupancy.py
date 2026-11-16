# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Exact adaptive64 expectations without decimalizing large integers.

This reader consumes the completed, hash-bound finite occupancy certificate.
It does not rerun that calculation, generate a random draw, or import native
arithmetic. Large dyadic numerators remain hexadecimal in every JSON record.
"""
from fractions import Fraction
from functools import cache
import hashlib
import json
from v7_paths import ROOT, PROJECT

CERTIFICATE = PROJECT/'k24/runs/adaptive-gauge-occupancy/paper_certificate.json'
CERTIFICATE_SHA = 'baa51690dae289f4bba81e53ca98c8c9db420a13dbd74f4c00beb281a9c4b627'
CALCULATOR = PROJECT/'k24/adaptive_gauge_occupancy.py'
CALCULATOR_SHA = '623203e26d18c0579e723f687cc85279f1c924cb641e533e4f1a15952ea021cd'
V6_FULL_MEAN = Fraction(13165890612252429,34359738368)
OLD_SCAN_STATIC = 44275
NEW_SCAN_STATIC = 44286


def require(condition, message):
    if not condition:
        raise ValueError(message)


def _scaled_decimal(integer, digits):
    """Only a small, already-divided display integer is converted to text."""
    sign = '-' if integer < 0 else ''
    value = abs(integer)
    whole, remainder = divmod(value,10**digits)
    return sign+str(whole)+'.'+str(remainder).zfill(digits)


def encode(value, digits=12):
    value = Fraction(value)
    denominator = value.denominator
    require(denominator > 0 and denominator & (denominator-1) == 0,
            'The exact ledger must be dyadic')
    require(type(digits) is int and 1 <= digits <= 24, 'Invalid display precision')
    scale = 10**digits
    lower = value.numerator*scale//denominator
    upper = -((-value.numerator*scale)//denominator)
    require(abs(lower).bit_length() < 256 and abs(upper).bit_length() < 256,
            'Unexpected display magnitude')
    return dict(numerator_hex=hex(value.numerator),
                denominator_power_of_two=denominator.bit_length()-1,
                decimal_lower=_scaled_decimal(lower,digits),
                decimal_upper=_scaled_decimal(upper,digits),
                directed_decimal_digits=digits)


def decode(row):
    require(isinstance(row,dict), 'Expected an exact dyadic object')
    text, exponent = row['numerator_hex'], row['denominator_power_of_two']
    require(isinstance(text,str) and 3 <= len(text) <= 13000,
            'Invalid or oversized hexadecimal numerator')
    require(type(exponent) is int and 0 <= exponent <= 50000,
            'Invalid power-of-two denominator')
    integer = int(text,16)
    require(hex(integer) == text, 'Noncanonical hexadecimal numerator')
    value = Fraction(integer,1 << exponent)
    lower,upper = row['decimal_lower'],row['decimal_upper']
    digits = row['directed_decimal_digits']
    require(isinstance(lower,str) and isinstance(upper,str)
            and len(lower) < 96 and len(upper) < 96
            and type(digits) is int and 1 <= digits <= 24,
            'Invalid directed decimal bounds')
    lo,hi = Fraction(lower),Fraction(upper)
    require(lo <= value <= hi and hi-lo <= Fraction(1,10**digits),
            'The displayed interval does not enclose its exact value')
    return value


@cache
def certificate_values():
    raw = CERTIFICATE.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == CERTIFICATE_SHA,
            'The completed occupancy certificate changed')
    require(hashlib.sha256(CALCULATOR.read_bytes()).hexdigest() == CALCULATOR_SHA,
            'The certified occupancy calculator changed')
    report = json.loads(raw)
    require(report['format'] == 'DQI_ADAPTIVE_GAUGE_CAPPED_OCCUPANCY_V1'
            and report['status'] == 'EXACT_FINITE_OCCUPANCY_PAPER_CERTIFICATE_NOT_NATIVE'
            and report['source_sha256'] == CALCULATOR_SHA,
            'Wrong occupancy certificate identity')
    require((report['q'],report['independent_residual_labels'],report['cap'],
             report['fixed_zero_pivot_labels']) == (4096,4025,7,1)
            and report['zero_first_tie_policy'] is True
            and report['all_input_pointwise_no_T_loss'] is True
            and report['exact_modal_selector'] is False
            and report['admission_changed'] is False,
            'Wrong capped64 occupancy law')
    require(all(report[key] == 0 for key in
                ('native_builds','native_simulations','population_census_runs',
                 'project_imports','sampler_draws')),
            'The exact finite calculation is not native or population evidence')
    selected = [row for row in report['rows'] if row['candidates'] == 64]
    require(len(selected) == 1 and selected[0]['cap'] == 7, 'Missing unique capped64 result')
    row = selected[0]
    old = decode(report['old_scan_mean_T'])
    new = decode(row['exact_new_scan_mean_T'])
    gain = decode(row['exact_expected_T_saving'])
    zeros = decode(row['exact_expected_additional_zeros'])
    require(old == Fraction(OLD_SCAN_STATIC*4095,4096)
            and old-new == gain == 11*zeros and gain > 0,
            'The occupancy gain and scan expectation do not reconcile')
    require(row['exact_expected_T_saving']['decimal_lower'] == '21.650726134792'
            and row['exact_expected_T_saving']['decimal_upper'] == '21.650726134793',
            'Unexpected selected exact gain')
    return old,new,gain


def binding():
    old,new,gain = certificate_values()
    return dict(certificate=str(CERTIFICATE.relative_to(ROOT)),
                certificate_sha256=CERTIFICATE_SHA,
                calculator=str(CALCULATOR.relative_to(ROOT)),
                calculator_sha256=CALCULATOR_SHA,
                q=4096,independent_residual_labels=4025,virtual_zero_pivots=1,
                candidates=64,cap=7,first_strict_maximum=True,
                old_scan_static_T=OLD_SCAN_STATIC,new_scan_static_T=NEW_SCAN_STATIC,
                old_scan_mean_T_exact=encode(old),
                new_scan_mean_T_exact=encode(new),
                expected_T_saving_exact=encode(gain),
                expected_full_v7_mean_T_exact=encode(V6_FULL_MEAN-gain),
                measured_official_gain=None,new_population_draws=0,
                scope='Exact finite uniform-mask expectation; the correlated point masks are not independent.')
