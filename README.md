NetCDF4 for MODFLOW 6
=====================

This repository has been set up to provide a few NetCDF4 example files
in the context of existing MODFLOW 6 autotests for the purposes of review
and feedback.

Any part of this proposal is open to discussion and modification, feel
free to create a discussion or otherwise send feedback.

Examples are under the examples directory and the complimentary ASCII
examples are also there for comparison.  An additional ncdump file of
the *.nc* file has also been added to each netcdf run directory for
convenience- these are named with the extension *.nc.out*

A starting point for each example is to compare GWF model namefiles
for each paired ASCII and netcdf test.

File organization and purpose
-----------------------------

The example NetCDF files are intended to demonstrate their ability
to serve as Model input sources for packages that are already integrated
with IDM.

Basic assumptions:
* A NetCDF4 file describes inputs for a single Model
* The NetCDF4 input file can contain any information beyond modflow6
  specific input for the model, however the model input must
  be tagged with modflow6 attributes to be properly read and loaded.
* All MODFLOW 6 NetCDF4 inputs will have the extension ".nc", which
  will be reserved for netcdf files.
* Only one NetCDF4 input file will be supported per model.  This
  means that the same file name can be found multiple times in a model
  namefile packages block, and an error should result if more than one
  unique netcdf input file name appears in the block.
* Variable names are not inherently meaningful to MODFLOW 6.  Variable
  attributes drive the reading and loading of input.
* List based input is not aggregated into a single block of data as
  with ASCII based inputs but instead is considered the set of dynamic
  input parameters needed for that package.

MODFLOW 6 NetCDF attributes
---------------------------

Attributes are the primary mechanism enabling Model input to be correctly
read by MODFLOW 6. It is proposed that a well described set of file and
variable scoped attributes be defined to support this effort.  The names
and purposes described here are open for discussion. A common prefix for
all MODFLOW 6 NetCDF4 attributes is probably useful, and in these examples
the prefix "modflow6_" is used.  It is intended that the MODFLOW 6 NetCDF
supported attribute set can be extended as appropriate.

### Global attributes

File scoped attributes apply to all MODFLOW 6 variable input that also
use appropriate variable attributes.

| Attribute             |           Meaning             |     Example(s)         |
|-----------------------|-------------------------------|------------------------|
| modflow6_modeltype    | Type of MODFLOW 6 Model       | GWF6, GWT6             |
| modflow6_modelname    | Name of MODFLOW 6 Model       | "RCH", "MYMODEL"       |

### Variable attributes

These variable attributes describe input parameters for MODFLOW 6 input
processing.

| Attribute             |           Meaning             |     Example(s)              |        Comment
|-----------------------|-------------------------------|-----------------------------|-------------------------------------
| modflow6_component    | Variable component string     | "GWF/CHD", "GWF/RCHA"       | Could be replaced with modflow6_ptype (package type)
| modflow6_package      | Variable package name         | "CHD_0", "RCHA_0"           |
| modflow6_block        | Variable dfn block name       | "OPTIONS", "PERIOD"         |
| modflow6_param        | Variable dfn param tag        | "readasarrays", "head"      |
| modflow6_iper         | IPER package variable, size   | modflow6_iper = 3           | IPER array size 3, described below
| modflow6_griddata     | Griddata variable, size       | Lmodflow6_griddata = 3      | griddata variable, param IPER is size 3
| modflow6_param_iper   | IPER array for griddata var   | modflow6_param_iper = 1,5,8 | griddata param iper array, described below


MODFLOW 6 NetCDF iper variables
-------------------------------

The intent of iper variable is to reduce the amount of data written to the
NetCDF file.  IPER arrays provide a list of integers that are analogous to
ASCII input period block variables. The indexes of IPER arrays are used to
access relevant read and load variable period data at the right time.

There are 2 types of IPER data. Package IPER variables apply to List based
and Array based input.  These variables are 1d integer arrays and are identified
with the variable attribute "modflow6_iper".  The name of this special variable
is not meaningful to MODFLOW 6.  The type of this attribute is a scalar that
describes the size of the 1d data array associated with the variable.  The
following is a simple example for a CHD package instance that would have three
period blocks defined in an ASCII input file for periods 1, 5 and 8:

```
// variable declaration with iper attribute set to size 3
int chd_0_iper(one) ;
       chd_0_iper:modflow6_component = "GWF/CHD" ;
       chd_0_iper:modflow6_package = "CHD_0" ;
       chd_0_iper:modflow6_iper = 3LL ;

// iper variable data
chd_0_iper = 1, 5, 8 ;
```

Package IPER variables are also relevant for Array based input parameters,
however there is the additional need to describe whether individual parameters
have new data for a given period.  When READASARRAYS is read for a package
that supports Array based input, PERIOD data variables must define two 
additional attributes: modflow6_griddata, which defines the size of the 
variable iper 1d array, and modflow6_param_iper, which is the 1d data array.
With array input, the modflow6_param_iper 1d array should always be a subset
of the pacakge modflow6_iper 1d array.

An example:
```
// variable definition with iper attribute set to size 3
int rcha_0_iper(three) ;
        rcha_0_iper:modflow6_component = "GWF/RCHA_0" ;
        rcha_0_iper:modflow6_package = "RCHA_0" ;
        rcha_0_iper:modflow6_iper = 3LL ;

// iper variable data
rcha_0_iper = 1, 5, 8 ;

// recharge declaration with griddata set to size 2
// and param_iper attribute containing the data
double rcha_0_recharge_griddata(three, nlay, nrow, ncol) ;
        rcha_0_recharge_griddata:modflow6_component = "GWF/RCHA" ;
        rcha_0_recharge_griddata:modflow6_package = "RCHA_0" ;
        rcha_0_recharge_griddata:modflow6_block = "PERIOD" ;
        rcha_0_recharge_griddata:modflow6_param = "recharge" ;
        rcha_0_recharge_griddata:modflow6_griddata = 2LL ;
        rcha_0_recharge_griddata:modflow6_param_iper = 1LL, 8LL ;
```

MODFLOW 6 NetCDF Array parameter input format
---------------------------------------------

It may be useful to structure certain array input (e.g. RECHARGE) as
fully gridded, when possible, for the additional purpose of reading and
visualizing the NetCDF file with external tools.

A simple example from example test_gwf_rch03 is shown here:
```
// declaration
double rcha_0_recharge_griddata(one, nlay, nrow, ncol) ;
        rcha_0_recharge_griddata:modflow6_component = "GWF/RCHA" ;
        rcha_0_recharge_griddata:modflow6_package = "RCHA_0" ;
        rcha_0_recharge_griddata:modflow6_block = "PERIOD" ;
        rcha_0_recharge_griddata:modflow6_param = "recharge" ;
        rcha_0_recharge_griddata:modflow6_griddata = 1LL ;
        rcha_0_recharge_griddata:modflow6_param_iper = 1LL ;

// data
rcha_0_recharge_griddata =
  3e+30, 2, 3, 4, 5,
  6, 3e+30, 8, 3e+30, 10,
  11, 3e+30, 13, 3e+30, 15,
  16, 17, 18, 19, 20,
  1, 3e+30, 3e+30, 3e+30, 3e+30,
  3e+30, 7, 3e+30, 9, 3e+30,
  3e+30, 12, 3e+30, 14, 3e+30,
  3e+30, 3e+30, 3e+30, 3e+30, 3e+30 ;
```

This example defines a grid with 1 nper, 2 layers, 4 rows and 5 columns.

The data shows that DNODATA is used as a FillValue for cells
with no data.  IRCH is not explicitly required (and is not
in the example netcdf file) as it can be inferred from the
griddata.  It's inclusion may simplify processing, however, and
ultimately it may be required.  (Note: If the attribute \_FillValue
had been defined for the variable (as should typically be the case)
then the ncdump output for this data would show underscores for the
DNODATA values.)

It should also be noted that index order for multi-dimensional data
intended for visualization is likely important and could change
from what is seen in the examples.



