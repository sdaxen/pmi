#!/usr/bin/env python
import IMP
import IMP.algebra




############################
#####Analysis tools
############################



class Alignment():

    """
    This class performs alignment and RMSD calculation for two sets of coordinates
 
    Inputs:

      - query = {'p1':coords(L,3), 'p2':coords(L,3)}
      - template = {'p1':coords(L,3), 'p2':coords(L,3)}

    The class also takes into accout non-equal stoichiometry of the proteins. If this
    is the case, the protein names of protein in multiple copies should be delivered 
    in the following form: nameA..1, nameA..2 (note two dots).
    """

    def __init__(self, template, query):

        global array,argwhere,mgrid,shape,reshape,zeros,diagonal,argsort,deepcopy,cdist,sqrt
        global product, permutations
        from numpy import array,argwhere,mgrid,shape,reshape,zeros,diagonal,argsort
        from copy import deepcopy
        from scipy.spatial.distance import cdist
        from math import sqrt
        from itertools import permutations, product

        self.query = query
        self.template = template
        
        if len(self.query.keys()) != len(self.template.keys()): print '''ERROR: the number of proteins
                               in template and query does not match!''';exit()

    def permute(self):

        self.proteins = sorted(self.query.keys())
        prots_uniq = [i.split('..')[0] for i in self.proteins]
        P = {}
        for p in prots_uniq:
            np = prots_uniq.count(p)
            copies = [i for i in self.proteins if i.split('..')[0]==p]
            prmts = list(permutations( copies, len(copies) )) 
            P[p] = prmts
        self.P = P
        self.Product = list(product(*P.values()))

    def get_rmsd(self):

        self.permute()

        template_xyz = []
        torder = sum([list(i) for i in self.Product[0]],[])
        for t in torder:
           template_xyz += [i for i in self.template[t]]
        template_xyz = array(template_xyz)
        
        self.rmsd = 10000000000.
        for comb in self.Product:
            order = sum([list(i) for i in comb],[])
            query_xyz = []
            for p in order: query_xyz += [i for i in self.query[p]]
            query_xyz = array(query_xyz)
            if len(template_xyz) != len(query_xyz):
                print '''ERROR: the number of coordinates
                               in template and query does not match!''';exit()
            dist = sqrt(sum(diagonal(cdist(template_xyz,query_xyz)**2)) / len(template_xyz))
            if dist < self.rmsd: self.rmsd = dist
        return self.rmsd

    def align(self):

        self.permute()

        template_xyz = []
        torder = sum([list(i) for i in self.Product[0]],[])
        for t in torder:
           template_xyz += [IMP.algebra.Vector3D(i) for i in self.template[t]]
        #template_xyz = array(template_xyz)
        
        self.rmsd, Transformation = 10000000000.,''
        for comb in self.Product:
            order = sum([list(i) for i in comb],[])
            query_xyz = []
            for p in order: query_xyz += [IMP.algebra.Vector3D(i) for i in self.query[p]]
            #query_xyz = array(query_xyz)

            if len(template_xyz) != len(query_xyz):
                print '''ERROR: the number of coordinates
                               in template and query does not match!''';exit()

            transformation = IMP.algebra.get_transformation_aligning_first_to_second(query_xyz,template_xyz)
            query_xyz_tr = [transformation.get_transformed(n) for n in query_xyz]
            
            dist = sqrt(sum(diagonal(cdist(template_xyz,query_xyz_tr)**2)) / len(template_xyz))
            if dist < self.rmsd:
                self.rmsd = dist
                Transformation = transformation
            
        return (self.rmsd, Transformation)
            

### TEST for the alignment ###
"""
import numpy as np
Proteins = {'a..1':np.array([np.array([-1.,1.])]),
            'a..2':np.array([np.array([1.,1.,])]),
            'a..3':np.array([np.array([-2.,1.])]),
            'b':np.array([np.array([0.,-1.])]),
            'c..1':np.array([np.array([-1.,-1.])]),
            'c..2':np.array([np.array([1.,-1.])]),
            'd':np.array([np.array([0.,0.])]),
            'e':np.array([np.array([0.,1.])])}

Ali = Alignment(Proteins, Proteins)
Ali.permute()
if Ali.get_rmsd() == 0.0: print 'successful test!'
else: print 'ERROR!'; exit()
"""      
        
         

# ----------------------------------
class Violations():

    def __init__(self, filename):
        global impem,deepcopy,cdist,array,argwhere,mgrid,shape,reshape,zeros,sqrt,diagonal,argsort
        import IMP.em as impem
        from numpy import array,argwhere,mgrid,shape,reshape,zeros,diagonal,argsort
        from copy import deepcopy
        from scipy.spatial.distance import cdist
        from math import sqrt
        self.violation_thresholds = {}
        self.violation_counts = {}
   
        data = open(filename)
        D = data.readlines()
        data.close()

        for d in D:
            d = d.strip().split()
            self.violation_thresholds[d[0]] = float(d[1])

    def get_number_violated_restraints(self, rsts_dict):
        num_violated = 0
        for rst in self.violation_thresholds:
            if rst not in rsts_dict: continue #print rst; 
            if float(rsts_dict[rst]) > self.violation_thresholds[rst]:
                num_violated += 1
                if rst not in self.violation_counts: self.violation_counts[rst] = 1
                else: self.violation_counts[rst] += 1
        return num_violated



# ----------------------------------
class Clustering():

    def __init__(self):

        global impem,deepcopy,cdist,array,argwhere,mgrid,shape,reshape,zeros,sqrt,diagonal,argsort
        import IMP.em as impem
        from numpy import array,argwhere,mgrid,shape,reshape,zeros,diagonal,argsort
        from copy import deepcopy
        from scipy.spatial.distance import cdist
        from math import sqrt
        self.all_coords = {}

    def set_prot(self, prot):

        self.prot = prot

    def set_template(self, part_coords):

        self.tmpl_coords = part_coords

    def fill(self, frame, Coords, alignment=0):

        if alignment==0:

            self.all_coords[frame]= Coords

        elif alignment==1:

            qry_coords = {}
            for pr in self.tmpl_coords.keys():
                parts = IMP.atom.Selection(self.prot,molecule=pr).get_selected_particles()
                coords = array([array(IMP.core.XYZ(i).get_coordinates()) for i in parts])
                qry_coords[pr] = coords
            Ali = Alignment(self.tmpl_coords, qry_coords)
            rmsd_tm, transformation = Ali.align()
       
            assmb_coords = {}
            for pr in Coords:
                assmb_coords[pr] = [transformation.get_transformed(i) for i in Coords[pr]]
            self.all_coords[frame]= assmb_coords

    def dist_matrix(self):

        K= self.all_coords.keys()
        M = zeros((len(K), len(K)))
        for f1 in xrange(len(K)-1):
            for f2 in xrange(f1,len(K)):

                Ali = Alignment(self.all_coords[K[f1]], self.all_coords[K[f2]])
                r= Ali.get_rmsd()
                M[f1,f2]= r
                M[f2,f1]= r

        print M.max()
        from scipy.cluster import hierarchy as hrc
        import pylab as pl
        import pickle
        C = hrc.fclusterdata(M,0.5)
        outf = open('tmp_cluster_493.pkl','w')
        pickle.dump((K,M),outf)
        outf.close()
        C = list(argsort(C))
        M= M[C,:][:,C]
        fig = pl.figure()
        ax = fig.add_subplot(111)
        cax = ax.imshow(M, interpolation='nearest')
        ax.set_yticks(range(len(K)))
        ax.set_yticklabels( [K[i] for i in C] )
        fig.colorbar(cax)
        pl.show()

# ----------------------------------
class GetModelDensity():

    def __init__(self, dens_thresh=0.1, margin=20., voxel=5.):

        global impem,deepcopy,cdist,array,argwhere,mgrid,shape,reshape
        import IMP.em as impem
        from numpy import array,argwhere,mgrid,shape,reshape
        from copy import deepcopy
        from scipy.spatial.distance import cdist


        self.dens_thresh= dens_thresh
        self.margin= margin
        self.voxel= voxel
        self.mgr= None
        self.densities= {}

    def set_grid(self, part_coords):

        coords = array([array(list(j)) for j in part_coords])
        minx,maxx,miny,maxy,minz,maxz = min(coords[:,0]),max(coords[:,0]),\
                                        min(coords[:,1]),max(coords[:,1]),\
                                        min(coords[:,2]),max(coords[:,2])
        minx-=self.margin
        maxx+=self.margin
        miny-=self.margin
        maxy+=self.margin
        minz-=self.margin
        maxz+=self.margin
        grid= mgrid[minx:maxx:self.voxel,\
                   miny:maxy:self.voxel,\
                   minz:maxz:self.voxel]
        grid= reshape(grid, (3,-1)).T
        self.grid= grid
        return self.grid

    def set_template(self, part_coords):

        self.tmpl_coords = part_coords

    def fill(self, Coords, prot, alignment=0):

        if alignment==0:

            transformation = ''
            self.get_subunits_densities(prot, transformation)

        elif alignment==1:

            qry_coords = {}
            for pr in self.tmpl_coords.keys():
                parts = IMP.atom.Selection(prot,molecule=pr).get_selected_particles()
                coords = array([array(IMP.core.XYZ(i).get_coordinates()) for i in parts])
                qry_coords[pr] = coords
            Ali = Alignment(self.tmpl_coords, qry_coords)
            rmsd_tm, transformation = Ali.align()
       
            self.get_subunits_densities(prot, transformation)


    def get_subunit_density(self, name, prot, transformation):

        crds= []
        radii= []
        
        for part in [IMP.atom.get_leaves(c) for c in prot.get_children()\
                     if c.get_name()==name][-1]:
            p= IMP.core.XYZR(part)
            if transformation!='': crds.append(array(list(transformation.get_transformed((p.get_x(),p.get_y(),p.get_z())))))
            else:  crds.append(array([p.get_x(),p.get_y(),p.get_z()]))
            radii.append(p.get_radius())

        crds= array(crds)
        radii= array(radii)
        dists= cdist(self.grid, crds)-radii
        dens= set(list(argwhere(dists<0)[:,0]))
        return dens

    def get_subunits_densities(self, prot, transformation):

        for sbucp in set([i.get_name().split('..')[0] for i in prot.get_children()]):
            for sbu in prot.get_children():
                subname= sbu.get_name()
                if subname.split('..')[0]!=sbucp: continue

                dens= self.get_subunit_density(subname, prot, transformation)
                if sbucp not in self.densities:
                    self.densities[sbucp]= array([1 if i in dens else 0 for i in xrange(len(self.grid))])
                else:
                    self.densities[sbucp]+= array([1 if i in dens else 0 for i in xrange(len(self.grid))])
        return self.densities

    def write_mrc(self, outname):

        for subunit in self.densities:
            mdl= IMP.Model()
            apix=self.voxel
            resolution=6.
            bbox= IMP.algebra.BoundingBox3D(IMP.algebra.Vector3D(\
                          self.grid[:,0].min(),self.grid[:,1].min(),self.grid[:,2].min()),\
                          IMP.algebra.Vector3D(\
                          self.grid[:,0].max(),self.grid[:,1].max(),self.grid[:,2].max()))
            dheader = impem.create_density_header(bbox,apix)
            dheader.set_resolution(resolution)

            dmap = impem.SampledDensityMap(dheader)
            ps = []
            freqs= self.densities[subunit]
            for x,i in enumerate(self.grid):
                if freqs[x]==0.: continue
                p=IMP.Particle(mdl)
                IMP.core.XYZR.setup_particle(p,\
                                     IMP.algebra.Sphere3D(i,\
                                     1.))#freqs[x]))
                s=IMP.atom.Mass.setup_particle(p,freqs[x])
                ps.append(p)
            dmap.set_particles(ps)
            dmap.resample()
            dmap.calcRMS() # computes statistic stuff about the map and insert it in the header
            print subunit, len(ps), subunit.rsplit('.',1)[0].split('/')[-1]
            impem.write_map(dmap,outname+"_"+subunit.rsplit('.',1)[0].split('/')[-1]+".mrc",impem.MRCReaderWriter())


# ----------------------------------

class GetContactMap():
    def __init__(self, distance=15.):
        global impem,deepcopy,cdist,array,argwhere,mgrid,shape,reshape,zeros,sqrt,diagonal,argsort,log
        import IMP.em as impem
        from numpy import array,argwhere,mgrid,shape,reshape,zeros,diagonal,argsort,log
        from copy import deepcopy
        from scipy.spatial.distance import cdist
        global itemgetter
        from operator import itemgetter
        
        self.distance = distance
        self.contactmap = ''
        self.namelist = []
        self.xlinks = 0
        self.XL = {}
        self.expanded = {}
        self.resmap = {}

    def set_prot(self, prot):
        self.prot = prot

    def get_subunit_coords(self,frame, align=0):
        coords= []
        radii= []
        namelist = []
        test,testr = [],[]
        for part in self.prot.get_children():
            SortedSegments = []
            print part
            for chl in part.get_children():
                start = IMP.atom.get_leaves(chl)[0]
                end   = IMP.atom.get_leaves(chl)[-1]

                startres = IMP.atom.Fragment(start).get_residue_indexes()[0]
                endres   = IMP.atom.Fragment(end).get_residue_indexes()[-1]
                SortedSegments.append((chl,startres))
            SortedSegments = sorted(SortedSegments, key=itemgetter(1))

            for sgmnt in SortedSegments:
                for leaf in IMP.atom.get_leaves(sgmnt[0]):
                    p= IMP.core.XYZR(leaf)
                    crd = array([p.get_x(),p.get_y(),p.get_z()])

                    coords.append(crd)
                    radii.append(p.get_radius())
                   
                    new_name = part.get_name()+'_'+sgmnt[0].get_name()+\
                                    '_'+str(IMP.atom.Fragment(leaf).get_residue_indexes()[0])
                    namelist.append(new_name)
                    self.expanded[new_name] = len(IMP.atom.Fragment(leaf).get_residue_indexes())
                    if part.get_name() not in self.resmap: self.resmap[part.get_name()] = {}
                    for res in IMP.atom.Fragment(leaf).get_residue_indexes():
                        self.resmap[part.get_name()][res] = new_name

        coords = array(coords)
        radii = array(radii)
        if len(self.namelist)==0:
            self.namelist = namelist
            self.contactmap = zeros((len(coords), len(coords)))
        distances = cdist(coords, coords)
        distances = (distances-radii).T - radii
        distances = distances<=self.distance
        self.contactmap += distances


    def add_xlinks(self, filname):
        self.xlinks = 1
        data = open(filname)
        D = data.readlines()
        data.close()

        for d in D:
            d = d.strip().split()
            t1, t2 = (d[0],d[1]), (d[1],d[0])
            if t1 not in self.XL:
                self.XL[t1] = [(int(d[2])+1, int(d[3])+1)]
                self.XL[t2] = [(int(d[3])+1, int(d[2])+1)]
            else:
                self.XL[t1].append((int(d[2])+1, int(d[3])+1))
                self.XL[t2].append((int(d[3])+1, int(d[2])+1))

        


    def dist_matrix(self, skip_cmap=0, skip_xl=1):
        K= self.namelist
        M= self.contactmap
        C,R = [],[]
        L= sum(self.expanded.values())

        # exp new
        if skip_cmap==0:
            Matrices = {}
            proteins = [p.get_name() for p in self.prot.get_children()]
            missing = []
            for p1 in xrange(len(proteins)):
                for p2 in xrange(p1,len(proteins)):
                    pl1,pl2=max(self.resmap[proteins[p1]].keys()),max(self.resmap[proteins[p2]].keys())
                    pn1,pn2=proteins[p1],proteins[p2]
                    mtr=zeros((pl1+1,pl2+1))
                    print 'Creating matrix for: ',p1,p2,pn1,pn2,mtr.shape,pl1,pl2
                    for i1 in xrange(1,pl1+1):
                        for i2 in xrange(1,pl2+1):
                            try:
                                r1=K.index( self.resmap[pn1][i1] )
                                r2=K.index( self.resmap[pn2][i2] )
                                r=M[r1,r2]
                                mtr[i1-1,i2-1]=r
                            except KeyError: missing.append((pn1,pn2,i1,i2)); pass
                    Matrices[(pn1,pn2)]=mtr

        # add cross-links
        if skip_xl==0:
            if self.XL=={}: print "ERROR: cross-links were not provided, use add_xlinks function!"; exit()
            Matrices_xl = {}
            proteins = [p.get_name() for p in self.prot.get_children()]
            missing_xl = []
            for p1 in xrange(len(proteins)):
                for p2 in xrange(p1,len(proteins)):
                    pl1,pl2=max(self.resmap[proteins[p1]].keys()),max(self.resmap[proteins[p2]].keys())
                    pn1,pn2=proteins[p1],proteins[p2]
                    mtr=zeros((pl1+1,pl2+1))
                    flg=0
                    try: xls = self.XL[(pn1,pn2)]
                    except KeyError:
                        try: xls = self.XL[(pn2,pn1)]; flg=1
                        except KeyError: flg=2
                    if flg==0:
                        print 'Creating matrix for: ',p1,p2,pn1,pn2,mtr.shape,pl1,pl2
                        for xl1,xl2 in xls:
                            if xl1>pl1: print 'X'*10,xl1,xl2; xl1=pl1
                            if xl2>pl2: print 'X'*10,xl1,xl2; xl2=pl2
                            mtr[xl1-1,xl2-1]=100
                    elif flg==1:
                        print 'Creating matrix for: ',p1,p2,pn1,pn2,mtr.shape,pl1,pl2
                        for xl1,xl2 in xls:
                            if xl1>pl1: print 'X'*10,xl1,xl2; xl1=pl1
                            if xl2>pl2: print 'X'*10,xl1,xl2; xl2=pl2
                            mtr[xl2-1,xl1-1]=100
                    else: print 'WTF!'; exit()
                    Matrices_xl[(pn1,pn2)]=mtr                

        # expand the matrix to individual residues
        NewM = []
        for x1 in xrange(len(K)):
            lst = []
            for x2 in xrange(len(K)):
                lst += [M[x1,x2]]*self.expanded[K[x2]]
            for i in xrange(self.expanded[K[x1]]): NewM.append(array(lst))
        NewM = array(NewM)

        # make list of protein names and create coordinate lists  
        C = proteins
        W,R = [],[]
        for i,c in enumerate(C):
            cl = max(self.resmap[c].keys())
            W.append(cl)
            if i==0: R.append(cl)
            else: R.append(R[-1]+cl)
        
        # start plotting
        import matplotlib.pyplot as plt
        import matplotlib.gridspec as gridspec
        import scipy.sparse as sparse

        f = plt.figure()
        gs = gridspec.GridSpec(len(W), len(W),
                       width_ratios=W,
                       height_ratios=W)

        cnt = 0
        for x1,r1 in enumerate(R):
            if x1==0: s1=0
            else: s1 = R[x1-1]
            for x2,r2 in enumerate(R):
                if x2==0: s2=0
                else: s2 = R[x2-1]

                ax = plt.subplot(gs[cnt])
                if skip_cmap==0:
                    try: mtr = Matrices[(C[x1],C[x2])]
                    except KeyError: mtr = Matrices[(C[x2],C[x1])].T
                    #cax = ax.imshow(log(NewM[s1:r1,s2:r2] / 1.), interpolation='nearest', vmin=0., vmax=log(NewM.max()))
                    cax = ax.imshow(log(mtr), interpolation='nearest', vmin=0., vmax=log(NewM.max()))
                    ax.set_xticks([])
                    ax.set_yticks([])
                if skip_xl==0:
                    try: mtr = Matrices_xl[(C[x1],C[x2])]
                    except KeyError: mtr = Matrices_xl[(C[x2],C[x1])].T
                    cax = ax.spy(sparse.csr_matrix(mtr), markersize=10, color='white', linewidth=100, alpha=0.5)
                    ax.set_xticks([])
                    ax.set_yticks([])
                                        
                cnt+=1
                if x2==0: ax.set_ylabel(C[x1], rotation=90)
        plt.show()

