
## Sample Problem to Tackle

We try to factorize some given big integers, using a naive factorization method.

```python
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
```

The big integers are generated using the codes below

```python
def make_nums(N):
    nums = [999999999999]
    for i in range(N):
        nums.append(nums[-1] + 2)
    return nums

N = 20000
big_ints = make_nums(N)
```


## Different Methods and Results

Serial computing using single processor (`single_node_serial_computing.py`): ~180 seconds

Parallel computing using multiple processors on a single machine (`single_node_multiprocessing.py`): ~47 seconds

minimalcluster - single node (4 processors X 1): ~47 seconds

minimalcluster - two node (4 processors X 2): ~26 seconds

minimalcluster - three node (4 processors X 3): ~19 seconds



## Specs

The benchmarking was done on three virtual machines on DigitalOcean.

### Network

Using the normal network connection among virtual machines. The ping time is about 0.35 to 0.40 ms.

### CPU Info

```
Architecture:          x86_64
CPU(s):                4
Vendor ID:             GenuineIntel
CPU family:            6
Model:                 85
Model name:            Intel(R) Xeon(R) Platinum 8168 CPU @ 2.70GHz
CPU MHz:               2693.658
```

### Software

- Python 2.7.5
- minimalcluster 0.1.0.dev5