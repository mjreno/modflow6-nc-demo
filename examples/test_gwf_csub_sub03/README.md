test_gwf_csub_sub03 tests
-------------------------

These tests are based on test_gwf_csub_sub03 but are modified to add additional period blocks.
The relevant code change in the test script is copied here:

```
# recharge data
q = 3000.0 / (delr * delc)
v = np.zeros((nrow, ncol), dtype=float)
v2 = np.zeros((nrow, ncol), dtype=float)
for r, c in zip(wr, wc):
    v[r, c] = q
rech = {0: v, 4: v2, 7: v}
```
The intent is to clear rechage data at period 5 and then reset back to original state at period 8.
These changes are not meant to be meaningful from a modeling perspective, but rather only to test
for consistency changing and reloading recharge array data during the progression of the simulation.
These changes are directly comparable for both the ASCII and netcdf tests in this directory.
