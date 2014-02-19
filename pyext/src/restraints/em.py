#!/usr/bin/env python
import IMP
import IMP.core
import IMP.base
import IMP.algebra
import IMP.atom
import IMP.container


class GaussianEMRestraint():

    def __init__(self, densities,
                 target_fn='',
                 target_ps=[],
                 cutoff_dist_for_container=10.0,
                 target_mass_scale=1.0,
                 target_radii_scale=1.0,
                 model_radii_scale=1.0):
        global sys, tools
        import sys
        import IMP.isd_emxl
        import IMP.isd_emxl.gmm_tools
        import IMP.pmi.tools as tools
        from math import sqrt

        # some parameters
        self.label="None"
        self.sigmaissampled = False
        self.sigmamaxtrans = 0.3
        self.sigmamin = 1.0
        self.sigmamax = 100.0
        self.sigmainit = 2.0
        self.tabexp = False
        self.label="None"
        self.densities=densities

        # setup target GMM
        self.m = self.densities[0].get_model()
        print 'will scale target mass by',target_mass_scale
        if target_fn!='':
            self.target_ps = []
            IMP.isd_emxl.gmm_tools.decorate_gmm_from_text(target_fn, self.target_ps, self.m)
        elif target_ps!=[]:
            self.target_ps=target_ps
        else:
            print 'Gaussian EM restraint: must provide target density file or properly set up target densities'
            return
        for p in self.target_ps:
            rmax=sqrt(max(IMP.core.Gaussian(p).get_variances()))*target_radii_scale
            if not IMP.core.XYZR.get_is_setup(p):
                IMP.core.XYZR.setup_particle(p,rmax)
            else:
                IMP.core.XYZR.setup_particle(p,rmax)
            mp=IMP.atom.Mass(p)
            mp.set_mass(mp.get_mass()*target_mass_scale)


        # setup model GMM
        self.model_ps = []
        for h in self.densities:
            self.model_ps += IMP.atom.get_leaves(h)
        if model_radii_scale!=1.0:
            for p in self.model_ps:
                rmax=sqrt(max(IMP.core.Gaussian(p).get_variances()))*model_radii_scale
                if not IMP.core.XYZR.get_is_setup(p):
                    IMP.core.XYZR.setup_particle(p,rmax)
                else:
                    IMP.core.XYZR.setup_particle(p,rmax)

        # sigma particle
        self.sigmaglobal = tools.SetupNuisance(self.m, self.sigmainit,
                                               self.sigmamin, self.sigmamax,
                                               self.sigmaissampled).get_particle()

        # create restraint
        print 'target num particles',len(self.target_ps), \
            'total weight',sum([IMP.atom.Mass(p).get_mass() for p in self.target_ps])
        print 'model num particles',len(self.model_ps), \
            'total weight',sum([IMP.atom.Mass(p).get_mass() for p in self.model_ps])

        self.gaussianEM_restraint = IMP.isd_emxl.GaussianEMRestraint(self.m,
                                                                     IMP.get_indexes(self.model_ps),
                                                                     IMP.get_indexes(self.target_ps),
                                                                     self.sigmaglobal.get_particle().get_index(),
                                                                     cutoff_dist_for_container,
                                                                     False, False)
        print 'done EM setup'
        self.rs = IMP.RestraintSet(self.m, 'GaussianEMRestraint')
        self.rs.add_restraint(self.gaussianEM_restraint)

    def center_model_on_target_density(self):
        target_com=IMP.algebra.Vector3D(0,0,0)
        target_mass=0.0
        for p in self.target_ps:
            mass=IMP.atom.Mass(p).get_mass()
            pos=IMP.core.XYZ(p).get_coordinates()
            target_com+=pos*mass
            target_mass+=mass
        target_com/=target_mass
        print 'target com',target_com
        model_com=IMP.algebra.Vector3D(0,0,0)
        model_mass=0.0
        for p in self.model_ps:
            mass=IMP.atom.Mass(p).get_mass()
            pos=IMP.core.XYZ(p).get_coordinates()
            model_com+=pos*mass
            model_mass+=mass
        model_com/=model_mass
        print 'model com',model_com

        v=target_com-model_com
        print 'translating with',v
        IMP.pmi.tools.translate_hierarchies(self.densities,v)

    def set_weight(self,weight):
        self.rs.set_weight(weight)

    def set_label(self, label):
        self.label = label

    def add_to_model(self):
        self.m.add_restraint(self.rs)

    def get_particles_to_sample(self):
        ps = {}
        if self.sigmaissampled:
            ps["Nuisances_GaussianEMRestraint_sigma_" +
                self.label] = ([self.sigmaglobal], self.sigmamaxtrans)
        return ps

    def get_hierarchy(self):
        return self.prot

    def get_restraint_set(self):
        return self.rs

    def get_output(self):
        self.m.update()
        output = {}
        score = self.rs.unprotected_evaluate(None)
        output["_TotalScore"] = str(score)
        output["GaussianEMRestraint_" +
               self.label] = str(self.rs.unprotected_evaluate(None))
        output["GaussianEMRestraint_sigma_" +
               self.label] = str(self.sigmaglobal.get_scale())
        return output
