# TODO: See how modified protein residues are affected
import ProtoCaller as _PC
if not _PC.MODELLER:
    raise ImportError("BioSimSpace module cannot be imported")

from contextlib import redirect_stdout as _redirect_stdout
import copy as _copy
import logging as _logging
import os as _os
import re as _re
import sys as _sys
import warnings as _warnings

import modeller as _modeller
import modeller.automodel as _modellerautomodel

import ProtoCaller.IO as _IO

__all__ = ["modellerTransform", "FASTA2PIR"]


# taken from https://salilab.org/modeller/manual/node36.html
class MyLoop(_modellerautomodel.loopmodel):
    def __init__(self, filename=None, *args, **kwargs):
        super(MyLoop, self).__init__(*args, **kwargs)
        if filename is not None:
            self.pdb = _IO.PDB.PDB(filename)
            self.total_residue_list = self.pdb.totalResidueList()
            self.transformed_total_residue_list = self._transform_id(self.total_residue_list)
            self.transformed_missing_residue_list = [self.transformed_total_residue_list[i]
                                                     for i, res in enumerate(self.total_residue_list)
                                                     if type(res) == _IO.PDB.MissingResidue]
        else:
            raise ValueError("Need to specify input PDB filename")

        self.selection = _modeller.selection()

    def select_loop_atoms(self):
        for residue in self.transformed_missing_residue_list:
            try:
                self.selection.add(self.residues[residue])
            except KeyError:
                try:
                    self.selection.add(self.residues[residue[:-2]])
                except KeyError:
                    _warnings.warn("Error while selecting missing residue: %s. "
                                   "Residue either missing from FASTA sequence"
                                   " or there  is a problem with Modeller." %
                                   residue)
        return self.selection

    @staticmethod
    def _transform_id(reslist):
        modified_id_list = []
        for i, res in enumerate(reslist):
            modified_id_list += ["{}:{}".format(i + 1, res.chainID)]
        return modified_id_list


def modellerTransform(filename_pdb, filename_fasta, add_missing_atoms,
                      pdb_code=None, refinement="very_fast"):
    """
    Adds missing residues and (optionally) missing atoms to a PDB file.

    Parameters
    ----------
    filename_pdb : str
        Name of the input PDB file.
    filename_fasta : str
        Name of the input sequence FASTA file.
    add_missing_atoms : bool
        Whether to add missing atoms.
    pdb_code : bool
        The PDB code of the PDB file. Default: the PDB filename.
    refinement : str, None
        Level of MD refinement. Allowed values are: None, "very_fast", "fast",
        "slow", "very_slow", "slow_large".

    Returns
    -------
    filename_output : str
        Absolute path to the modified file.
    """
    if not pdb_code:
        pdb_code = _os.path.splitext(_os.path.basename(filename_pdb))[0]
    _logging.basicConfig(stream=_sys.stdout)
    _logging.write = lambda msg: _logging.info(msg.strip()) \
        if msg.strip() else None
    with _redirect_stdout(_logging):
        _modeller.log.verbose()
        env = _modeller.environ()

        # convert FASTA to PIR
        filename_pir = FASTA2PIR(filename_pdb, filename_fasta)

        m = MyLoop(env=env,
                   alnfile=filename_pir,
                   knowns="PROT",
                   filename=filename_pdb,
                   sequence=pdb_code.upper(),  # code of the target
                   loop_assess_methods=_modeller.automodel.assess.DOPE)

        refinement_dict = {
            "very_fast": _modeller.automodel.refine.very_fast,
            "fast": _modeller.automodel.refine.fast,
            "slow": _modeller.automodel.refine.slow,
            "very_slow": _modeller.automodel.refine.very_slow,
            "slow_large": _modeller.automodel.refine.slow_large,
        }

        if refinement and refinement not in refinement_dict.keys():
            _warnings.warn("Refinement option {} not supported. Valid "
                           "refinement options: {}. Continuing with very fast "
                           "refinement...".format(refinement,
                                                  list(refinement_dict.keys())))
        if refinement:
            m.loop.md_level = refinement_dict[refinement]
        else:
            m.loop.md_level = None

        m.auto_align()  # get an automatic alignment
        m.make()

        return fixModellerPDB(m, add_missing_atoms,
                              filename_output=pdb_code + "_modeller.pdb")


def FASTA2PIR(filename_pdb, filename_fasta):
    """
    Converts a FASTA file into a PIR file using a PDB sequence.

    Parameters
    ----------
    filename_pdb : str
        Name of the input PDB file.
    filename_fasta : str
        Name of the input FASTA file.

    Returns
    -------
    filename_output : str
        Name of the output PIR file.
    """
    sequence = _IO.PDB.PDB(filename_pdb).sequence.replace("/", "-")
    sequence_lines = [sequence[i:i+80] for i in range(0, len(sequence), 80)]
    file = open(filename_fasta).readlines()
    pdb_code = ""
    new_file = []

    for line in file:
        if not pdb_code:
            match = _re.search(r">([\w]{4})", line)
            if match:
                pdb_code = match.group(1)
            new_file = [">P1;%s\nsequence:::::::::\n" % pdb_code]
        else:
            if _re.search(r">[\w]{4}", line):
                new_file += "/"
            else:
                new_file += line

    filename_output = pdb_code + ".pir"
    with open(filename_output, "w") as file:
        file.write(">P1;PROT\nstructureX:%s:FIRST:@:::::-1.00:-1.00\n" %
                   pdb_code)
        for i, line in enumerate(sequence_lines):
            file.write(line)
            if i != len(sequence_lines) - 1:
                file.write("\n")
        file.write("*\n\n")
        for i, line in enumerate(new_file):
            if i != len(new_file) - 1:
                file.write(line)
            else:
                file.write(line[:-1])
        file.write("*")

    return filename_output


def fixModellerPDB(model, add_missing_atoms, filename_output=None):
    """
    Used to regenerate some data lost by Modeller.

    Parameters
    ----------
    model : modeller.automodel.loopmodel
        Input model.
    add_missing_atoms : bool
        Whether missing atoms have been added.
    filename_output : str
        Name of the fixed output PDB file.

    Returns
    -------
    filename_output : str
        The absolute path to the fixed output PDB file.
    """
    try:
        filename_modified = model.loop.outputs[0]['name']
    except:
        raise FileNotFoundError("Modeller failed to create file. Please see "
                                "the log.")

    pdb_modified = _IO.PDB.PDB(filename_modified)

    all_res_mod = pdb_modified.totalResidueList()
    all_res_orig = model.pdb.totalResidueList()
    if len(all_res_orig) != len(all_res_mod):
        raise ValueError("Mismatch between original number of residues ({}) "
                         "and number of residues output by Modeller ({}).".
                         format(len(all_res_orig), len(all_res_mod)))

    for miss_res in model.pdb.missing_residues:
        fixed_res = _copy.copy(all_res_mod[all_res_orig.index(miss_res)])
        fixed_res.chainID = miss_res.chainID
        fixed_res.resSeq = miss_res.resSeq
        if fixed_res.resName != miss_res.resName:
            _warnings.warn("Mismatch between original residue name ({}) "
                           "and the residue name output by Modeller ({}) in "
                           "chain {}, residue number {}.".format(
                           miss_res.resName, fixed_res.resName,
                           miss_res.chainID, miss_res.resSeq))
        chain = model.pdb.filter("chainID=='{}'".format(miss_res.chainID),
                                 type="chains")[0]

        if miss_res > chain[-1]:
            chain.append(fixed_res)
        else:
            for i, res in enumerate(chain):
                if res > miss_res:
                    chain.insert(i, fixed_res)
                    break
    model.pdb.missing_residues = []

    if add_missing_atoms:
        for missing_atom in model.pdb.missing_atoms:
            filter = "chainID=='{}'&resSeq=={}&iCode=='{}'".format(
                missing_atom.chainID, missing_atom.resSeq, missing_atom.iCode)
            res = model.pdb.filter(filter)[0]
            fixed_res = all_res_mod[all_res_orig.index(res)]
            fixed_res.chainID = missing_atom.chainID
            fixed_res.resSeq = missing_atom.resSeq
            res.__init__(fixed_res)
        model.pdb.missing_atoms = []

    model.pdb.reNumberAtoms()
    model.pdb.reNumberResidues()
    if filename_output is None:
        filename_output = _os.path.splitext(model.pdb.filename)[0] + \
                          "_modified.pdb"

    return model.pdb.writePDB(filename_output)
