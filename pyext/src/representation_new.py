import IMP
import IMP.atom
import IMP.pmi
from collections import defaultdict
import structure_tools
from Bio import SeqIO

"""
A new representation module. It helps to construct the hierarchy
and deal with multi-state, multi-scale, multi-copies

Usage Example:

see representation_new_test.py

For each of the classes System, State, and Molecule, you store the root node and
  references to child classes (System>State>Molecule).
When you call Build() on any of these classes, Build() is also called for each of the child classes,
and the root IMP hierarchy is returned.
"""

#------------------------


class _SystemBase(object):
    """This is the base class for System, _State and _Molecule
    classes. It contains shared functions in common to these classes
    """

    def __init__(self,mdl=None):
        if mdl is None:
            self.mdl=IMP.Model()
        else:
            self.mdl=mdl

    def _create_hierarchy(self):
        """create a new hierarchy"""
        tmp_part=IMP.kernel.Particle(self.mdl)
        return IMP.atom.Hierarchy.setup_particle(tmp_part)

    def _create_child(self,parent_hierarchy):
        """create a new hierarchy, set it as child of the input
        one, and return it"""
        child_hierarchy=self._create_hierarchy()
        parent_hierarchy.add_child(child_hierarchy)
        return child_hierarchy

    def build(self):
        """Build the coordinates of the system.
        Loop through stored(?) hierarchies and set up coordinates!"""
        pass

#------------------------

class System(_SystemBase):
    """This class initializes the root node of the global IMP.atom.Hierarchy."""
    def __init__(self,mdl=None):
        _SystemBase.__init__(self,mdl)
        self._number_of_states = 0
        self.states = []
        self.built=False

        # the root hierarchy node
        self.system=self._create_hierarchy()
        self.system.set_name("System")

    def create_state(self):
        """returns a new IMP.pmi.representation_new._State(), increment the state index"""
        self._number_of_states+=1
        state = _State(self.system,self._number_of_states-1)
        self.states.append(state)
        return state

    def get_number_of_states(self):
        """returns the total number of states generated"""
        return self._number_of_states

    def build(self):
        """call build on all states"""
        if not self.built:
            for state in self.states:
                state.build()
            self.built=True
        return self.system

#------------------------

class _State(_SystemBase):
    """This private class is constructed from within the System class.
    It wrapps an IMP.atom.State
    """
    def __init__(self,system_hierarchy,state_index):
        """Define a new state
        @param system_hierarchy     the parent root hierarchy
        @param state_index          the index of the new state
        """
        self.mdl = system_hierarchy.get_model()
        self.system = system_hierarchy
        self.state = self._create_child(system_hierarchy)
        self.state.set_name("State_"+str(state_index))
        self.molecules = []
        IMP.atom.State.setup_particle(self.state,state_index)
        self.built=False

    def create_molecule(self,name,sequence=None,molecule_to_copy=None):
        """Create a new Molecule within this State
        @param name       the name of the molecule (string)
        @param sequence            sequence (string)
        """
        mol = _Molecule(self.state,name,sequence)
        self.molecules.append(mol)
        return mol

    def build(self):
        """call build on all molecules (automatically makes copies)"""
        if not self.built:
            for mol in self.molecules:
                mol.build()
            self.built=True
        return self.state

#------------------------

class _Molecule(_SystemBase):
    """This private class is constructed from within the State class.
    It wraps an IMP.atom.Molecule and IMP.atom.Copy
    Structure is read using this class
    Resolutions and copies can be registered, but are only created when build() is called
    """

    def __init__(self,state_hierarchy,name,sequence):
        """Create copy 0 of this molecule.
        Arguments:
        @param state_hierarchy     the parent State-decorated hierarchy (IMP hier)
        @param name       the name of the molecule (string)
        @param sequence            sequence (string)
        """
        # internal data storage
        self.mdl=state_hierarchy.get_model()
        self.state=state_hierarchy
        self.name=name
        self.sequence=sequence
        self.number_of_copies=1
        self.built=False

        # create root node and set it as child to passed parent hierarchy
        self.molecule=self._create_child(self.state)
        self.molecule.set_name(self.name+"_0")
        IMP.atom.Copy.setup_particle(self.molecule,0)

        # create Residues from the sequence
        self.residues=[]
        for ns,s in enumerate(sequence):
            r=Residue(s,ns,ns+1)
            self.residues.append(r)

    def add_copy(self):
        """Register a new copy of the Molecule.
        Copies are only constructed when Build() is called.
        """
        self.number_of_copies+=1

    def add_structure(self,pdb_fn,chain,res_range=None,offset=0):
        """Read a structure and store the coordinates.
        Returns the atomic Residue ranges
        @param pdb_fn The file to read
        @param chain  Chain ID to read
        @param res_range Add only a specific set of residues
        @param offset Apply an offset to the residue indexes of the PDB file
        \note After offset, we expect the PDB residue numbering to match the FASTA file
        """
        rhs=structure_tools.get_structure(self.mdl,pdb_fn,chain,res_range,offset)
        if len(rhs)>len(self.residues):
            print 'ERROR: You are loading',len(rhs), \
                'pdb residues for a sequence of length',len(self.residues),'(too many)'
        ret=[]
        prev_idx=rhs[0].get_index()-1
        cur_range=[rhs[0],rhs[0]]
        for rh in rhs:
            idx=rh.get_index()
            if self.residues[idx-1].code!=IMP.atom.get_one_letter_code(rh.get_residue_type()):
                print 'ERROR: PDB residue is',IMP.atom.get_one_letter_code(rh.get_residue_type()), \
                    'and sequence residue is',self.residues[idx-1].code
            self.residues[idx-1].set_structure(rh)
            if idx!=prev_idx+1:
                ret.append(cur_range)
                cur_range=[rh,rh]
            else:
                cur_range[1]=rh
            prev_idx=idx
        ret.append(cur_range)
        return ret

    def set_representation(self,res_ranges=None):
        """handles the IMP.atom.Representation decorators, such as multi-scale,
        density, etc."""
        pass

    def build(self):
        """Create all parts of the IMP hierarchy
        including Atoms, Residues, and Fragments/Representations and, finally, Copies
        cur_rep={}
        if backbone:
        # loop along backbone and group things if they have the same representations
        for res in self.residues:
        if res.rep!=cur_rep:
        start_new_fragment()
        if volume:
        # group things by resolution and break into fragments by volume
        for each resolution X:
        for all residues at resolution X:
        group by volume
        """

        if not self.built:
            # group into Fragments either along backbone or using volume
            #    ...

            # create copies
            for nc in range(1,self.number_of_copies):
                mhc=self._create_child(self.state)
                mhc.set_name(self.name+"_%i"%nc)
                IMP.atom.Copy.setup_particle(mhc,nc)
                # DEEP COPY
                # ...

            self.built=True
        return self.molecule


#------------------------

class Sequences(object):
    """A dictionary-like wrapper for reading and storing sequence data"""
    def __init__(self,fasta_fn,name_map=None):
        """read a fasta file and extract all the requested sequences
        @param fasta_fn sequence file
        @param name_map dictionary mapping the fasta name to the stored name
        """
        self.sequences={}
        self.read_sequences(fasta_fn,name_map)
    def __len__(self):
        return len(self.sequences)
    def __contains__(self,x):
        return x in self.sequences
    def __getitem__(self,key):
        return self.sequences[key]
    def read_sequences(self,fasta_fn,name_map=None):
        # read all sequences
        handle = open(fasta_fn, "rU")
        record_dict = SeqIO.to_dict(SeqIO.parse(handle, "fasta"))
        handle.close()
        if name_map is None:
            for pn in record_dict:
                self.sequences[pn]=str(record_dict[pn].seq).replace("*", "")
        else:
            for pn in name_map:
                try:
                    self.sequences[name_map[pn]]=str(record_dict[pn].seq).replace("*", "")
                except:
                    print "tried to add sequence but: id %s not found in fasta file" % pn
                    exit()

#------------------------

class Residue(object):
    """Stores basic residue information, even without structure available."""
    def __init__(self,code,num,index):
        """setup a Residue
        @param code one-letter residue type code
        @param num  PDB-style residue number
        @param index internal integer index
        """
        self.code = code
        self.index = index
        self.num = num
        self.res = None
        representations = defaultdict(set)
    def __str__(self):
        return code
    def set_structure(self,res_hier):
        self.res = res_hier
    def add_representation(self,rep_type,resolutions):
        self.representations[rep_type] &= set(resolutions)
