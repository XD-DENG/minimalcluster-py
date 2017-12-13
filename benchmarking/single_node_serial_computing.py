import time

# A naive factorization method. Take integer 'n', return list of factors.
# Ref: https://eli.thegreenplace.net/2012/01/24/distributed-computing-in-python-with-multiprocessing
def example_factorize_naive(n):
    if n < 2:
        return []
    factors = []
    p = 2
    while True:
        if n == 1:
            return factors
        r = n % p
        if r == 0:
            factors.append(p)
            n = n / p
        elif p * p >= n:
            factors.append(n)
            return factors
        elif p > 2:
            p += 2
        else:
            p += 1
    assert False, "unreachable"


def make_nums(N):
    nums = [999999999999]
    for i in range(N):
        nums.append(nums[-1] + 2)
    return nums

N = 20000
big_ints = make_nums(N)

t_start = time.time()
result = map(example_factorize_naive, big_ints)
t_end = time.time()

print("[Single-Node Serial Computing (Single Core)] Lapse: {} seconds".format(t_end - t_start))