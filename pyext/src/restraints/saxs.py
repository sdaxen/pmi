"""@namespace IMP.pmi.restraints.saxs
Restraints for handling small angle x-ray (SAXS) data.
"""

from __future__ import print_function
import math
import IMP
import IMP.core
import IMP.algebra
import IMP.atom
import IMP.container
import IMP.pmi.tools
import IMP.pmi.restraints
import IMP.saxs


class SAXSRestraint(IMP.pmi.restraints.RestraintBase):

    """Basic SAXS restraint."""

    def __init__(self, input_objects, saxs_datafile, weight=1.0,
                 ff_type=IMP.saxs.HEAVY_ATOMS, label=None):
        """Builds the restraint.
        @param input_objects A list of hierarchies or PMI objects that the
               SAXS restraint will be applied to. This hierarchy MUST be
               atomic. You can pass a list of CA atom particles to evaluate
               at residue resolution
        @param saxs_datafile the SAXS .dat file.
        @param weight Restraint score coefficient
        @param ff_type the form factor to use, of the following types:
                   - IMP.saxs.HEAVY_ATOMS: use form factors with implicit
                     hydrogens
                   - IMP.saxs.ALL_ATOMS: use individual form factors for all
                     atoms. Does not build missing hydrogens.
                   - IMP.saxs.CA_ATOMS: use residue based form factors
                     centered at CA atoms
        @param label Label for the restraint in outputs
        """
        hiers = IMP.pmi.tools.input_adaptor(input_objects, pmi_resolution=0,
                                            flatten=True)
        m = list(hiers)[0].get_model()
        super(SAXSRestraint, self).__init__(m, label=label, weight=weight)
        self.profile = IMP.saxs.Profile(saxs_datafile)

        if ff_type == IMP.saxs.CA_ATOMS:
            self.particles = IMP.atom.Selection(
                hiers, atom_type=IMP.atom.AT_CA).get_selected_particles()
        elif ff_type == IMP.saxs.HEAVY_ATOMS:
            self.particles = IMP.atom.Selection(
                hiers, resolution=0).get_selected_particles()
        elif ff_type == IMP.saxs.ALL_ATOMS:
            self.particles = IMP.atom.Selection(
                hiers, resolution=0).get_selected_particles()
        else:
            raise Exception("SAXSRestraint: Must provide an IMP.saxs atom "
                            "type: CA_ATOMS, HEAVY_ATOMS or ALL_ATOMS")
        if len(self.particles) == 0:
            raise Exception("SAXSRestraint: There are no selected particles")

        self.restraint = IMP.saxs.Restraint(self.particles, self.profile,
                                            ff_type)
        self.rs.add_restraint(self.restraint)


class SAXSISDRestraint(IMP.pmi.restraints.RestraintBase):

    """Basic SAXS restraint using ISD."""

    import IMP.isd
    try:
        import IMP.isd2
    except:
        print("Module isd2 not installed. Cannot use SAXSISDRestraint")

    def __init__(self, representation, profile, resolution=0, weight=1,
                 ff_type=IMP.saxs.HEAVY_ATOMS, label=None):

        m = representation.prot.get_model()
        super(SAXSISDRestraint, self).__init__(m, label=label, weight=weight)

        self.taumaxtrans = 0.05
        self.prof = IMP.saxs.Profile(profile)

        self.atoms = IMP.pmi.tools.select(
            representation,
            resolution=resolution)

        # gamma nuisance
        self.gamma = IMP.pmi.tools.SetupNuisance(
            self.m, 1., 0., None, False).get_particle()

        # sigma nuisance
        self.sigma = IMP.pmi.tools.SetupNuisance(self.m, 10.0, 0., None, False
                                                 ).get_particle()

        # tau nuisance, optimized
        self.tau = IMP.pmi.tools.SetupNuisance(self.m, 1., 0., None, False,
                                               ).get_particle()

        # c1 and c2, optimized
        self.c1 = IMP.pmi.tools.SetupNuisance(self.m, 1.0, 0.95, 1.05,
                                              True).get_particle()
        self.c2 = IMP.pmi.tools.SetupNuisance(self.m, 0.0, -2., 4.,
                                              True).get_particle()

        # weight, optimized
        self.w = IMP.pmi.tools.SetupWeight(self.m).get_particle()
        IMP.isd.Weight(self.w).set_weights_are_optimized(True)

        # take identity covariance matrix for the start
        self.cov = [[1 if i == j else 0 for j in range(self.prof.size())]
                    for i in range(self.prof.size())]

        print("create saxs restraint")
        self.saxs = IMP.isd2.SAXSRestraint(self.prof, self.sigma, self.tau,
                                           self.gamma, self.w, self.c1,
                                           self.c2)
        self.saxs.add_scatterer(self.atoms, self.cov, ff_type)

        self.rs.add_restraint(self.saxs)

        # self.saxs_stuff={'nuis':(sigma,gamma),'cov':cov,
        #        'exp':prof,'th':tmp}

        self.rs2 = self._create_restraint_set('Prior')
        # jeffreys restraints for nuisances
        j1 = IMP.isd.JeffreysRestraint(self.m, self.sigma)
        self.rs2.add_restraint(j1)
        j2 = IMP.isd.JeffreysRestraint(self.m, self.tau)
        self.rs2.add_restraint(j2)
        j3 = IMP.isd.JeffreysRestraint(self.m, self.gamma)
        self.rs2.add_restraint(j3)

    def optimize_sigma(self):
        """Set sigma to the value that maximizes its conditional likelihood"""
        self.m.update()
        sigma2hat = self.saxs.get_sigmasq_scale_parameter() \
            / (self.saxs.get_sigmasq_shape_parameter() + 1)
        IMP.isd.Scale(self.sigma).set_scale(math.sqrt(sigma2hat))

    def optimize_gamma(self):
        """Set gamma to the value that maximizes its conditional likelihood"""
        self.m.update()
        gammahat = math.exp(self.saxs.get_loggamma_variance_parameter() *
                            self.saxs.get_loggamma_jOg_parameter())
        IMP.isd.Scale(self.gamma).set_scale(gammahat)

    def optimize_tau(self, ltaumin=-2, ltaumax=3, npoints=100):
        values = []
        self.m.update()
        IMP.atom.write_pdb(self.atoms, 'tauvals.pdb')
        fl = open('tauvals.txt', 'w')
        for tauval in self._logspace(ltaumin, ltaumax, npoints):
            IMP.isd.Scale(self.tau).set_scale(tauval)
            try:
                values.append((self.m.evaluate(False), tauval))
            except:
                pass
            fl.write('%G %G\n' % (values[-1][1], values[-1][0]))
        values.sort()
        ltcenter = math.log(values[0][1]) / math.log(10)
        spacing = (ltaumax - ltaumin) / float(npoints)
        values = []
        for tauval in self._logspace(
            ltcenter - 2 * spacing, ltcenter + 2 * spacing,
                npoints):
            IMP.isd.Scale(self.tau).set_scale(tauval)
            values.append((self.m.evaluate(False), tauval))
            fl.write('%G %G\n' % (values[-1][1], values[-1][0]))
        values.sort()
        IMP.isd.Scale(self.tau).set_scale(values[0][1])

    def get_gamma_value(self):
        """Get value of gamma."""
        return self.gamma.get_scale()

    def set_taumaxtrans(self, taumaxtrans):
        self.taumaxtrans = taumaxtrans

    def draw_sigma(self):
        """Draw 1/sigma2 from gamma distribution."""
        self.m.update()
        self.saxs.draw_sigma()

    def draw_gamma(self):
        """Draw gamma from lognormal distribution."""
        self.m.update()
        self.saxs.draw_gamma()

    def update_covariance_matrix(self):
        c1 = IMP.isd.Nuisance(self.c1).get_nuisance()
        c2 = IMP.isd.Nuisance(self.c2).get_nuisance()
        # tau = IMP.isd.Nuisance(self.tau).get_nuisance()
        tau = 1.0
        self.cov = IMP.isd2.compute_relative_covariance(self.atoms, c1, c2,
                                                        tau, self.prof)
        # for i in xrange(len(self.cov)):
        #    for j in xrange(len(self.cov)):
        #        self.cov[i][j] = self.cov[i][j]/tau**2
        self.saxs.set_cov(0, self.cov)

    def write_covariance_matrix(self, fname):
        fl = open(fname, 'w')
        for line in self.cov:
            for i in line:
                fl.write('%G ' % i)
            fl.write('\n')

    def get_output(self):
        output = super(SAXSISDRestraint, self).get_output()
        suffix = self._get_label_suffix()
        output["SAXSISDRestraint_Sigma" +
               suffix] = str(self.sigma.get_scale())
        output["SAXSISDRestraint_Tau" + suffix] = str(self.tau.get_scale())
        output["SAXSISDRestraint_Gamma" +
               suffix] = str(self.gamma.get_scale())
        return output

    @staticmethod
    def _logspace(a, b, num=100):
        """Mimick numpy's logspace function"""
        for i in range(num):
            val = a + float(b - a) / float(num - 1) * i
            yield 10 ** val
