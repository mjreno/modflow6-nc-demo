import os
import sys
import time

import flopy

import netCDF4
import numpy as np
import geopandas as gpd
import re
from shapely.geometry import Point

from enum import Enum
from pathlib import Path

LENBOUNDNAME = 40 # maximum length of a bound name
LENINPUTSTR = 300
DNODATA = 0.3000000000E+31
INODATA = -2147483647

idm_integrated = ['dis','disu','disv','npf', 'dsp', 'chd', 'drn', 'evt', 'ghb', 'rch', 'rcha', 'wel']

class Mf6DisType(Enum):
    NONE = 0
    DISU = 1
    DISV = 2
    DIS = 3

class Mf6NetCDFSim:
    """
    """

    def __init__(self, sim, verbose: bool):
        self._sim = sim
        self._verbose = verbose
        self._component = None
        self._compstr = ''
        self._distype = Mf6DisType.NONE
        self._nc = None
        self._nper = 0
        self._nlay = 0
        self._nrow = 0
        self._ncol = 0
        self._ncpl = 0
        self._nodes = 0
        self._nvert = 0
        
        # for pkg specific griddata input
        self._rcha_irch = {}
        self._rcha_data = {}

        np.set_printoptions(threshold=sys.maxsize)

        self._load_data()

    def _load_data(self):
        # simpath
        sim_path = self._sim.sim_path

        tdis = None

        for p in self._sim.sim_package_list:
            # tdis
            if p.package_type == 'tdis':
                tdis = p

        for model in self._sim.model_names:
            print(f"model => {model}")
            # set model attrs
            modelfname = self._sim.get_model(model).model_nam_file
            self._component = self._sim.get_model(model).model_type
            if 'GWF' not in self._component.upper():
                continue
            self._compstr = self._component.rstrip('6')

            # create ncfile
            self._nc = Mf6NetCDFModel(simpath=sim_path, modeltype=self._component,
                                      modelname=model, modelfname=modelfname,
                                      verbose=True)

            if tdis:
                #self._write_tdis(tdis)
                self._nc.create_dim('nper', tdis.nper.data)
                self._nper = tdis.nper.data

            # package data
            for pkg in self._sim.get_model(model).package_names:
                ptype = self._sim.get_model(model).get_package(pkg).package_type
                if ptype in idm_integrated:
                    self._write_package(model, pkg)
                else:
                    print(f'Skipping idm not supported: {ptype}')

            self._nc.close()
            self._nc = None

    def _write_tdis(self, tdis):
        #perlen nstp tsmult
        perlen = [per[0] for per in tdis.perioddata.get_data()]
        nstp = [per[1] for per in tdis.perioddata.get_data()]
        tsmult = [per[2] for per in tdis.perioddata.get_data()]

        self._nper = tdis.nper.data

        time_units = tdis.time_units.data.ljust(LENINPUTSTR)

        self._nc.create_dim('nper', tdis.nper.data)
        self._nc.add_input_var(self._compstr, 'tdis', 'tdis', 'options', 'time_units',
                               time_units, 'S1', ('lencharstr'))
        self._nc.add_input_var(self._compstr, 'tdis', 'tdis', 'perioddata', 'perlen',
                               perlen, np.float64, ('nper'))
        self._nc.add_input_var(self._compstr, 'tdis', 'tdis', 'perioddata', 'nstp',
                               nstp, np.int32, ('nper'))
        self._nc.add_input_var(self._compstr, 'tdis', 'tdis', 'perioddata', 'tsmult',
                               tsmult, np.float64, ('nper'))

    def _write_package(self, model, pkg):
        #print(dir(self._sim.get_model(model).get_package(pkg)))
        package_name = self._sim.get_model(model).get_package(pkg).package_name
        package_type = self._sim.get_model(model).get_package(pkg).package_type
        dfns = self._sim.get_model(model).get_package(pkg).dfn
        print(f'PROCESSING PKG={package_name}')

        for v in self._sim.get_model(model).get_package(pkg).simulation_data.mfdata.items():
            if v[0][0] == model and v[0][1] == package_type:
                dfn = None
                for d in dfns:
                    if len(d) > 1:
                        tokens = d[1].split()
                        if len(tokens) == 2 and tokens[0] == 'name' and tokens[1] == v[0][3]:
                            dfn = d
                self._write_var(model, package_name, package_type, v, dfn)

        if package_type == 'dis':
            self._distype = Mf6DisType.DIS
            self._nodes = self._nlay * self._nrow * self._ncol
            self._ncpl = self._nrow * self._ncol
            self._nc.create_dim('nodes', self._nodes)
            self._nc.create_dim('ncpl', self._ncpl)
            self._nc.create_dim('ncelldim', 3)
        elif package_type == 'disu':
            self._distype = Mf6DisType.DISU
            self._nc.create_dim('ncelldim', 1)
        elif package_type == 'disv':
            self._distype = Mf6DisType.DISV
            self._nodes = self._nlay * self._ncpl
            self._nc.create_dim('nodes', self._nodes)
            self._nc.create_dim('ncelldim', 2)

        if hasattr(self._sim.get_model(model).get_package(pkg), "stress_period_data"):
            if self._sim.get_model(model).get_package(pkg).stress_period_data.has_data():
                aux = self._sim.get_model(model).get_package(pkg).auxiliary.get_data()
                if aux:
                    aux = list(aux[0])
                    aux.pop(0)
                else:
                    aux = []
                maxbound = self._sim.get_model(model).get_package(pkg).stress_period_data.package.maxbound.data
                spdata = self._sim.get_model(model).get_package(pkg).stress_period_data.data
                self._nc.add_period_data(self._compstr, package_type, package_name, self._nper, maxbound, spdata, aux)

    def _write_var(self, model, package_name, package_type, v, dfn):
        if v[0][2] == 'obs' and type(v[1]) is not flopy.mf6.data.mfdatautil.MFComment:
            print(f'WARN skipping observations tied to package {package_name}: {v}')
            return

        print(f"write_var var={v[0][3]} type={type(v[1])}")

        if type(v[1]) is flopy.mf6.data.mfdatautil.MFComment:
            pass
        elif type(v[1]) is flopy.mf6.data.mfdatalist.MFList:
            if v[0][3] == 'timeseries':
                print(f'timeseries: {v}')
            elif v[1].has_data():
                self._write_mflist(model, package_name, package_type, v, dfn)
        elif type(v[1]) is flopy.mf6.data.mfdataarray.MFArray:
            if v[1].has_data():
                self._write_mfarray(model, package_name, package_type, v, dfn)
        elif type(v[1]) is flopy.mf6.data.mfdataarray.MFTransientArray:
            if v[1].has_data():
                self._write_mftransarray(model, package_name, package_type, v, dfn)
        elif type(v[1]) is flopy.mf6.data.mfdatalist.MFTransientList:
            print(f'UNHANDLED MFTransientList: {v[0][3]}')
        elif type(v[1]) is flopy.mf6.data.mfdataplist.MFPandasTransientList:
            print(f'UNHANDLED MFPandasTransientList: {v[0][3]}')
        elif type(v[1]) is flopy.mf6.data.mfdatascalar.MFScalar:
            if v[1].has_data():
                self._write_mfscalar(model, package_name, package_type, v, dfn)
        elif type(v[1]) is flopy.mf6.data.mfdatalist.MFMultipleList:
            print(f'UNHANDLED MFMultipleList: {v[0][3]}')
        elif type(v[1]) is flopy.mf6.data.mfdatascalar.MFScalarTransient:
            print(f'UNHANDLED MFScalarTransient: {v[0][3]}')
        else:
            sys.stderr.write(f'UNHANDLED FLOPY TYPE: {type(v[1])}\n')
            sys.stderr.write(f'{v}\n')
            sys.exit(1)

    def _set_dis_dim(self, model, package_name, package_type, v, dfn):
        blockname = v[0][2]
        varname = v[0][3]
        data = v[1].data
        dtype = v[1].dtype

        if varname == 'nlay':
            self._nlay = data
        elif varname == 'nrow':
            self._nrow = data
        elif varname == 'ncol':
            self._ncol = data
        elif varname == 'ncpl':
            self._ncpl = data
        elif varname == 'nodes':
            self._nodes = data
        elif varname == 'nvert':
            self._nvert = data
        else:
            sys.stderr.write(f'UNHANDLED DIS DIM: {varname}\n')
            sys.exit(1)

    def _write_mflist(self, model, package_name, package_type, v, dfn):
        blockname = v[0][2]
        varname = v[0][3]
        data = v[1].get_data()
        dtype = v[1].dtype

        if '_filerecord' in varname:
            fname = v[1].get_data()[0][0].ljust(LENINPUTSTR)

            if v[0][3] == "afrcsv_filerecord":
                keyword = "afrcsvfile"
            elif v[0][3] == "obs_filerecord":
                keyword = "obs6_filename"
            else:
                sys.stderr.write(f'UNHANDLED MFList IOTAG for filerecord: {v[0][3]}\n')
                sys.exit(1)

            self._nc.add_input_var(self._compstr, package_type, package_name, blockname, v[0][3],
                                   fname, 'S1', ('lencharstr'))
        elif varname == 'vertices':
            #NOTE iv is 0 based, others arent
            iv = [x[0]+1 for x in data]
            xv = [x[1] for x in data]
            yv = [x[2] for x in data]

            self._nc.add_input_var(self._compstr, package_type, package_name, blockname,
                                   'IV', iv, np.int32, ('nvert'))
            self._nc.add_input_var(self._compstr, package_type, package_name, blockname,
                                   'XV', xv, np.float64, ('nvert'))
            self._nc.add_input_var(self._compstr, package_type, package_name, blockname,
                                   'YV', yv, np.float64, ('nvert'))
        elif varname == 'cell2d':
            icell2d = [x[0] + 1 for x in data]
            xc = [x[1] for x in data]
            yc = [x[2] for x in data]
            ncvert = [x[3] for x in data]
            icvert = []
            for n, v in enumerate(ncvert):
                # These are 0 indexed
                l = data[n].tolist()
                r = l[4:4+ncvert[n]]
                for c in r:
                    icvert.append(c+1)

            cdim = f"{package_name}_ncell2d"
            vdim = f"{package_name}_ncvert"
            self._nc.create_dim(cdim, len(icell2d))
            self._nc.create_dim(vdim, len(icvert))

            self._nc.add_input_var(self._compstr, package_type, package_name, blockname,
                                   'ICELL2D', icell2d, np.int32, (cdim))
            self._nc.add_input_var(self._compstr, package_type, package_name, blockname,
                                   'XC', xc, np.float64, (cdim))
            self._nc.add_input_var(self._compstr, package_type, package_name, blockname,
                                   'YC', yc, np.float64, (cdim))
            self._nc.add_input_var(self._compstr, package_type, package_name, blockname,
                                   'NCVERT', ncvert, np.int32, (cdim))
            self._nc.add_input_var(self._compstr, package_type, package_name, blockname,
                                   'ICVERT', icvert, np.int32, (vdim))
        elif varname == 'auxiliary':
            # TODO: incoming could be string (like this) or list of strings, handle both
            s = data[0][1].ljust(LENINPUTSTR)
            aux_l = data[0][1].split(',')
            # TODO: naux isn't in ascii input
            self._nc.create_dim(f"{package_name}_naux", len(aux_l))
            self._nc.add_input_var(self._compstr, package_type, package_name, blockname,
                                   'AUXILIARY', s, 'S1', (f"{package_name}_naux", 'lencharstr'))

        else:
            sys.stderr.write(f'UNHANDLED _write_mflist: {varname}\n')
            sys.exit(1)
        

    def _write_mfarray(self, model, package_name, package_type, v, dfn):
        blockname = v[0][2]
        varname = v[0][3]
        data = v[1].data
        dtype = v[1].dtype
        shape = dfn[3].split()[1]
        if 'nodes' in shape:
            if self._distype == Mf6DisType.DIS:
                self._nc.add_input_var(self._compstr, package_type, package_name, blockname,
                                       varname, data, dtype, ('nlay','nrow','ncol'))
            elif self._distype == Mf6DisType.DISU:
                self._nc.add_input_var(self._compstr, package_type, package_name, blockname,
                                       varname, data, dtype, ('nodes'))
            elif self._distype == Mf6DisType.DISV:    
                self._nc.add_input_var(self._compstr, package_type, package_name, blockname,
                                       varname, data, dtype, ('nlay','ncpl'))
            else:
                sys.stderr.write(f'Attempting to write griddata when distype not set\n')
                sys.exit(1)
        else:
            dims = re.sub(r'[(),]', '', dfn[3].replace('shape ', ''))
            dimlist = dims.split()
            ordered = ['nlay', 'nrow', 'ncpl', 'ncol', 'nodes', 'nvert']
            sorted_dims = [x for x in ordered if x in dimlist]
            if len(sorted_dims) != len(dimlist):
                sys.stderr.write(f'Invalid shape sort\n')
                #print(sorted_dims)
                #print(dimlist)
                for d in dimlist:
                    if '*' in d:
                        dimlist.remove(d)
                        if len(dimlist) == 1:
                            data = data.flatten()
                            #print(data)
                #sys.exit(1)
            self._nc.add_input_var(self._compstr, package_type, package_name, blockname,
                                   varname, data, dtype, sorted_dims)

    def _write_mftransarray(self, model, package_name, package_type, v, dfn):
        print(f"_write_mftransarray {v}")
        blockname = v[0][2]
        varname = v[0][3]
        data = v[1].get_data(layer=0)
        dtype = v[1].dtype
        shape = dfn[3].split()[1]

        print(f"write_mftransarray: {package_name}/{blockname}/{varname}")

        if 'nodes' in shape:
            if self._distype == Mf6DisType.DIS:
                self._nc.add_input_var(self._compstr, package_type, package_name, blockname,
                                       varname, data.reshape(self._nodes), dtype, ('nodes'))
            elif self._distype == Mf6DisType.DISU:
                self._nc.add_input_var(self._compstr, package_type, package_name, blockname,
                                       varname, data, dtype, ('nodes'))
            elif self._distype == Mf6DisType.DISV:
                self._nc.add_input_var(self._compstr, package_type, package_name, blockname,
                                       varname, data, dtype, ('nodes'))
            else:
                sys.stderr.write(f'Attempting to write griddata when distype not set\n')
                sys.exit(1)
        else:
            dims = re.sub(r'[(),]', '', dfn[3].replace('shape ', ''))
            dimlist = dims.split()
            ordered = ['nlay', 'nrow', 'ncpl', 'ncol', 'nodes', 'nvert']
            sorted_dims = [x for x in ordered if x in dimlist]
            load_d = np.array([[]])
            last_d = np.array([])
            if len(sorted_dims) != len(dimlist):
                #print(sorted_dims)
                #print(dimlist)
                for d in dimlist:
                    if '*' in d:
                        dimlist.remove(d)
                        if len(dimlist) == 1:
                            for x in range(len(data)):
                                d = data[x]
                                if d is None:
                                    load_d = np.append(load_d, last_d)
                                else:
                                    load_d = np.append(load_d, d.flatten())
                                    last_d = d.flatten()
                                    #print(last_d)
                                    #print(type(last_d))
                            load_d.shape = (self._nper, self._ncpl)
                            #print(load_d)
                            
            print(f"varname={varname} shape={load_d.shape} data={load_d} type={type(load_d)}")
            iper_l = [1]
            if shape != '':
                if package_name.upper() not in self._rcha_data:
                    self._rcha_data[package_name.upper()] = {}
                if varname not in self._rcha_data[package_name.upper()]:
                    prev_d = None
                    for kper, d  in enumerate(load_d):
                        if prev_d is not None:
                            for i, v in enumerate(d):
                                if (v != prev_d[i]):
                                    iper_l.append(kper+1)
                                    break
                        prev_d = d
                    self._rcha_data[package_name.upper()][varname] = iper_l
                        
            # The following assumes irch is always seen first
            do_load = True
            if varname.upper() == 'IRCH':
                do_load = False
                # overwrite if there
                print(f"recharge IRCH: provided from FloPy as: {load_d}")
                self._rcha_irch[package_name.upper()] = load_d
                load_d = load_d + 1
            elif varname.upper() == 'RECHARGE':
                do_load = False
                # TODO: if IRCH isn't defined it is just 0's
                if package_name.upper() not in self._rcha_irch:
                    iirch = []
                    irch_per = np.zeros(self._nrow * self._ncol).reshape(1, self._nrow * self._ncol)
                    for i in range(self._nper):
                        iirch.append(irch_per)
                    self._rcha_irch[package_name.upper()] = iirch

                pdim = f"{package_name}_niper"
                self._nc.create_dim(pdim, len(iper_l))

                # create and set mf6_iper for package
                per = self._nc._dataset.createVariable(f"{package_name.lower()}_iper", np.int32,
                                                   (pdim))
                per.mf6_package = package_name.upper()
                per.mf6_iper = len(iper_l)
                per[:] = [x for x in iper_l]

                # only write griddata if DIS
                if self._distype == Mf6DisType.DIS:
                    rch = np.full((len(iper_l), self._nlay, self._nrow, self._ncol), DNODATA)
                    for idx in range(len(iper_l)):
                        k = iper_l[idx]
                        irch = self._rcha_irch[package_name.upper()][k-1].reshape(self._nrow, self._ncol)
                        for r in range(self._nrow):
                            for c in range(self._ncol):
                                # TODO why is this a real?
                                l = int(irch[r,c])
                                rch[idx][l,r,c] = load_d[k-1][c + r * self._ncol]

                    self._nc.add_input_var(self._compstr, package_type, package_name, blockname,
                                           varname, rch, dtype, [pdim, 'nlay', 'nrow', 'ncol'], True, iper_l)


            if do_load:
                self._nc.add_input_var(self._compstr, package_type, package_name, blockname,
                                       varname, load_d, dtype, ['nper', 'ncpl'])


    def _write_mfscalar(self, model, package_name, package_type, v, dfn):
        blockname = v[0][2]
        varname = v[0][3]
        data = v[1].data
        dtype = v[1].dtype
        if v[1].dtype == np.int32 or v[1].dtype == np.float64:
            if blockname == 'period':
                pass
            elif blockname == 'dimensions':
                if package_type == 'dis' or package_type == 'disu' or package_type == 'disv':
                    self._set_dis_dim(model, package_name, package_type, v, dfn)
                    self._nc.create_dim(f'{varname}', data)
                else:
                    #self._nc.create_dim(f'{package_name}_{varname}', data)
                    print(f'creating dim {varname} at {data}')
                    vdim = f"{package_name}_{varname}"
                    self._nc.create_dim(vdim, data)

                # always create mf6 dimension variable as well
                self._nc.add_input_var(self._compstr, package_type, package_name, blockname,
                                       varname, data, np.int32, '')
            else:
                if blockname == 'obs':
                    print(f'obs blockvar: {v}')
                self._nc.add_input_var(self._compstr, package_type, package_name, blockname,
                                       varname, data, dtype, '')
        elif v[1].dtype == np.record:
            print('UNHANDLED record')
        elif v[1].dtype is None:
            self._nc.add_input_var(self._compstr, package_type, package_name, blockname,
                                   varname, 1, np.int32, '')
        else:
            print()
            #print(dir(v[1]))
            print(f'model={v[0][0]}')
            print(f'pkgtype={v[0][1]}')
            print(f'pkgname={package_name}')
            print(f'block={v[0][2]}')
            print(f'var={v[0][3]}')
            print(type(v[1]))
            print(f'data={v[1].data}')
            print(f'dtype={v[1].dtype}')
            print(f'data_type={v[1].data_type}')
            print(f'has_data={v[1].has_data()}')
            print(f'get_data={v[1].get_data()}')
            sys.stderr.write(f'UNHANDLED FLOPY MFSCALAR DTYPE: {v[1].dtype}\n')
            sys.exit(1)
        
class Mf6NetCDFModel:
    """
    """

    def __init__(self, simpath: str, modeltype: str, modelname: str, modelfname: str, verbose: bool):
        self._simpath = Path(simpath).resolve()
        self._modeltype = modeltype
        self._modelname = modelname
        self._modelfname = modelfname
        self._verbose = verbose

        self._fname = self._simpath / f'{modelname}.nc'

        self._dataset = netCDF4.Dataset(self._fname, mode='w', format='NETCDF4')

        self._dataset.description = "MODFLOW 6 NetCDF4 file prototype"
        self._dataset.history = "Created " + time.ctime(time.time())
        self._dataset.source = "mf6netcdf4.py"
        self._dataset.mf6_modeltype = modeltype.upper()
        self._dataset.mf6_modelname = modelname.upper()
        #self._dataset.Conventions = "CF-1.8 UGRID-1.0"
        self._dataset.Conventions = "CF-1.8"
        #self._dataset.coordinates = "mesh_nodes_x mesh_nodes_y"
        #self._dataset.coordinates = "longitude latitude"

        self._dataset.set_fill_on()
        self.create_dim('lencharstr', LENINPUTSTR)

    def close(self):
        self._dataset.close()
        if self._verbose:
            print('Dataset is closed!')

    def create_dim(self, name: str, data):
        self._dataset.createDimension(name, data)

    def add_input_var(self, component, pkgtype, pkgname, blockname, varname, data, dtype, shape, griddata=None, iper_l=None):
        if varname == 'top':
            if pkgtype.upper() == 'DIS':
                shape = ['nrow', 'ncol']
            #elif pkgtype.upper() == 'DISV':
            #    shape = ['ncpl']
        if griddata:
            aname = f"{pkgname.lower()}_{varname.lower()}_griddata"
        else:
            aname = f"{pkgname.lower()}_{varname.lower()}"
        if shape == '':
            grpvar = self._dataset.createVariable(aname, dtype)
        else:
            fill = None
            if (dtype == np.float64):
                fill = DNODATA
            elif (dtype == np.int32):
                fill = INODATA
            grpvar = self._dataset.createVariable(aname, dtype, shape, fill_value=fill)

        if dtype == 'S1':
                grpvar._Encoding = 'ascii'
            
        grpvar.mf6_input = f"{pkgtype.upper()}6:{self._modelname.upper()}/{pkgname.upper()}/{varname.upper()}"
        if griddata:
            grpvar.mf6_griddata = iper_l
        grpvar[:] = data

    def create_var(self, component, pkgtype, pkgname, blockname, varname, dtype, shape, fill=None):
        print(f'adding pkg={pkgname} var={varname} block={blockname} shape={shape}')
        if varname == 'top':
            shape = ['nrow', 'ncol']
        aname = f"{pkgname.lower()}_{varname.lower()}"
        if shape == '':
            grpvar = self._dataset.createVariable(aname, dtype, fill_value=fill)
        else:
            grpvar = self._dataset.createVariable(aname, dtype, shape, fill_value=fill)

        if dtype == 'S1':
            grpvar._Encoding = 'ascii'

        grpvar.mf6_input = f"{pkgtype.upper()}6:{self._modelname.upper()}/{pkgname.upper()}/{varname.upper()}"

        return grpvar


    def add_period_data(self, component, pkgtype, pkgname, nper, maxbound, data, auxvar):

        # This is the load routine for LIST based dynamic input
        if pkgtype.upper() == 'CHD':
            self.add_sp_base_ncolbnd1(component, pkgtype, pkgname, nper, maxbound, data, auxvar)
        elif pkgtype.upper() == 'DRN':
            self.add_sp_base_ncolbnd1(component, pkgtype, pkgname, nper, maxbound, data, auxvar)
        elif pkgtype.upper() == 'EVT':
            self.add_sp_base_ncolbnd1(component, pkgtype, pkgname, nper, maxbound, data, auxvar)
        elif pkgtype.upper() == 'GHB':
            self.add_sp_base_ncolbnd1(component, pkgtype, pkgname, nper, maxbound, data, auxvar)
        elif pkgtype.upper() == 'RCH':
            self.add_sp_base_ncolbnd1(component, pkgtype, pkgname, nper, maxbound, data, auxvar)
        elif pkgtype.upper() == 'WEL':
            self.add_sp_base_ncolbnd1(component, pkgtype, pkgname, nper, maxbound, data, auxvar)
        else:
            sys.stderr.write(f'UNHANDLED SP PACKAGE TYPE: {pkgtype}\n')
            sys.exit(1)

    def add_sp_base_ncolbnd1(self, component, pkgtype, pkgname, nper, maxbound, data, auxvar):
        print(f'add_sp_base_ncolbnd1 nper={nper} maxbound={maxbound} auxvar={auxvar}')
        print(data)
        iper_l = list(data.keys())
        pdim = f"{pkgname}_niper"
        self.create_dim(pdim, len(iper_l))

        # create and set mf6_iper for package
        per = self._dataset.createVariable(f"{pkgname.lower()}_iper", np.int32,
                                           (pdim))
        per.mf6_package = pkgname.upper()
        per.mf6_iper = len(iper_l)
        per[:] = [x+1 for x in iper_l]

        # create vars
        fieldvars = []
        for n, f in enumerate(data[iper_l[0]].dtype.names):
            #print(f'field={n}')
            #print([x[n] for x in data[0]])
            if f in auxvar:
                continue
            elif f == 'cellid':
                shape = (f"{pkgname}_niper", f"{pkgname}_maxbound", "ncelldim")
                cellid = self.create_var(component, pkgtype, pkgname, 'PERIOD',
                                         'cellid', np.int32, shape, INODATA)
            elif f == 'boundname':
                self.create_dim('lenboundname', LENBOUNDNAME)
                shape = (f"{pkgname}_niper", f"{pkgname}_maxbound", "lenboundname")
                boundname = self.create_var(component, pkgtype, pkgname, 'PERIOD',
                                            'boundname', 'S1', shape)
            elif f == 'head':
                shape = (f"{pkgname}_niper", f"{pkgname}_maxbound")
                head = self.create_var(component, pkgtype, pkgname, 'PERIOD',
                                       'head', np.float64, shape, DNODATA)
            elif f == 'bhead':
                shape = (f"{pkgname}_niper", f"{pkgname}_maxbound")
                bhead = self.create_var(component, pkgtype, pkgname, 'PERIOD',
                                       'bhead', np.float64, shape, DNODATA)
            elif f == 'elev':
                shape = (f"{pkgname}_niper", f"{pkgname}_maxbound")
                elev = self.create_var(component, pkgtype, pkgname, 'PERIOD',
                                       'elev', np.float64, shape, DNODATA)
            elif f == 'cond':
                shape = (f"{pkgname}_niper", f"{pkgname}_maxbound")
                cond = self.create_var(component, pkgtype, pkgname, 'PERIOD',
                                       'cond', np.float64, shape, DNODATA)
            elif f == 'recharge':
                shape = (f"{pkgname}_niper", f"{pkgname}_maxbound")
                rch = self.create_var(component, pkgtype, pkgname, 'PERIOD',
                                      'recharge', np.float64, shape, DNODATA)
            elif f == 'surface':
                shape = (f"{pkgname}_niper", f"{pkgname}_maxbound")
                surface = self.create_var(component, pkgtype, pkgname, 'PERIOD',
                                          'surface', np.float64, shape, DNODATA)
            elif f == 'rate':
                shape = (f"{pkgname}_niper", f"{pkgname}_maxbound")
                rate = self.create_var(component, pkgtype, pkgname, 'PERIOD',
                                       'rate', np.float64, shape, DNODATA)
            elif f == 'depth':
                shape = (f"{pkgname}_niper", f"{pkgname}_maxbound")
                depth = self.create_var(component, pkgtype, pkgname, 'PERIOD',
                                        'depth', np.float64, shape, DNODATA)
            elif f == 'petm0':
                shape = (f"{pkgname}_niper", f"{pkgname}_maxbound")
                petm0 = self.create_var(component, pkgtype, pkgname, 'PERIOD',
                                        'petm0', np.float64, shape, DNODATA)
            elif f == 'q':
                shape = (f"{pkgname}_niper", f"{pkgname}_maxbound")
                q = self.create_var(component, pkgtype, pkgname, 'PERIOD',
                                    'q', np.float64, shape, DNODATA)
            else:
                sys.stderr.write(f'UNHANDLED PERIOD TYPE: {f}\n')
                sys.exit(1)

        if len(auxvar):
            aux = self._dataset.createVariable(f"{pkgname.lower()}_aux", np.float64,
                                                   (f"{pkgname}_niper", f"{pkgname}_maxbound", f"{pkgname}_naux"), fill_value=DNODATA)
            #TODO: don't do this, define attribute?
            aux.mf6_input = f"{pkgtype.upper()}6:{self._modelname.upper()}/{pkgname.upper()}/AUX"

        index = 0
        for iper in iper_l:
            for n, f in enumerate(data[iper].dtype.names):
                d = [x[n] for x in data[iper]]
                if f == 'cellid':
                    for i, c in enumerate(d):
                        c = [d + 1 for d in d[i]]
                        print(f'adding cellid={c}')
                        cellid[index,i,:] = c
                elif f == 'head':
                    d = [x if not isinstance(x, str) else DNODATA for x in d]
                    for m in range(len(d)):
                        head[index,m] = d[m]
                elif f == 'bhead':
                    d = [x if not isinstance(x, str) else DNODATA for x in d]
                    for m in range(len(d)):
                        bhead[index,m] = d[m]
                elif f == 'elev':
                    d = [x if not isinstance(x, str) else DNODATA for x in d]
                    for m in range(len(d)):
                        elev[index,m] = d[m]
                elif f == 'cond':
                    d = [x if not isinstance(x, str) else DNODATA for x in d]
                    for m in range(len(d)):
                        cond[index,m] = d[m]
                elif f == 'recharge':
                    d = [x if not isinstance(x, str) else DNODATA for x in d]
                    for m in range(len(d)):
                        rch[index,m] = d[m]
                elif f == 'surface':
                    d = [x if not isinstance(x, str) else DNODATA for x in d]
                    for m in range(len(d)):
                        surface[index,m] = d[m]
                elif f == 'rate':
                    d = [x if not isinstance(x, str) else DNODATA for x in d]
                    for m in range(len(d)):
                        rate[index,m] = d[m]
                elif f == 'depth':
                    d = [x if not isinstance(x, str) else DNODATA for x in d]
                    for m in range(len(d)):
                        depth[index,m] = d[m]
                elif f == 'petm0':
                    d = [x if not isinstance(x, str) else DNODATA for x in d]
                    for m in range(len(d)):
                        petm0[index,m] = d[m]
                elif f == 'q':
                    d = [x if not isinstance(x, str) else DNODATA for x in d]
                    for m in range(len(d)):
                        q[index,m] = d[m]
                elif f == 'boundname':
                    for b in range(len(d)):
                        s = d[b].ljust(LENBOUNDNAME)
                        boundname[index,b] = s
                elif f in auxvar:
                    auxidx = auxvar.index(f)
                    d = [x if not isinstance(x, str) else DNODATA for x in d]
                    #print(f'auxidx={auxidx}')
                    #print(f'data={d}')
                    for m in range(len(d)):
                        aux[index,m,auxidx] = d[m]
            index += 1
