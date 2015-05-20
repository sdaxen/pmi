"""@namespace IMP.pmi.samplers
   Sampling of the system.
"""

from __future__ import print_function
import IMP
import IMP.core
from IMP.pmi.tools import get_restraint_set

class _SerialReplicaExchange(object):
    """Dummy replica exchange class used in non-MPI builds.
       It should act similarly to IMP.mpi.ReplicaExchange on a single processor.
    """
    def __init__(self):
        self.__params = {}
    def get_number_of_replicas(self):
        return 1
    def create_temperatures(self, tmin, tmax, nrep):
        return [tmin]
    def get_my_index(self):
        return 0
    def set_my_parameter(self, key, val):
        self.__params[key] = val
    def get_my_parameter(self, key):
        return self.__params[key]
    def get_friend_index(self, step):
        return 0
    def get_friend_parameter(self, key, findex):
        return self.get_my_parameter(key)
    def do_exchange(self, myscore, fscore, findex):
        return False


class MonteCarlo(object):
    """Sample using Monte Carlo"""

    # check that isd is installed
    try:
        import IMP.isd
        isd_available = True
    except ImportError:
        isd_available = False

    def __init__(self, m, objects, temp, filterbyname=None):
        # check that the objects containts get_particles_to_sample methods
        # and the particle type is supported
        # list of particles to sample self.losp

        self.losp = [
            "Rigid_Bodies",
            "Floppy_Bodies",
            "Nuisances",
            "X_coord",
            "Weights"]
        self.simulated_annealing = False
        self.selfadaptive = False
        # that is -1 because mc has not yet run
        self.nframe = -1
        self.temp = temp
        self.mvs = []
        self.mvslabels = []
        self.label = "None"
        self.m = m

        for ob in objects:
            try:
                ob.get_particles_to_sample()
            except:
                print("MonteCarlo: object ", ob, " doesn't have get_particles_to_sample() method")

            pts = ob.get_particles_to_sample()
            for k in pts.keys():

                if "Rigid_Bodies" in k:
                    mvs = self.get_rigid_body_movers(
                        pts[k][0],
                        pts[k][1],
                        pts[k][2])
                    for mv in mvs:
                        mv.set_name(k)
                    self.mvs += mvs

                if "SR_Bodies" in k:
                    print(len(pts[k]))
                    mvs = self.get_super_rigid_body_movers(
                        pts[k][0],
                        pts[k][1],
                        pts[k][2])
                    for mv in mvs:
                        mv.set_name(k)
                    self.mvs += mvs

                if "Floppy_Bodies" in k:
                    mvs = self.get_floppy_body_movers(pts[k][0], pts[k][1])
                    for mv in mvs:
                        mv.set_name(k)
                    self.mvs += mvs

                if "X_coord" in k:
                    mvs = self.get_X_movers(pts[k][0], pts[k][1])
                    for mv in mvs:
                        mv.set_name(k)
                    self.mvs += mvs

                if "Nuisances" in k:
                    if not self.isd_available:
                        raise ValueError("isd module needed to use nuisances")
                    mvs = self.get_nuisance_movers(pts[k][0], pts[k][1])
                    for mv in mvs:
                        mv.set_name(k)
                    self.mvs += mvs

                if "Weights" in k:
                    if not self.isd_available:
                        raise ValueError("isd module needed to use weights")
                    mvs = self.get_weight_movers(pts[k][0], pts[k][1])
                    for mv in mvs:
                        mv.set_name(k)
                    self.mvs += mvs

        # SerialMover
        self.smv = IMP.core.SerialMover(self.mvs)

        self.mc = IMP.core.MonteCarlo(self.m)
        self.mc.set_scoring_function(get_restraint_set(self.m))
        self.mc.set_return_best(False)
        self.mc.set_kt(self.temp)
        self.mc.add_mover(self.smv)

    def set_kt(self, temp):
        self.temp = temp
        self.mc.set_kt(temp)

    def get_mc(self):
        return self.mc

    def set_scoring_function(self, objectlist):
        rs = IMP.RestraintSet(self.m, 1.0, 'sfo')
        for ob in objectlist:
            rs.add_restraint(ob.get_restraint())
        sf = IMP.core.RestraintsScoringFunction([rs])
        self.mc.set_scoring_function(sf)

    def set_simulated_annealing(
        self,
        min_temp,
        max_temp,
        min_temp_time,
            max_temp_time):
        self.simulated_annealing = True
        self.tempmin = min_temp
        self.tempmax = max_temp
        self.timemin = min_temp_time
        self.timemax = max_temp_time

    def set_self_adaptive(self, isselfadaptive=True):
        self.selfadaptive = isselfadaptive

    def get_nuisance_movers_parameters(self):
        '''
        Return a dictionary with the mover parameters for nuisance parameters
        '''
        output = {}
        for i in range(self.get_number_of_movers()):
            mv = self.smv.get_mover(i)
            name = mv.get_name()
            if "Nuisances" in name:
                stepsize = IMP.core.NormalMover.get_from(mv).get_sigma()
                output[name] = stepsize
        return output

    def get_number_of_movers(self):
        return len(self.smv.get_movers())

    def get_particle_types():
        return self.losp

    def optimize(self, nstep):
        self.nframe += 1
        self.mc.optimize(nstep * self.get_number_of_movers())

        # apply simulated annealing protocol
        if self.simulated_annealing:
            self.temp = self.temp_simulated_annealing()
            self.mc.set_kt(self.temp)

        # apply self adaptive protocol
        if self.selfadaptive:
            for i, mv in enumerate(self.smv.get_movers()):
                name = mv.get_name()

                if "Nuisances" in name:
                    mvacc = mv.get_number_of_accepted()
                    mvprp = mv.get_number_of_proposed()
                    accept = float(mvacc) / float(mvprp)
                    nmv = IMP.core.NormalMover.get_from(mv)
                    stepsize = nmv.get_sigma()

                    if 0.4 > accept or accept > 0.6:
                        nmv.set_sigma(stepsize * 2 * accept)
                    if accept < 0.05:
                        accept = 0.05
                        nmv.set_sigma(stepsize * 2 * accept)
                    if accept > 1.0:
                        accept = 1.0
                        nmv.set_sigma(stepsize * 2 * accept)

                if "Weights" in name:

                    mvacc = mv.get_number_of_accepted()
                    mvprp = mv.get_number_of_proposed()
                    accept = float(mvacc) / float(mvprp)
                    wmv = IMP.isd.WeightMover.get_from(mv)
                    stepsize = wmv.get_radius()

                    if 0.4 > accept or accept > 0.6:
                        wmv.set_radius(stepsize * 2 * accept)
                    if accept < 0.05:
                        accept = 0.05
                        wmv.set_radius(stepsize * 2 * accept)
                    if accept > 1.0:
                        accept = 1.0
                        wmv.set_radius(stepsize * 2 * accept)

    @IMP.deprecated_method("2.5", "Use optimize() instead.")
    def run(self, *args, **kwargs):
        self.optimize(*args, **kwargs)

    def get_nuisance_movers(self, nuisances, maxstep):
        mvs = []
        for nuisance in nuisances:
            print(nuisance, maxstep)
            mvs.append(
                IMP.core.NormalMover([nuisance],
                                     IMP.FloatKeys([IMP.FloatKey("nuisance")]),
                                     maxstep))
        return mvs

    def get_rigid_body_movers(self, rbs, maxtrans, maxrot):
        mvs = []
        for rb in rbs:
            mvs.append(IMP.core.RigidBodyMover(rb, maxtrans, maxrot))
        return mvs

    def get_super_rigid_body_movers(self, rbs, maxtrans, maxrot):
        mvs = []
        for rb in rbs:
            if len(rb) == 2:
                # normal Super Rigid Body
                srbm = IMP.pmi.TransformMover(self.m, maxtrans, maxrot)
            if len(rb) == 3:
                # super rigid body with 2D rotation, rb[2] is the axis
                srbm = IMP.pmi.TransformMover(
                    self.m,
                    IMP.algebra.Vector3D(rb[2]),
                    maxtrans,
                    maxrot)
            for xyz in rb[0]:
                srbm.add_xyz_particle(xyz)
            for rb in rb[1]:
                srbm.add_rigid_body_particle(rb)
            mvs.append(srbm)
        return mvs

    def get_floppy_body_movers(self, fbs, maxtrans):
        mvs = []
        for fb in fbs:
            # check is that is a rigid body member:
            if IMP.core.NonRigidMember.get_is_setup(fb):
            # if so force the particles to move anyway
                floatkeys = [IMP.FloatKey(4), IMP.FloatKey(5), IMP.FloatKey(6)]
                for fk in floatkeys:
                    fb.set_is_optimized(fk, True)
                mvs.append(
                    IMP.core.BallMover([fb],
                                       IMP.FloatKeys(floatkeys),
                                       maxtrans))
            else:
                # otherwise use the normal ball mover
                mvs.append(IMP.core.BallMover([fb], maxtrans))
        return mvs

    def get_X_movers(self, fbs, maxtrans):
        mvs = []
        Xfloatkey = IMP.core.XYZ.get_xyz_keys()[0]
        for fb in fbs:
            # check is that is a rigid body member:
            if IMP.core.NonRigidMember.get_is_setup(fb):
                raise ValueError("particle is part of a rigid body")
            else:
                # otherwise use the normal ball mover
                mvs.append(IMP.core.NormalMover([fb], [Xfloatkey], maxtrans))
        return mvs

    def get_weight_movers(self, weights, maxstep):
        mvs = []
        for weight in weights:
            if(weight.get_number_of_states() > 1):
                mvs.append(IMP.isd.WeightMover(weight, maxstep))
        return mvs

    def temp_simulated_annealing(self):
        if self.nframe % (self.timemin + self.timemax) < self.timemin:
            value = 0.0
        else:
            value = 1.0
        temp = self.tempmin + (self.tempmax - self.tempmin) * value
        return temp

    def set_label(self, label):
        self.label = label

    def get_frame_number(self):
        return self.nframe

    def get_output(self):
        output = {}
        acceptances = []
        for i, mv in enumerate(self.smv.get_movers()):
            mvname = mv.get_name()
            mvacc = mv.get_number_of_accepted()
            mvprp = mv.get_number_of_proposed()
            try:
                mvacr = float(mvacc) / float(mvprp)
            except:
                mvacr = 0.0
            output["MonteCarlo_Acceptance_" +
                   mvname + "_" + str(i)] = str(mvacr)
            if "Nuisances" in mvname:
                output["MonteCarlo_StepSize_" + mvname + "_" +
                       str(i)] = str(IMP.core.NormalMover.get_from(mv).get_sigma())
            if "Weights" in mvname:
                output["MonteCarlo_StepSize_" + mvname + "_" +
                       str(i)] = str(IMP.isd.WeightMover.get_from(mv).get_radius())
        output["MonteCarlo_Temperature"] = str(self.mc.get_kt())
        output["MonteCarlo_Nframe"] = str(self.nframe)
        return output


class MolecularDynamics(object):
    """Sample using molecular dynamics"""

    def __init__(self,m,objects,kt,gamma=0.01,maximum_time_step=1.0):
        self.m=m
        to_sample=[]
        for obj in objects:
            to_sample+=obj.get_particles_to_sample()['Floppy_Bodies_SimplifiedModel'][0]
        self.ltstate=IMP.atom.LangevinThermostatOptimizerState(self.m,to_sample,
                                                          kt/0.0019872041,
                                                          gamma)
        self.md = IMP.atom.MolecularDynamics(self.m)
        self.md.set_maximum_time_step(maximum_time_step)
        self.md.add_optimizer_state(self.ltstate)
        self.simulated_annealing = False
        self.nframe = -1
    def set_kt(self,kt):
        temp=kt/0.0019872041
        self.ltstate.set_temperature(temp)
        self.md.assign_velocities(temp)

    def set_simulated_annealing(self, min_temp, max_temp, min_temp_time,
                                max_temp_time):
        self.simulated_annealing = True
        self.tempmin = min_temp
        self.tempmax = max_temp
        self.timemin = min_temp_time
        self.timemax = max_temp_time

    def temp_simulated_annealing(self):
        if self.nframe % (self.timemin + self.timemax) < self.timemin:
            value = 0.0
        else:
            value = 1.0
        temp = self.tempmin + (self.tempmax - self.tempmin) * value
        return temp

    def set_gamma(self,gamma):
        self.ltstate.set_gamma(gamma)

    def optimize(self,nsteps):
        # apply simulated annealing protocol
        self.nframe+=1
        if self.simulated_annealing:
            self.temp = self.temp_simulated_annealing()
            self.set_kt(self.temp)
        self.md.optimize(nsteps)

    def get_output(self):
        output={}
        output["MolecularDynamics_KineticEnergy"]=str(self.md.get_kinetic_energy())
        return output

class ConjugateGradients(object):
    """Sample using conjugate gradients"""

    def __init__(self, m, objects):
        self.m = m
        self.nframe = -1
        self.cg = IMP.core.ConjugateGradients(self.m)
        self.cg.set_scoring_function(get_restraint_set(self.m))

    def set_label(self, label):
        self.label = label

    def get_frame_number(self):
        return self.nframe

    @IMP.deprecated_method("2.5", "Use optimize() instead.")
    def run(self, *args, **kwargs):
        self.optimize(*args, **kwargs)

    def optimize(self, nstep):
        self.nframe += 1
        self.cg.optimize(nstep)

    def set_scoring_function(self, objectlist):
        rs = IMP.RestraintSet(self.m, 1.0, 'sfo')
        for ob in objectlist:
            rs.add_restraint(ob.get_restraint())
        sf = IMP.core.RestraintsScoringFunction([rs])
        self.cg.set_scoring_function(sf)

    def get_output(self):
        output = {}
        acceptances = []
        output["ConjugatedGradients_Nframe"] = str(self.nframe)
        return output


class ReplicaExchange(object):
    """Sample using replica exchange"""

    def __init__(
        self,
        model,
        tempmin,
        tempmax,
        samplerobjects,
        test=True,
            replica_exchange_object=None):
        '''
        samplerobjects can be a list of MonteCarlo or MolecularDynamics
        '''


        self.m = model
        self.samplerobjects = samplerobjects
        # min and max temperature
        self.TEMPMIN_ = tempmin
        self.TEMPMAX_ = tempmax

        if replica_exchange_object is None:
            # initialize Replica Exchange class
            try:
                import IMP.mpi
                print('ReplicaExchange: MPI was found. Using Parallel Replica Exchange')
                self.rem = IMP.mpi.ReplicaExchange()
            except ImportError:
                print('ReplicaExchange: Could not find MPI. Using Serial Replica Exchange')
                self.rem = _SerialReplicaExchange()

        else:
            # get the replica exchange class instance from elsewhere
            print('got existing rex object')
            self.rem = replica_exchange_object

        # get number of replicas
        nproc = self.rem.get_number_of_replicas()

        if nproc % 2 != 0 and test == False:
            raise Exception("number of replicas has to be even. set test=True to run with odd number of replicas.")
        # create array of temperatures, in geometric progression
        temp = self.rem.create_temperatures(
            self.TEMPMIN_,
            self.TEMPMAX_,
            nproc)
        # get replica index
        self.temperatures = temp

        myindex = self.rem.get_my_index()
        # set initial value of the parameter (temperature) to exchange
        self.rem.set_my_parameter("temp", [self.temperatures[myindex]])
        for so in self.samplerobjects:
            so.set_kt(self.temperatures[myindex])
        self.nattempts = 0
        self.nmintemp = 0
        self.nmaxtemp = 0
        self.nsuccess = 0

    def get_temperatures(self):
        return self.temperatures

    def get_my_temp(self):
        return self.rem.get_my_parameter("temp")[0]

    def get_my_index(self):
        return self.rem.get_my_index()

    def swap_temp(self, nframe, score=None):
        if score is None:
            score = self.m.evaluate(False)
        # get my replica index and temperature
        myindex = self.rem.get_my_index()
        mytemp = self.rem.get_my_parameter("temp")[0]

        if mytemp == self.TEMPMIN_:
            self.nmintemp += 1

        if mytemp == self.TEMPMAX_:
            self.nmaxtemp += 1

        # score divided by kbt
        myscore = score / mytemp

        # get my friend index and temperature
        findex = self.rem.get_friend_index(nframe)
        ftemp = self.rem.get_friend_parameter("temp", findex)[0]
        # score divided by kbt
        fscore = score / ftemp

        # try exchange
        flag = self.rem.do_exchange(myscore, fscore, findex)

        self.nattempts += 1
        # if accepted, change temperature
        if (flag):
            for so in self.samplerobjects:
                so.set_kt(ftemp)
            self.nsuccess += 1

    def get_output(self):
        output = {}
        acceptances = []
        if self.nattempts != 0:
            output["ReplicaExchange_SwapSuccessRatio"] = str(
                float(self.nsuccess) / self.nattempts)
            output["ReplicaExchange_MinTempFrequency"] = str(
                float(self.nmintemp) / self.nattempts)
            output["ReplicaExchange_MaxTempFrequency"] = str(
                float(self.nmaxtemp) / self.nattempts)
        else:
            output["ReplicaExchange_SwapSuccessRatio"] = str(0)
            output["ReplicaExchange_MinTempFrequency"] = str(0)
            output["ReplicaExchange_MaxTempFrequency"] = str(0)
        output["ReplicaExchange_CurrentTemp"] = str(self.get_my_temp())
        return output


class PyMCMover(object):
    # only works if the sampled particles are rigid bodies

    def __init__(self, representation, mcchild, n_mc_steps):

        # mcchild must be pmi.samplers.MonteCarlo
        # representation must be pmi.representation

        self.rbs = representation.get_rigid_bodies()

        self.mc = mcchild
        self.n_mc_steps = n_mc_steps

    def store_move(self):
        # get all xyz coordinates of all rigid bodies of all copies
        self.oldcoords = []
        for copy in self.rbs:
            crd = []
            for rb in copy:
                crd.append(rb.get_reference_frame())
            self.oldcoords.append(crd)

    def propose_move(self, prob):
        self.mc.run(self.n_mc_steps)

    def reset_move(self):
        # reset each copy to crd
        for copy, crd in zip(self.rbs, self.oldcoords):
            for rb, ref in zip(copy, crd):
                rb.set_reference_frame(ref)

    def get_number_of_steps(self):
        return self.n_mc_steps

    def set_number_of_steps(self, nsteps):
        self.n_mc_steps = nsteps


class PyMC(object):

    def __init__(self, model):
        from math import exp
        import random

        self.m = model
        self.restraints = None
        self.first_call = True
        self.nframe = -1

    def add_mover(self, mv):
        self.mv = mv

    def set_kt(self, kT):
        self.kT = kT

    def set_return_best(self, thing):
        pass

    def set_move_probability(self, thing):
        pass

    def get_energy(self):
        if self.restraints:
            pot = sum([r.evaluate(False) for r in self.restraints])
        else:
            pot = self.m.evaluate(False)
        return pot

    def metropolis(self, old, new):
        deltaE = new - old
        print(": old %f new %f deltaE %f new_epot: %f" % (old, new, deltaE,
                                                          self.m.evaluate(
                                                              False)), end=' ')
        kT = self.kT
        if deltaE < 0:
            return True
        else:
            return exp(-deltaE / kT) > random.uniform(0, 1)

    def optimize(self, nsteps):
        self.naccept = 0
        self.nframe += 1
        print("=== new MC call")
        # store initial coordinates
        if self.first_call:
            self.mv.store_move()
            self.first_call = False
        for i in range(nsteps):
            print("MC step %d " % i, end=' ')
            # get total energy
            old = self.get_energy()
            # make a MD move
            self.mv.propose_move(1)
            # get new total energy
            new = self.get_energy()
            if self.metropolis(old, new):
                # move was accepted: store new conformation
                self.mv.store_move()
                self.naccept += 1
                print("accepted ")
            else:
                # move rejected: restore old conformation
                self.mv.reset_move()
                print(" ")

    def get_number_of_forward_steps(self):
        return self.naccept

    def set_restraints(self, restraints):
        self.restraints = restraints

    def set_scoring_function(self, objects):
        # objects should be pmi.restraints
        rs = IMP.RestraintSet(self.m, 1.0, 'sfo')
        for ob in objects:
            rs.add_restraint(ob.get_restraint())
        self.set_restraints([rs])

    def get_output(self):
        output = {}
        acceptances = []
        output["PyMC_Temperature"] = str(self.kT)
        output["PyMC_Nframe"] = str(self.nframe)
        return output


# 3
