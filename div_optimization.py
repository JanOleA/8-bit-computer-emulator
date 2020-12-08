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
    
    bloops = loopcounts
    ifs = 0
    while pow2 > 0:
        if a >= b: # if a >= b, b fits into a (2^x) times
            quotient += pow2
            a -= b    # and this is the remainder
            ifs += 1

        b = b//2  # divide b by 2
        pow2 = pow2//2 # and we check (2^(x - 1)) next

        loopcounts += 1

    remainder = a

    print(quotient, remainder, ifs, bloops)

    return quotient, remainder

divide_new(103, 7)
divide_new(78, 3)
divide_new(32, 9)
divide_new(20, 10)

def test_dividers():
    for a in range(2000):
        for b in range(1, min(100, a)):
            expected_quotient = a//b
            expected_remainder = a%b

            new_quot, new_rem = divide_new(a, b)

            assert new_quot == expected_quotient
            assert new_rem == expected_remainder


