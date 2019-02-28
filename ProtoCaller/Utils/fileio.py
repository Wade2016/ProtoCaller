import atexit as _atexit
import os as _os
import shutil as _shutil


class Dir:
    """
    A class that handles directory changes in Python in a more intuitive way.

    Parameters
    ----------
    dirname : str
        Initialises dirname.
    copydirname : str or None
        Initialises copydirname.
    overwrite : bool
        Initialises overwrite.
    temp : bool
        Initialises temp.
    purge_immediately : bool
        Initialise purge_immediately.


    Attributes
    ----------
    workdirname : str
        The absolute path to the parent directory of Dir.
    dirname : str
        The directory name.
    copydirname : str or None
        If not None, copies the directory in copydirname as a basis for Dir.
    path : str
        Full absolute path of the directory.
    overwrite : bool
        Whether to overwrite any directories with the same name as Dir.
    temp : bool
        If True, the directory is deleted upon __exit__.
    purge_immediately : bool
        If True, the directory is only deleted upon program exit. Only valid if temp is True.
    initialdirnames : [str]
        Keeps track of different places from which __enter__ has been called in order to avoid mistakes.
    """
    def __init__(self, dirname, copydirname=None, overwrite=False, temp=False, purge_immediately=True):
        if _os.path.isabs(dirname):
            self.workdirname = _os.path.dirname(dirname)
        else:
            self.workdirname = _os.getcwd()
        self.dirname = _os.path.basename(dirname)
        self.copydirname = copydirname
        self.overwrite = overwrite
        self.temp = temp
        self.purge_immediately = purge_immediately
        self.initialdirnames = []

    def __enter__(self):
        self.initialdirnames += [_os.getcwd()]
        if not _os.path.exists(self.workdirname):
            _os.makedirs(self.workdirname)
        _os.chdir(self.workdirname)
        if self.overwrite and _os.path.exists(self.dirname):
            _shutil.rmtree("%s/%s" % (self.workdirname, self.dirname))
        if self.overwrite and self.copydirname and _os.path.exists(self.copydirname):
            _shutil.copytree("%s/%s" % (self.workdirname, self.copydirname), "%s/%s" % (self.workdirname, self.dirname))
        elif not _os.path.exists(self.dirname):
            _os.makedirs(self.dirname)
        _os.chdir(self.dirname)
        self.path = "%s/%s" % (self.workdirname, self.dirname)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        _os.chdir(self.workdirname)
        # removes temporary directory at the end of execution
        if self.temp:
            def delete():
                try:
                    _shutil.rmtree(self.path)
                except:
                    pass

            if self.purge_immediately:
                delete()
            else:
                _atexit.register(delete)
        _os.chdir(self.initialdirnames.pop())


def checkFileExists(file):
    """A simple wrapper around os.path.exists which throws an error if False."""
    file = _os.path.abspath(file)
    if not _os.path.exists(file):
        raise ValueError("File %s does not exist. Please provide a valid filename." % file)
    return file
