#!/usr/bin/env python
import IMP
import IMP.core
import IMP.atom
import IMP.isd

class CharmmForceFieldRestraint(object):
    """ Enable CHARMM force field """
    def __init__(self,mdl,root,ff_temp=300.0):
        """Setup the charmm restraint on a selection. Expecting atoms.
        @param mdl        The IMP model
        @param root       The node at which to apply the restraint
        @param ff_temp    The temperature of the force field
        """

        kB = (1.381 * 6.02214) / 4184.0

        self.mdl=mdl
        self.bonds_rs = IMP.RestraintSet(self.mdl, 1.0 / (kB * ff_temp), 'BONDED')
        self.nonbonded_rs = IMP.RestraintSet(self.mdl, 1.0 / (kB * ff_temp), 'NONBONDED')
        self.weight=1
        self.label="None"

        ### charmm setup
        ff = IMP.atom.get_heavy_atom_CHARMM_parameters()
        topology = ff.create_topology(root)
        topology.apply_default_patches()
        topology.setup_hierarchy(root)
        r = IMP.atom.CHARMMStereochemistryRestraint(root, topology)
        self.bonds_rs.add_restraint(r)
        ff.add_radii(root)
        ff.add_well_depths(root)
        atoms = IMP.atom.get_leaves(root)

        ### non-bonded forces
        cont = IMP.container.ListSingletonContainer(atoms)
        self.nbl = IMP.container.ClosePairContainer(cont, 4.0)
        self.nbl.add_pair_filter(r.get_pair_filter())
        #sf = IMP.atom.ForceSwitch(6.0, 7.0)
        #pairscore = IMP.atom.LennardJonesPairScore(sf)
        pairscore = IMP.isd.RepulsiveDistancePairScore(0,1)
        pr=IMP.container.PairsRestraint(pairscore, self.nbl)
        self.nonbonded_rs.add_restraint(pr)

        #self.scoring_function = IMP.core.RestraintsScoringFunction([r,pr])

        print 'CHARMM is set up'

    def set_label(self, label):
        self.label = label
        self.rs.set_name(label)
        for r in self.rs.get_restraints():
            r.set_name(label)

    def add_to_model(self):
        self.mdl.add_restraint(self.bonds_rs)
        self.mdl.add_restraint(self.nonbonded_rs)

    def get_restraints(self):
        return [self.bonds_rs,self.nonbonded_rs]

    def get_close_pair_container(self):
        return self.nbl

    def set_weight(self, weight):
        self.weight = weight
        self.rs.set_weight(weight)

    def get_output(self):
        self.mdl.update()
        output = {}
        bonds_score = self.weight * self.bonds_rs.unprotected_evaluate(None)
        nonbonded_score = self.weight * self.nonbonded_rs.unprotected_evaluate(None)
        score=bonds_score+nonbonded_score
        output["_TotalScore"] = str(score)
        output["CHARMM_BONDS"] = str(bonds_score)
        output["CHARMM_NONBONDED"] = str(nonbonded_score)
        return output

class ElasticNetworkRestraint(object):
    import IMP.pmi.tools
    from math import pi as pi

    def __init__(self,mdl,
                 selection,
                 strength=10.0,
                 dist_cutoff=10.0):
        """ Add harmonic restraints between all pairs below a specified distance
        @param mdl         The IMP model
        @param selection   Includes the particles to apply the restraint to
        @param strength    The elastic bond strength
        @param dist_cutoff Create bonds when below this distance
        """
        self.m = representation.prot.get_model()
        self.rs = IMP.RestraintSet(self.m, "ElasticNetwork")
        self.weight = 1
        self.label = "None"
        self.pairslist = []

        particles = selection.get_selected_particles():
        for pair in itertools.combinations(particles,2):
            distance=IMP.algebra.get_distance(IMP.core.XYZ(pair[0]).get_coordinates(),
                                              IMP.core.XYZ(pair[1]).get_coordinates())
            if distance>=dist_cutoff:
                continue
            ts=IMP.core.HarmonicDistancePairScore(distance,strength)
            print "ElasticNetworkConstraint: adding a restraint between %s and %s with distance %.3f" % (pair[0].get_name(),pair[1].get_name(),distance)
            self.rs.add_restraint(IMP.core.PairRestraint(ts,pair))
            self.pairslist.append(IMP.ParticlePair(pair[0], pair[1]))
            self.pairslist.append(IMP.ParticlePair(pair[1], pair[0]))
        print 'created',self.rs.get_number_of_restraints(),'restraints'

    def set_label(self, label):
        self.label = label
        self.rs.set_name(label)
        for r in self.rs.get_restraints():
            r.set_name(label)

    def add_to_model(self):
        self.m.add_restraint(self.rs)

    def get_restraint(self):
        return self.rs

    def set_weight(self, weight):
        self.weight = weight
        self.rs.set_weight(weight)

    def get_excluded_pairs(self):
        return self.pairslist

    def get_output(self):
        self.m.update()
        output = {}
        score = self.weight * self.rs.unprotected_evaluate(None)
        output["ElasticNetworkRestraint_" + self.label] = str(score)
        return output
