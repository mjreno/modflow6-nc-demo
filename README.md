NetCDF4 for MODFLOW 6
=====================

This repository provides documentation realated to Modflow 6 NetCDF4
input files, a new capability under development.

A few example cdl file can be found in the [cdl](examples/cdl)
directory.

- [NetCDF](#modflow6-netcdf)
- [Attributes](#attributes)
- [ODM](#ODM)
- [Dfns](#Definitions)

Modflow6-NetCDF
---------------

The example files are intended to show the organization of Modflow 6
Idm integrated package data in model netcdf4 inputs.

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
* Parameter user tagnames are assumed to be unique to an "input package",
  i.e. globally unique in a dfn file.

Attributes
----------

Attributes are a NetCDF feature that support the aim of self-describing
files.  They can be used to describe additional properties of data or
relationships between data.  They also provide scope when a single file
supports multiple conventions.

Attributes are the primary mechanism enabling Model input to be correctly
read by MODFLOW 6. It is intended that the MODFLOW 6 NetCDF supported
attribute set can be extended as appropriate.

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

| Attribute        |           Meaning             |     Example(s)                                |        Comment
|------------------|-------------------------------|-----------------------------------------------|-------------------------------------
| mf6_input        | Modflow 6 iput string         | "WEL6:GWF_MST03/WEL-1/Q"                      | Format: [PKGTYPE]:[COMPONENT-NAME]/[SUBCOMPONENT-NAME]/[PARAM-TAG]
| mf6_iper         | readasarrays param iper array | mf6_iper = 1,5,8                              | Designated load periods defined per readasarrays period parameter
| mf6_timeseries   | parameter ts variable         | [csub_sk03a.cdl](examples/cdl/csub_sk03a.cdl) |

### Attribute mf6_iper

When READASARRAYS is read for a package that supports Array based input,
PERIOD data variables must define the additional attribute "mf6_iper",
a 1d data array that represents load periods for the parameter. The intent
of this attribute is similar to that of the package "IPER" variable, and the
mf6_iper 1d array should always be a subset of the package "IPER" 1d array.

An example:
```
// declare package iper variable
int rcha_0_iper(rcha_0_niper) ;
        rcha_0_iper:mf6_input = "RCHA6:RCH/RCHA_0/IPER" ;

// iper variable data
rcha_0_iper = 1, 5, 8 ;

// recharge declaration with mf6_iper 1d array as subset of package IPER array
double rcha_0_recharge(rcha_0_niper, NLAY, NROW, NCOL) ;
        rcha_0_recharge:_FillValue = 3.e+30 ;
        rcha_0_recharge:mf6_input = "RCHA6:CSUB_SUB03A/RCHA_0/RECHARGE" ;
        rcha_0_recharge:mf6_iper = 1LL, 8LL ;
```

### Attribute mf6_timeseries

An input parameter mf6_timeseries attribute is set to the name of an associated
netcdf variable that stores timeseries names.  This special variable should only
exist (and mf6_timeseries set) when the input parameter supports timeseries and
the package has an TS6 file input.

The timeseries variable is not an mf6 input parameter and does not define the
mf6_input attribute.  It is type ```char``` and has the same dimensions of its
associated parameter.  It defines timeseries names, when appropriate, that relate
to the period cellid id array.  Where the timeseries array defines a string name,
the associated numeric variable will be set to DNODATA.

A complete example is shown here:  [csub_sk03a.cdl](examples/cdl/csub_sk03a.cdl)

Input Processing
----------------

With the following exceptions, mf6_input parameter tags have a direct correspondence
to dfn file block parameter names.  The input associated with the following tags or tag
classes is in some ways handled differently when compared to ASCII inputs and is described
here:

### IPER
The intent of a package iper variable is to reduce the amount of data written
to the NetCDF file.  IPER arrays provide a list of integers that are analogous
to ASCII input period block variables. The indexes of IPER arrays are used to
access relevant read and load variable period data at the right time.

An IPER variable is required per packge (List and Array based input) but the
associated data is not allocated in the memory manager- it is used internally
to determine when input loaders are to be run:

```
// variable declaration of package iper
int ghb_0_iper(ghb_0_niper) ;
        ghb_0_iper:mf6_input = "GHB6:UZF_3LAY_WC_CHK/GHB_0/IPER" ;

// iper variable data
ghb_0_iper = 1, 4 ;
```
### \*\_RECORD
Parameter sets defined as record types in a dfn file have no direct correspondance
in a NetCDF4 file.  Instead, the individual constituents of the record are each
defined when relevant.  For example:

```
// ASCI input REWET in NPF OPTIONS block
REWET  WETFCT       1.00000000  IWETIT  1  IHDWET  1

// Analogous NetCDF4 declarations
int npf_rewet ;
        npf_rewet:mf6_input = "NPF6:GWF0/NPF/REWET" ;
double npf_wetfct ;
        npf_wetfct:mf6_input = "NPF6:GWF0/NPF/WETFCT" ;
int64 npf_iwetit ;
        npf_iwetit:mf6_input = "NPF6:GWF0/NPF/IWETIT" ;
int64 npf_ihdwet ;
        npf_ihdwet:mf6_input = "NPF6:GWF0/NPF/IHDWET" ;

// data
npf_rewet = 1 ;
npf_wetfct = 1 ;
npf_iwetit = 1 ;
npf_ihdwet = 1 ;

```
### \*\_FILERECORD
These tags are associated with a record that defines an input
or output file specification.  In a NetCDF input file, these tags are associated
with character arrays with a dimension of "LINELENGTH" which is set to the file
specification:

```
// declaration
char chd-1_obs_filerecord(LINELENGTH) ;
        chd-1_obs_filerecord:_Encoding = "ascii" ;
        chd-1_obs_filerecord:mf6_input = "CHD6:GWF_BNDNAME01/CHD-1/OBS_FILERECORD" ;

// data
chd-1_obs_filerecord = "gwf_bndname01.chd.obs                                                                                                                                                                                                                                                                                       " ;

```

These tags are then processed in accordance with the definition and allocated in the
memory manager at the path associated with the 4th token in the RECORD defintion.  For
the case above, the "OBS_FILERECORD" definition is "RECORD OBS6 FILEIN OBS6_FILENAME"
and the variable name of the memory address for the loaded string is "OBS6_FILENAME".

### AUXILIARY
AUXILIARY inputs are 1D character arrays of size (naux, LENAUXNAME), for example:

```
// declaration
char wel-1_auxiliary(wel-1_naux, LENAUXNAME) ;
        wel-1_auxiliary:_Encoding = "ascii" ;
        wel-1_auxiliary:mf6_input = "WEL6:GWF_MST03/WEL-1/AUXILIARY" ;

// data (naux=1)
wel-1_auxiliary =
  "CONCENTRATION   " ;
```

ODM
---

The Output Data Model is intended to support writing simulation data to various output
destinations in the same way that IDM is set up to support various input sources. NetCDF
is also an intended ODM file type.

This section is outline some possible differences between NetCDF input and output files,
and not the mechanism by which a user selects an ODM option.

The most important distinction between an input and output NetCDF file is the organization
of the files and intended use.  Internal files are intended primarily for internal use:

- "proprietary" attributes
- refer to intenal definitions
- datatypes that aren't typical for geoscience NetCDF files
- data that might be structured for input reads, or for how internal data in the simulation is represented
- data that is not stuctured or necessarily intended for external visualiztion tools
- atypical, or no, representation of timeseries information
- Possible future aggregation into larger simulation scoped files that support groups

On the other hand, external (ODM) NetCDF files should better suit users:

- CF conventions and UGRID conventions (when appropriate) compliance
- Output parameters of interest to the modeling scenio
- Output parameters annotated with relevant external convention attributes
- Gridded data structured as appropriate for visulation
- Timeseries data represented in a typical way along a time dimension, unlimited if necessary
- CRS information and Grid mapping variables, when relevant
- Optional distinct representation of grid with UGRID

The last point implies the potential for different types of NetCDF output files to be
selectable by the user.


Definitions
-----------

Parameter definitions are a critical piece that underscore IDM.  This section captures
a few points that may be relevant for discussions related to a definition set refactor.

Definition (.dfn) files describe the set of user input tags for a given input "component",
typically a model package.  Appropriate supported attributes are defined for a parameter,
and these are used by IDM to interpret the input.  The files are currently ASCII, and there
is momentum towards formalizing the system.  A possible file type under consideration is TOML
(see [toml](examples/dfn/GWF-CHD.toml). The points following are for general consideration,
regardless of the file type chosen:

- An component ASCII file might be still be the most straightforward way for developers
  to create or update definitions for a new or existing model
- A tool could be used to validate ASCII inputs and formalize in the creation of TOML
  files that are inputs to other systems.
- An extra layer like this could perform multiple functions:
  - Validation of ASCII
  - Creation of parameter "types", if useful, with unique attribute sets
  - Standarization of attribute initialization
  - Atrribute scopes, e.g. parameter or component (file scope)

