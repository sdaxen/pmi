"""@namespace IMP.pmi.restraints.basic
Some miscellaneous simple restraints.
"""

from __future__ import print_function
import IMP
import IMP.core
import IMP.algebra
import IMP.atom
import IMP.container
import IMP.pmi.tools
import IMP.pmi.restraints


class ExternalBarrier(IMP.pmi.restraints.RestraintBase):

    """Restraint to keep all structures inside sphere."""

    def __init__(self,
                 representation=None,
                 radius=10.0,
                 hierarchies=None,
                 resolution=10,
                 weight=1.0,
                 center=None,
                 label=None):
        """Setup external barrier restraint.
        @param representation DEPRECATED
        @param radius Size of external barrier
        @param hierarchies Can be one of the following inputs: IMP Hierarchy,
               PMI System/State/Molecule/TempResidue, or a list/set of them
        @param resolution Select which resolutions to act upon
        @param weight Weight of restraint
        @param center Center of the external barrier restraint
               (IMP.algebra.Vector3D object)
        @param label A unique label to be used in outputs and
                     particle/restraint names.
        """
        if representation:
            m = representation.prot.get_model()
            particles = IMP.pmi.tools.select(
                representation,
                resolution=resolution,
                hierarchies=hierarchies)
        elif hierarchies:
            hiers = IMP.pmi.tools.input_adaptor(hierarchies, resolution,
                                                flatten=True)
            m = hiers[0].get_model()
            particles = [h.get_particle() for h in hiers]
        else:
            raise Exception("%s: must pass representation or hierarchies" % (
                self.name))

        super(ExternalBarrier, self).__init__(m, label=label, weight=weight)
        self.radius = radius

        if center is None:
            c3 = IMP.algebra.Vector3D(0, 0, 0)
        elif type(center) is IMP.algebra.Vector3D:
            c3 = center
        else:
            raise Exception(
                "%s: @param center must be an IMP.algebra.Vector3D object" % (
                    self.name))

        ub3 = IMP.core.HarmonicUpperBound(radius, 10.0)
        ss3 = IMP.core.DistanceToSingletonScore(ub3, c3)
        lsc = IMP.container.ListSingletonContainer(self.m)

        lsc.add(particles)
        r3 = IMP.container.SingletonsRestraint(ss3, lsc)
        self.rs.add_restraint(r3)


class DistanceRestraint(IMP.pmi.restraints.RestraintBase):

    """A simple distance restraint"""

    def __init__(self,
                 representation=None,
                 tuple_selection1=None,
                 tuple_selection2=None,
                 distancemin=0,
                 distancemax=100,
                 resolution=1.0,
                 kappa=1.0,
                 root_hier=None,
                 label=None,
                 weight=1.):
        """Setup distance restraint.
        @param representation DEPRECATED
        @param tuple_selection1 (resnum, resnum, molecule name, copy
               number (=0))
        @param tuple_selection2 (resnum, resnum, molecule name, copy
               number (=0))
        @param distancemin The minimum dist
        @param distancemax The maximum dist
        @param resolution For selecting particles
        @param kappa The harmonic parameter
        @param root_hier The hierarchy to select from (use this instead of
               representation)
        @param label A unique label to be used in outputs and
                     particle/restraint names
        @param weight Weight of restraint
        \note Pass the same resnum twice to each tuple_selection. Optionally
              add a copy number (PMI2 only)
        """
        if tuple_selection1 is None or tuple_selection2 is None:
            raise Exception("You must pass tuple_selection1/2")
        ts1 = IMP.core.HarmonicUpperBound(distancemax, kappa)
        ts2 = IMP.core.HarmonicLowerBound(distancemin, kappa)

        if representation and not root_hier:
            m = representation.prot.get_model()
            particles1 = IMP.pmi.tools.select(representation,
                                              resolution=resolution,
                                              name=tuple_selection1[2],
                                              residue=tuple_selection1[0])
            particles2 = IMP.pmi.tools.select(representation,
                                              resolution=resolution,
                                              name=tuple_selection2[2],
                                              residue=tuple_selection2[0])
        elif root_hier and not representation:
            m = root_hier.get_model()
            copy_num1 = 0
            if len(tuple_selection1) > 3:
                copy_num1 = tuple_selection1[3]
            copy_num2 = 0
            if len(tuple_selection2) > 3:
                copy_num2 = tuple_selection2[3]

            sel1 = IMP.atom.Selection(root_hier,
                                      resolution=resolution,
                                      molecule=tuple_selection1[2],
                                      residue_index=tuple_selection1[0],
                                      copy_index=copy_num1)
            particles1 = sel1.get_selected_particles()
            sel2 = IMP.atom.Selection(root_hier,
                                      resolution=resolution,
                                      molecule=tuple_selection2[2],
                                      residue_index=tuple_selection2[0],
                                      copy_index=copy_num2)
            particles2 = sel2.get_selected_particles()
        else:
            raise Exception("Pass representation or root_hier, not both")

        super(DistanceRestraint, self).__init__(m, label=label, weight=weight)
        print(self.name)

        print("Created distance restraint between "
              "%s and %s" % (particles1[0].get_name(),
                             particles2[0].get_name()))

        if len(particles1) > 1 or len(particles2) > 1:
            raise ValueError("more than one particle selected")

        self.rs.add_restraint(
            IMP.core.DistanceRestraint(self.m, ts1,
                                       particles1[0],
                                       particles2[0]))
        self.rs.add_restraint(
            IMP.core.DistanceRestraint(self.m, ts2,
                                       particles1[0],
                                       particles2[0]))


class TorqueRestraint(IMP.Restraint):
    import math
    def __init__(self, m, objects, resolution, angular_tolerance,label='None'):
        IMP.Restraint.__init__(self, m, "TorqueRestraint %1%")
        self.softness_angle = 0.5
        self.plateau = 1e-10
        self.weight = 1.0
        self.m=m
        hierarchies = IMP.pmi.tools.input_adaptor(objects,
                                            resolution,
                                            flatten=True)
        self.particles = [h.get_particle() for h in hierarchies]
        self.ds=[IMP.core.XYZ(p) for p in self.particles]
        self.label=label
        self.at=angular_tolerance

    def get_angle_probability(self,xyz,angle_center):
        maxtheta=angle_center+self.at
        mintheta=angle_center-self.at
        angle=self.math.atan2(xyz.get_y(),xyz.get_x() )*180.0/self.math.pi
        anglediff = (angle - maxtheta + 180 + 360) % 360 - 180
        argvalue1=anglediff / self.softness_angle
        anglediff = (angle - mintheta + 180 + 360) % 360 - 180
        argvalue2=-anglediff / self.softness_angle
        prob = (1.0-self.plateau) / (1.0 + self.math.exp(-max(argvalue1,argvalue2)))
        return prob

    def unprotected_evaluate(self, da):
        s=0.0
        center=IMP.core.get_centroid(self.ds)
        angle_center=self.math.atan2(center[1],center[0])*180.0/self.math.pi
        for xyz in self.ds:
            s+=-self.math.log(1.0-self.get_angle_probability(xyz,angle_center))
        return s

    def do_get_inputs(self):
        return self.particles

    def add_to_model(self):
        IMP.pmi.tools.add_restraint_to_model(self.m, self)

    def get_output(self):
        self.m.update()
        output = {}
        score = self.weight * self.unprotected_evaluate(None)
        output["_TotalScore"] = str(score)
        output["TorqueRestraint_" + self.label] = str(score)
        return output




class CylinderRestraint(IMP.Restraint):
    '''
    PMI2 python restraint. Restrains particles within a
    Cylinder aligned along the z-axis and
    centered in x,y=0,0
    Optionally, one can restrain the cylindrical angle
    '''
    import math
    def __init__(self, m, objects, resolution, radius,mintheta=None,
                 maxtheta=None,repulsive=False,label='None'):
        '''
        @param objects PMI2 objects
        @param resolution the resolution you want the restraint to be applied
        @param radius the radius of the cylinder
        @param mintheta minimum cylindrical angle in degrees
        @param maxtheta maximum cylindrical angle in degrees
        '''
        IMP.Restraint.__init__(self, m, "CylinderRestraint %1%")
        self.radius=radius
        self.softness = 3.0
        self.softness_angle = 0.5
        self.plateau = 1e-10
        self.weight = 1.0
        self.m=m
        self.mintheta=mintheta
        self.maxtheta=maxtheta
        self.repulsive=repulsive
        hierarchies = IMP.pmi.tools.input_adaptor(objects,
                                            resolution,
                                            flatten=True)
        self.particles = [h.get_particle() for h in hierarchies]
        self.label=label

    def get_probability(self,p):
        xyz=IMP.core.XYZ(p)
        r=self.math.sqrt(xyz.get_x()**2+xyz.get_y()**2)
        argvalue=(r-self.radius) / self.softness
        if self.repulsive: argvalue=-argvalue
        prob = (1.0 - self.plateau) / (1.0 + self.math.exp(-argvalue))
        return prob

    def get_angle_probability(self,p):
        xyz=IMP.core.XYZ(p)
        angle=self.math.atan2(xyz.get_y(),xyz.get_x() )*180.0/self.math.pi
        anglediff = (angle - self.maxtheta + 180 + 360) % 360 - 180
        argvalue1=anglediff / self.softness_angle
        anglediff = (angle - self.mintheta + 180 + 360) % 360 - 180
        argvalue2=-anglediff / self.softness_angle
        prob = (1.0-self.plateau) / (1.0 + self.math.exp(-max(argvalue1,argvalue2)))
        return prob

    def unprotected_evaluate(self, da):
        s=0.0
        for p in self.particles:
            s+=-self.math.log(1.0-self.get_probability(p))
            if self.mintheta is not None and self.maxtheta is not None:
                s+=-self.math.log(1.0-self.get_angle_probability(p))
        return s

    def do_get_inputs(self):
        return self.particles

    def add_to_model(self):
        IMP.pmi.tools.add_restraint_to_model(self.m, self)

    def get_output(self):
        self.m.update()
        output = {}
        score = self.weight * self.unprotected_evaluate(None)
        output["_TotalScore"] = str(score)
        output["CylinderRestraint_" + self.label] = str(score)
        return output


class NStableDistanceRestraint(IMP.pmi.restraints.RestraintBase):

    """An N-welled harmonic potential."""

    def __init__(self, m, p1, p2, dists, sigmas, weights, label=None,
                 weight=1.):
        """Setup restraint.
        @param m Model
        @param p1 Particle with XYZ coordinates
        @param p2 Particle with XYZ coordinates
        @param dists List of equilibrium distances for potentials.
        @param sigmas List of standard deviations of the potentials
        @param weights List of weights (populations) to apply to the
                       potentials. Must sum to 1.
        @param label A unique label to be used in outputs and
                     particle/restraint names.
        @param weight Weight of restraint
        """
        super(NStableDistanceRestraint, self).__init__(m, label=label,
                                                       weight=weight)

        if sum(weights) != 1.:
            raise ValueError("The sum of the weights must be one")

        hss = [IMP.core.Harmonic(d, 1. / s**2) for d, s in zip(dists, sigmas)]
        wss = IMP.core.WeightedSumOfExponential(hss, weights, 1.)

        r = IMP.core.DistanceRestraint(self.m, wss, p1, p2)
        self.rs.add_restraint(r)


class BiStableDistanceRestraint(NStableDistanceRestraint):

    """A two-welled harmonic potential.

    Authors: G. Bouvier, R. Pellarin. Pasteur Institute.
    """

    def __init__(self, m, p1, p2, dist1, dist2, sigma1, sigma2, weight1,
                 weight2, label=None, weight=1.):
        """Setup restraint.
        @param m Model
        @param p1 Particle with XYZ coordinates
        @param p2 Particle with XYZ coordinates
        @param dist1 Equilibrium distance for first potential
        @param dist2 Equilibrium distance for second potential
        @param sigma1 Standard deviation for first potential
        @param sigma2 Standard deviation for second potential
        @param weight1 Weight (population) of first potential
        @param weight2 Weight (population) of second potential
        @param label A unique label to be used in outputs and
                     particle/restraint names.
        @param weight Weight of restraint
        """
        return super(BiStableDistanceRestraint, self).__init__(
            m, p1, p2, [dist1, dist2], [sigma1, sigma2], [weight1, weight2],
            label=label, weight=weight)


class DistanceToPointRestraint(IMP.pmi.restraints.RestraintBase):

    """Restraint for anchoring a particle to a specific coordinate."""

    def __init__(self,
                 representation=None,
                 tuple_selection=None,
                 anchor_point=IMP.algebra.Vector3D(0, 0, 0),
                 radius=10.0,
                 kappa=10.0,
                 resolution=1.0,
                 weight=1.0,
                 root_hier=None,
                 label=None):
        """Setup distance restraint.
        @param representation DEPRECATED
        @param tuple_selection (resnum, resnum, molecule name,
               copy number (=0))
        @param anchor_point Point to which to restrain particle
               (IMP.algebra.Vector3D object)
        @param radius Size of the tolerance length
        @param kappa The harmonic parameter
        @param resolution For selecting a particle
        @param weight Weight of restraint
        @param root_hier The hierarchy to select from (use this instead of
               representation)
        @param label A unique label to be used in outputs and
                     particle/restraint names
        \note Pass the same resnum twice to each tuple_selection. Optionally
              add a copy number (PMI2 only)
        """
        if tuple_selection is None:
            raise Exception("You must pass a tuple_selection")

        if representation and not root_hier:
            m = representation.prot.get_model()
            ps = IMP.pmi.tools.select(representation,
                                      resolution=resolution,
                                      name=tuple_selection[2],
                                      residue=tuple_selection[0])
        elif root_hier and not representation:
            m = root_hier.get_model()
            copy_num1 = 0
            if len(tuple_selection) > 3:
                copy_num1 = tuple_selection[3]

            sel1 = IMP.atom.Selection(root_hier,
                                      resolution=resolution,
                                      molecule=tuple_selection[2],
                                      residue_index=tuple_selection[0],
                                      copy_index=copy_num1)
            ps = sel1.get_selected_particles()
        else:
            raise Exception("%s: Pass representation or root_hier, not both" %
                            self.name)
        if len(ps) > 1:
            raise ValueError("%s: more than one particle selected" %
                             self.name)

        super(DistanceToPointRestraint, self).__init__(m, label=label,
                                                       weight=weight)
        self.radius = radius

        ub3 = IMP.core.HarmonicUpperBound(self.radius, kappa)
        if anchor_point is None:
            c3 = IMP.algebra.Vector3D(0, 0, 0)
        elif type(anchor_point) is IMP.algebra.Vector3D:
            c3 = anchor_point
        else:
            raise Exception(
                "%s: @param anchor_point must be an algebra.Vector3D object" %
                self.name)
        ss3 = IMP.core.DistanceToSingletonScore(ub3, c3)

        lsc = IMP.container.ListSingletonContainer(self.m)
        lsc.add(ps)

        r3 = IMP.container.SingletonsRestraint(ss3, lsc)
        self.rs.add_restraint(r3)

        print("\n%s: Created distance_to_point_restraint between "
              "%s and %s" % (self.name, ps[0].get_name(), c3))
