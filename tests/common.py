import os
import subprocess as sp
import tempfile
import shutil
# import json
import unittest
import difflib
from tests.download import downloadpdf
from pathlib import Path
import io
from contextlib import redirect_stdout
import shlex

import papers
from papers import logger, logging
from papers.utils import set_directory
from papers.__main__ import main
from papers.config import CONFIG_FILE, CONFIG_FILE_LOCAL, Config
from papers.bib import Biblio

debug_level = logging.DEBUG
logger.setLevel(debug_level)

# Using python -m papers instead of papers otherwise pytest --cov does not detect the call
PAPERSCMD = f'PYTHONPATH={Path(papers.__file__).parent.parent} python3 -m papers'

def reliable_paperscmd(cmd, sp_cmd=None, cwd=None, **kw):
    return run(f'{PAPERSCMD} '+cmd, sp_cmd=sp_cmd, cwd=cwd, **kw)


def call(f, *args, check=False, check_output=False, cwd=None, **kwargs):
    if check_output:
        out = io.StringIO()
        with redirect_stdout(out):
            f(*args, **kwargs)
        return out.getvalue().strip()

    elif check:
        return f(*args, **kwargs)
    else:
        try:
            f(*args, **kwargs)
            return 0
        except:
            return 1

def speedy_paperscmd(cmd, sp_cmd=None, cwd=None, **kw):
    if '<' in cmd:
        return reliable_paperscmd(cmd, sp_cmd, cwd, **kw)

    logger.setLevel(debug_level)

    check = sp_cmd is None or "check" in sp_cmd
    check_output = sp_cmd == 'check_output'
    args = shlex.split(cmd)
    if cwd:
        with set_directory(cwd):
            return call(main, args, check=check, check_output=check_output)
    else:
        return call(main, args, check=check, check_output=check_output)

def paperscmd(cmd, *args, reliable=None, **kwargs):
    if reliable:
        return reliable_paperscmd(cmd, *args, **kwargs)
    else:
        return speedy_paperscmd(cmd, *args, **kwargs)

def run(cmd, sp_cmd=None, **kw):
    print(cmd)
    if not sp_cmd or sp_cmd == "check_output":
        return str(sp.check_output(cmd, shell=True, **kw).strip().decode())
    else:
        return str(getattr(sp, sp_cmd)(cmd, shell=True, **kw))



def prepare_paper():
    pdf = downloadpdf('bg-8-515-2011.pdf')
    doi = '10.5194/bg-8-515-2011'
    key = 'Perrette_2011'
    newkey = 'perrette_yool2011'
    year = '2011'
    bibtex = """@article{Perrette_2011,
    author = {M. Perrette and A. Yool and G. D. Quartly and E. E. Popova},
    doi = {10.5194/bg-8-515-2011},
    journal = {Biogeosciences},
    month = {feb},
    number = {2},
    pages = {515--524},
    publisher = {Copernicus {GmbH}},
    title = {Near-ubiquity of ice-edge blooms in the Arctic},
    url = {https://doi.org/10.5194%2Fbg-8-515-2011},
    volume = {8},
    year = 2011,
}"""

    file_rename = "perrette_et_al_2011_near-ubiquity-of-ice-edge-blooms-in-the-arctic.pdf"

    return pdf, doi, key, newkey, year, bibtex, file_rename


def prepare_paper2():
    pdf = downloadpdf('esd-4-11-2013.pdf')
    si = downloadpdf('esd-4-11-2013-supplement.pdf')
    doi = '10.5194/esd-4-11-2013'
    key = 'Perrette_2013'
    newkey = 'perrette_landerer2013'
    year = '2013'
    bibtex = """@article{Perrette_2013,
    author = {M. Perrette and F. Landerer and R. Riva and K. Frieler and M. Meinshausen},
    doi = {10.5194/esd-4-11-2013},
    journal = {Earth System Dynamics},
    month = {jan},
    number = {1},
    pages = {11--29},
    publisher = {Copernicus {GmbH}},
    title = {A scaling approach to project regional sea level rise and its uncertainties},
    url = {https://doi.org/10.5194%2Fesd-4-11-2013},
    volume = {4},
    year = 2013,
}"""
    file_rename = "perrette_et_al_2013_a-scaling-approach-to-project-regional-sea-level-rise-and-its-uncertainties.pdf"

    return pdf, si, doi, key, newkey, year, bibtex, file_rename



class BibTest(unittest.TestCase):
    """base class for bib tests: create a new bibliography
    """

    def assertMultiLineEqual(self, first, second, msg=None):
        """Assert that two multi-line strings are equal.

        If they aren't, show a nice diff.
        source: https://stackoverflow.com/a/3943697/2192272
        """
        self.assertTrue(isinstance(first, str),
                'First argument is not a string')
        self.assertTrue(isinstance(second, str),
                'Second argument is not a string')

        if first != second:
            message = ''.join(difflib.ndiff(first.splitlines(True),
                                                second.splitlines(True)))
            if msg:
                message += " : " + msg
            self.fail("Multi-line strings are unequal:\n" + message)




bibtex = """@article{Perrette_2011,
 author = {M. Perrette and A. Yool and G. D. Quartly and E. E. Popova},
 doi = {10.5194/bg-8-515-2011},
 journal = {Biogeosciences},
 link = {https://doi.org/10.5194%2Fbg-8-515-2011},
 month = {feb},
 number = {2},
 pages = {515--524},
 publisher = {Copernicus {GmbH}},
 title = {Near-ubiquity of ice-edge blooms in the Arctic},
 volume = {8},
 year = {2011}
}"""

bibtex2 = """@article{SomeOneElse2000,
 author = {Some One},
 doi = {10.5194/xxxx},
 title = {Interesting Stuff},
 year = {2000}
}"""

class BaseTest(BibTest):
    """This class provides a temporary directory to work with
    """

    mybib = "papersxyz.bib"
    filesdir = "filesxyz"
    anotherbib = 'another.bib'
    anotherbib_content = bibtex
    initial_content = None

    def setUp(self):
        if os.path.exists(CONFIG_FILE):
            self.backup = tempfile.mktemp(prefix='papers.bib.backup')
            shutil.move(CONFIG_FILE, self.backup)
        else:
            self.backup = None

        self.temp_dir = tempfile.TemporaryDirectory()

        if self.anotherbib_content is not None:
            open(self._path(self.anotherbib), 'w').write(self.anotherbib_content)

        if self.initial_content is not None:
            open(self._path(self.mybib), 'w').write(self.initial_content)

    def tearDown(self):
        if os.path.exists(CONFIG_FILE):
            os.remove(CONFIG_FILE)
        if self.backup:
            shutil.move(self.backup, CONFIG_FILE)
        self.temp_dir.cleanup()


    def _path(self, p):
        return os.path.join(self.temp_dir.name, p)

    def _exists(self, p):
        return os.path.exists(os.path.join(self.temp_dir.name, p))

    def papers(self, cmd, **kw):
        return paperscmd(f'{cmd}', cwd=self.temp_dir.name, **kw)

    def read_bib(self):
        return Biblio.load(self._path(self.mybib))



class LocalInstallTest(BaseTest):
    def setUp(self):
        super().setUp()
        self.papers(f'install --force --local --bibtex {self.mybib} --files {self.filesdir}')
        self.config = Config.load(self._path(CONFIG_FILE_LOCAL))

class GlobalInstallTest(BaseTest):
    def setUp(self):
        super().setUp()
        self.papers(f'install --force --bibtex {self.mybib} --files {self.filesdir}')
        self.config = Config.load(CONFIG_FILE)


class LocalGitInstallTest(LocalInstallTest):
    def setUp(self):
        super().setUp()
        self.papers(f'install --force --local --git --bibtex {self.mybib} --files {self.filesdir}')
        self.config = Config.load(self._path(CONFIG_FILE_LOCAL))


class GlobalGitInstallTest(LocalInstallTest):
    def setUp(self):
        super().setUp()
        self.papers(f'install --force --git --bibtex {self.mybib} --files {self.filesdir}')
        self.config = Config.load(self._path(CONFIG_FILE))


class LocalGitLFSInstallTest(LocalInstallTest):
    def setUp(self):
        super().setUp()
        self.papers(f'install --force --local --git --git-lfs --bibtex {self.mybib} --files {self.filesdir}')
        self.config = Config.load(self._path(CONFIG_FILE_LOCAL))


class GlobalGitLFSInstallTest(LocalInstallTest):
    def setUp(self):
        super().setUp()
        self.papers(f'install --force --git --git-lfs --bibtex {self.mybib} --files {self.filesdir}')
        self.config = Config.load(self._path(CONFIG_FILE))