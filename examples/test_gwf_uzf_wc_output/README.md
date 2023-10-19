test_gwf_uzf_wc_output tests
-------------------------

These tests are based on test_gwf_uzf_wc_output but are modified to increase the GHB
maxbound dimension to 3. This is just to show that in this case the related
set of list based dynamic input parameters behave in the same way wrt bound and 
MODFLOW 6 input processing establishes nbound by reading each up to DNODATA for each
period.
