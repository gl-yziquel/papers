from __future__ import print_function
import os, json
import logging
logging.basicConfig(level=logging.INFO)
import argparse
import subprocess as sp
import shutil
import re
import bisect

import bibtexparser

DRYRUN = False

def getentryfiles(e):
    'list of (fname, ftype) '
    files = e.get('file','').strip()
    if not files: 
        return []
    else:
        res = []
        for ef in files.split(';'):
            if ':' in ef:
                res.append(ef.split(':'))
            else:
                res.append((ef, 'pdf'))
        return res

def setentryfiles(e, files, overwrite=True, interactive=True):
    if not overwrite:
        existingfiles = [fname for fname, ftype in getentryfiles(e)]
        # if interactive and existingfiles:
            # ans = raw_input('files already present for '+)
    else:
        existingfiles = []
    efiles = []
    for file in files: 
        base, ext = os.path.splitext(file)
        efiles.append(file + ':' + ext[1:])
    e['file'] = ';'.join(efiles + existingfiles)


def move(f1, f2, copy=False):
    dirname = os.path.dirname(f2)
    if not os.path.exists(dirname):
        logging.info('create directory: '+dirname)
        os.makedirs(dirname)
    if copy:
        cmd = 'cp '+f1.decode('utf-8')+' '+f2
        logging.info(cmd)
        if not DRYRUN:
            shutil.copy(f1, f2)
    else:
        cmd = 'mv '+f1.decode('utf-8')+' '+f2
        logging.info(cmd)
        if not DRYRUN:
            shutil.move(f1, f2)


# main config
# ===========
class MyRef(object):
    """main config
    """
    def __init__(self, bibtex, filesdir, key_field='ID'):
        self.filesdir = filesdir
        self.txt = '/tmp'
        self.bibtex = bibtex
        self.db = bibtexparser.load(open(bibtex))
        # assume an already sorted list
        self.key_field = key_field
        self.sort()

    @classmethod
    def newbib(cls, bibtex, filesdir):
        assert not os.path.exists(bibtex)
        open(bibtex,'w').write('')
        return cls(bibtex, filesdir)

    def key(self, e):
        return e[self.key_field].lower()

    def sort(self):
        self.db.entries = sorted(self.db.entries, key=self.key)

    def insert_entry(self, e, replace=False):
        import bisect
        keys = [self.key(ei) for ei in self.db.entries]
        i = bisect.bisect_left(keys, self.key(e))
        if i < len(keys) and keys[i] == self.key(e):
            logging.info('entry already present: '+self.key(e) + replace*' => replace')
            if replace:
                self.db.entries[i] = e
            return self.db.entries[i]
        else:
            logging.info('NEW ENTRY: '+self.key(e))
            self.db.entries.insert(i, e)
            return e

    def save(self):
        s = bibtexparser.dumps(self.db)
        s = s.encode('utf-8')
        open(self.bibtex, 'w').write(s)


    def rename_entry_files(self, e, copy=False):

        files = getentryfiles(e)
        # newname = entrydir(e, root)
        direc = os.path.join(self.filesdir, e['year'])

        if not files:
            logging.info('no files to rename')
            return

        if len(files) == 1:
            file, type = files[0]
            base, ext = os.path.splitext(file)
            newfile = os.path.join(direc, e['ID']+ext)
            if file != newfile:
                move(file, newfile, copy)
                logging.info('one file was renamed')
            e['file'] = newfile + ':' +type

        # several files: only rename container
        else:
            newdir = os.path.join(direc, e['ID'])
            efiles = []
            count = 0
            for file, ftype in files:
                newfile = os.path.join(newdir, os.path.basename(file))
                if file != newfile:
                    move(file, newfile, copy)
                    count += 1
                efiles.append(file + ':' + ftype)
            e['file'] = ';'.join(efiles)
            if count > 0:
                logging.info('several files were renamed ({})'.format(count))


    def add_pdf(self, pdf, rename=False, copy=False, overwrite=True, attachments=None, **kw):
        doi = extract_doi(pdf, **kw)
        logging.info('found doi:'+doi)

        # get bib tex based on doi
        bibtex = fetch_bibtex(doi)

        bib = bibtexparser.loads(bibtex)
        entry = bib.entries[0]

        # add entry to library
        entry = self.insert_entry(entry, replace=False)

        # add pdf to entry
        files = [pdf]
        if attachments:
            files += attachments
        setentryfiles(entry, files, overwrite=overwrite)

        # rename files
        if rename:
            self.rename_entry_files(entry, copy=copy)


    # @staticmethod
    # def _create_folder(self, name):
    #     if not os.path.exists(name):
    #         logging.info('create: '+name)
    #         os.makedirs(name)
    #     else:
    #         logging.info('folder already present: '+name)        


def readpdf(pdf, first=None, last=None, keeptxt=False):
    txtfile = pdf.replace('.pdf','.txt')
    # txtfile = os.path.join(os.path.dirname(pdf), pdf.replace('.pdf','.txt'))
    if True: #not os.path.exists(txtfile):
        # logging.info(' '.join(['pdftotext','"'+pdf+'"', '"'+txtfile+'"']))
        cmd = ['pdftotext']
        if first is not None: cmd.extend(['-f',str(first)])
        if last is not None: cmd.extend(['-l',str(last)])
        cmd.append(pdf)
        sp.check_call(cmd)
    else:
        logging.info('file already present: '+txtfile)
    txt = open(txtfile).read()
    if not keeptxt:
        os.remove(txtfile)
    return txt


def extract_doi(pdf, space_digit=True):
    txt = readpdf(pdf, first=1, last=1)

    try:
        doi = parse_doi(txt, space_digit=space_digit)

    except ValueError:
        # sometimes first page is blank
        txt = readpdf(pdf, first=2, last=2)
        doi = parse_doi(txt, space_digit=space_digit)
    return doi

def parse_doi(txt, space_digit=True):
    # cut the reference part...

    # doi = r"10\.\d\d\d\d/[^ ,]+"  # this ignore line breaks
    doi = r"10\.\d\d\d\d/.*?"

    # sometimes an underscore is converted as space
    if space_digit:
        doi += r"[ \d]*"  # also accept empty space followed by digit

    # expression ends with a comma, empty space or newline
    stop = r"[, \n]"

    # expression starts with doi:
    prefixes = ['doi:', 'doi: ', 'doi ', 'dx\.doi\.org/', 'doi/']
    prefix = '[' + '|'.join(prefixes) + ']' # match any of those

    # full expression, capture doi as a group
    regexp = prefix + "(" + doi + ")" + stop

    matches = re.compile(regexp).findall(txt.lower())

    if not matches:
        raise ValueError('no matches')

    match = matches[0]

    # clean expression
    doi = match.replace('\n','').strip('.')

    if space_digit:
        doi = doi.replace(' ','_')

    # quality check 
    assert len(doi) > 8, 'failed to extract doi: '+doi

    return doi 


def cached(file):
    def decorator(fun):
        if os.path.exists(file):
            cache = json.load(open(file))
        else:
            cache = {}
        def decorated(doi):
            if doi in cache:
                return cache[doi]
            else:
                res = cache[doi] = fun(doi)
                if not DRYRUN:
                    json.dump(cache, open(file,'w'))
            return res
        return decorated
    return decorator


@cached('.crossref-bibtex.json')
def fetch_bibtex(doi):
    import urllib2
    url = "http://api.crossref.org/works/"+doi+"/transform/application/x-bibtex"
    response = urllib2.urlopen(url)
    html = response.read()
    return html.decode('utf-8')

# default_config = Config()

def main():
    main = argparse.ArgumentParser(description='library management tool')
    sp = main.add_subparsers(dest='cmd')

    parser = sp.add_parser('add', description='add PDF to library')
    parser.add_argument('pdf')

    grp = parser.add_argument_group('config')
    grp.add_argument('--bibtex', default='myref.bib',help='%(default)s')
    grp.add_argument('--filesdir', default='files', help='%(default)s')

    grp = parser.add_argument_group('files')
    grp.add_argument('-a','--attachments', nargs='+', help='supplementary material')
    grp.add_argument('-r','--rename', action='store_true', 
        help='rename PDFs according to key')
    grp.add_argument('-c','--copy', action='store_true', 
        help='copy file instead of moving them')
    grp.add_argument('--dry-run', action='store_true', 
            help='no PDF renaming/copying, no bibtex writing on disk (for testing)')

    grp = parser.add_argument_group('metadata')
    grp.add_argument('--append', action='store_true', 
            help='if the entry already exists, append instead of overwriting file')

    def addpdf(o):
        global DRYRUN
        DRYRUN = o.dry_run
        if os.path.exists(o.bibtex):
            my = MyRef(o.bibtex, o.filesdir)
        else:
            my = MyRef.newbib(o.bibtex, o.filesdir)

        try:
            my.add_pdf(o.pdf, rename=o.rename, copy=o.copy, overwrite=not o.append, attachments=o.attachments)
        except Exception as error:
            # print(error) 
            # parser.error(str(error))
            raise
            logging.error(str(error))
            parser.exit(1)
        if not o.dry_run:
            my.save()


    parser = sp.add_parser('doi', description='parse DOI from PDF')
    parser.add_argument('pdf')
    parser.add_argument('--space-digit', action='store_true', help='space digit fix')

    parser = sp.add_parser('fetch', description='fetch bibtex from DOI')
    parser.add_argument('doi')

    o = main.parse_args()

    if o.cmd == 'add':
        addpdf(o)
    elif o.cmd == 'doi':
        print(extract_doi(o.pdf, o.space_digit))
    elif o.cmd == 'fetch':
        print(fetch_bibtex(o.doi))

if __name__ == '__main__':
    main()
