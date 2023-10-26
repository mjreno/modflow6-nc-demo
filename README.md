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
  input parameters, related by index, needed for that package.

MODFLOW 6 NetCDF attributes
---------------------------

Attributes are a NetCDF feature that support the aim of self-describing
files.  They can be used to describe additional properties of data or
relationships between data.  They also provide scope when a single file
supports multiple conventions.

Attributes are the primary mechanism enabling Model input to be correctly
read by MODFLOW 6. It is proposed that a well described set of file and
variable scoped attributes be defined to support this effort.  The names
and purposes described here are open for discussion. A common prefix for
all MODFLOW 6 NetCDF4 attributes is probably useful, and in these examples
the prefix "mf6_" is used.  It is intended that the MODFLOW 6 NetCDF
supported attribute set can be extended as appropriate.

### Global attributes

File scoped attributes apply to all MODFLOW 6 variable input that also
use appropriate variable attributes.

| Attribute             |           Meaning             |     Example(s)         |
|-----------------------|-------------------------------|------------------------|
| mf6_modeltype    | Type of MODFLOW 6 Model       | GWF6, GWT6             |
| mf6_modelname    | Name of MODFLOW 6 Model       | "RCH", "MYMODEL"       |

### Variable attributes

These variable attributes describe input parameters for MODFLOW 6 input
processing.

| Attribute             |           Meaning             |     Example(s)              |        Comment
|-----------------------|-------------------------------|-----------------------------|-------------------------------------
| mf6_input             | Modflow 6 iput string         | "WEL6:GWF_MST03/WEL-1/Q"    | Format: [PKGTYPE]:[COMPONENT-NAME]/[SUBCOMPONENT-NAME]/[PARAM-TAG]
| mf6_package           | IPER variable package         | "WEL-1"                     | Use with mf6_iper to designate associated package
| mf6_iper              | IPER package variable, size   | mf6_iper = 3                | Package IPER array size 3, described below
| mf6_griddata          | Griddata iper integer array   | mf6_griddata = 1,5,8        | dynamic griddata variable load periods


MODFLOW 6 NetCDF iper variables
-------------------------------

The intent of iper variable is to reduce the amount of data written to the
NetCDF file.  IPER arrays provide a list of integers that are analogous to
ASCII input period block variables. The indexes of IPER arrays are used to
access relevant read and load variable period data at the right time.

There are 2 types of IPER data. Package IPER variables apply to List based
and Array based input.  These variables are 1d integer arrays and are identified
with the variable attribute "mf6_iper".  The name of this special variable
is not meaningful to MODFLOW 6.  The type of this attribute is a scalar that
describes the size of the 1d data array associated with the variable.  The
"mf6_package" attribute must be paired with the "mf6_iper" attribute to
designate the package to which the variable array data applies.  The
following is a simple example for a CHD package instance that would have three
period blocks defined in an ASCII input file for periods 1, 5 and 8:

```
// variable declaration with iper attribute set to size 2
int ghb_0_iper(ghb_0_niper) ;
        ghb_0_iper:mf6_package = "GHB_0" ;
        ghb_0_iper:mf6_iper = 2LL ;

// iper variable data
ghb_0_iper = 1, 4 ;
```

Package IPER variables are also relevant for Array based input parameters,
however there is the additional need to describe whether individual parameters
have new data for a given period.  When READASARRAYS is read for a package
that supports Array based input, PERIOD data variables must define
the additional attribute "mf6_griddata", a 1d data array that represents load
periods for the parameter. The intent of this attribute is similar to that of
the "mf6_iper" variable, and the mf6_griddata 1d array should always be a subset
of the package mf6_iper 1d array.

An example:
```
// variable definition with iper attribute set to size 3
int rcha_0_iper(rcha_0_niper) ;
        rcha_0_iper:mf6_package = "RCHA_0" ;
        rcha_0_iper:mf6_iper = 3LL ;

// iper variable data
rcha_0_iper = 1, 5, 8 ;

// recharge declaration with griddata of size 2 as subset of package mf6_iper array
double rcha_0_recharge_griddata(rcha_0_niper, nlay, nrow, ncol) ;
        rcha_0_recharge_griddata:_FillValue = 3.e+30 ;
        rcha_0_recharge_griddata:mf6_input = "RCHA6:CSUB_SUB03A/RCHA_0/RECHARGE" ;
        rcha_0_recharge_griddata:mf6_griddata = 1LL, 8LL ;
```

MODFLOW 6 NetCDF Array parameter input format
---------------------------------------------

Array based (READASARRAYS) input parameters (e.g. RECHARGE) are expected to
be fully gridded, when possible, for the additional purpose of reading and
visualizing the NetCDF file with external tools.

A simple example from example test_gwf_rch03 is shown here:
```
// declaration
double rcha_0_recharge_griddata(rcha_0_niper, nlay, nrow, ncol) ;
        rcha_0_recharge_griddata:_FillValue = 3.e+30 ;
        rcha_0_recharge_griddata:mf6_input = "RCHA6:RCH/RCHA_0/RECHARGE" ;
        rcha_0_recharge_griddata:mf6_griddata = 1LL ;

// data
rcha_0_recharge_griddata =
 _, 2, 3, 4, 5,
 6, _, 8, _, 10,
 11, _, 13, _, 15,
 16, 17, 18, 19, 20,
 1, _, _, _, _,
 _, 7, _, 9, _,
 _, 12, _, 14, _,
 _, _, _, _, _ ;
```

This example defines a single load period with a grid of 2 layers, 4 rows and 5 columns.

The data shows that DNODATA is used as a FillValue for cells
with no data.  IRCH is not explicitly required (and is not
in the example netcdf file) as it can be inferred from the
griddata.  It's inclusion may simplify processing, however, and
ultimately it may be required.
