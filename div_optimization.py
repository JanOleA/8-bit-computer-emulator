""" Experiments for optimizing division """

from numpy.random import default_rng
import pytest
rng = default_rng()

def divide_new(a, b):
    quotient = 0
    pow2 = 1

    loopcounts = 0

    while b*2 <= a: # find the smallest b*(2^x) which is smaller than a
        b *= 2
        pow2 *= 2

        loopcounts += 1
    
    while pow2 > 0:
        if a >= b: # if a >= b, b fits into a (2^x) times
            quotient += pow2
            a -= b    # and this is the remainder

        b = b//2  # divide b by 2
        pow2 = pow2//2 # and we check (2^(x - 1)) next

        loopcounts += 1

    remainder = a

    return quotient, remainder

def test_dividers():
    vals = rng.integers(1, 100000, size = (1000,2))

    for val in vals:
        a = val[0]
        b = val[1]//100

        expected_quotient = a//b
        expected_remainder = a%b

        new_quot, new_rem = divide_new(a, b)

        assert new_quot == expected_quotient
        assert new_rem == expected_remainder

