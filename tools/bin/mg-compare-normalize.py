#!/usr/bin/env python

import os
import sys
import json
from optparse import OptionParser
from mglib import *

prehelp = """
NAME
    mg-compare-normalize

VERSION
    %s

SYNOPSIS
    mg-compare-normalize [ --help, --input <input file or stdin>, --format <cv: 'text' or 'biom'>, --output <cv: 'text' or 'biom'> ]

DESCRIPTION
    Calculate normalized values from abundance profiles for multiple metagenomes.
"""

posthelp = """
Input
    Tab-delimited table of abundance profiles, metagenomes in columns and annotation in rows.
    OR
    BIOM format of abundance profiles.

Output
    Tab-delimited table of abundance profiles, metagenomes in columns and annotation in rows.

EXAMPLES
    mg-compare-taxa --ids "kb|mg.286,kb|mg.287,kb|mg.288,kb|mg.289" --level class --source RefSeq --format text | mg-compare-normalize --input - --format text

SEE ALSO
    -

AUTHORS
    %s
"""

def main(args):
    OptionParser.format_description = lambda self, formatter: self.description
    OptionParser.format_epilog = lambda self, formatter: self.epilog
    parser = OptionParser(usage='', description=prehelp%VERSION, epilog=posthelp%AUTH_LIST)
    parser.add_option("", "--url", dest="url", default=API_URL, help="communities API url")
    parser.add_option("", "--rlib", dest="rlib", default=None, help="R lib path")
    parser.add_option("", "--input", dest="input", default='-', help="input: filename or stdin (-), default is stdin")
    parser.add_option("", "--format", dest="format", default='biom', help="input format: 'text' for tabbed table, 'biom' for BIOM format, default is biom")
    parser.add_option("", "--output", dest="output", default='biom', help="output format: 'text' for tabbed table, 'biom' for BIOM format, default is biom")
    
    # get inputs
    (opts, args) = parser.parse_args()
    if (opts.input != '-') and (not os.path.isfile(opts.input)):
        sys.stderr.write("ERROR: input data missing\n")
        return 1
    if opts.format not in ['text', 'biom']:
        sys.stderr.write("ERROR: invalid input format\n")
        return 1
    if opts.output not in ['text', 'biom']:
        sys.stderr.write("ERROR: invalid output format\n")
        return 1
    if (not opts.rlib) and ('KB_PERL_PATH' in os.environ):
        opts.rlib = os.environ['KB_PERL_PATH']
    
    # parse inputs
    biom = None
    rows = []
    cols = []
    data = []
    tmp_in = 'tmp_'+random_str()+'.txt'
    tmp_hdl = open(tmp_in, 'w')
    try:
        indata = sys.stdin.read() if opts.input == '-' else open(opts.input, 'r').read()
        if opts.format == 'biom':
            try:
                biom = json.loads(indata)
                if opts.rlib:
                    biom_to_tab(biom, tmp_hdl)
                else:
                    rows, cols, data = biom_to_matrix(biom)
            except:
                sys.stderr.write("ERROR: input BIOM data not correct format\n")
                return 1
        else:
            if opts.rlib:
                tmp_hdl.write(indata)
            else:
                rows, cols, data = tab_to_matrix(indata)
    except:
        sys.stderr.write("ERROR: unable to load input data\n")
        return 1
    tmp_hdl.close()
    
    # retrieve data
    norm = None
    if opts.rlib:
        tmp_out = 'tmp_'+random_str()+'.txt'
        r_cmd = """source("%s/preprocessing.r")
suppressMessages( MGRAST_preprocessing(
    file_in="%s",
    file_out="%s"
))"""%(opts.rlib, tmp_in, tmp_out)
        execute_r(r_cmd)
        nrows, ncols, ndata = tab_to_matrix(open(tmp_out, 'r').read())
        norm = {"columns": ncols, "rows": nrows, "data": ndata}
        os.remove(tmp_out)
    else:
        post = {"columns": cols, "rows": rows, "data": data}
        norm = obj_from_url(opts.url+'/compute/normalize', data=json.dumps(post, separators=(',',':')))
    
    # output data
    os.remove(tmp_in)
    if biom and (opts.output == 'biom'):
        # may have rows removed
        new_rows = []
        for r in biom['rows']:
            if r['id'] in norm['rows']:
                new_rows.append(r)
        biom['rows'] = new_rows
        biom['data'] = norm['data']
        biom['shape'][0] = len(biom['rows'])
        biom['id'] = biom['id']+'_normalized'
        biom['matrix_type'] = 'dense'
        biom['matrix_element_type'] = 'float'
        safe_print(json.dumps(biom)+'\n')
    else:
        safe_print( "\t%s\n" %"\t".join(norm['columns']) )
        for i, d in enumerate(norm['data']):
            safe_print( "%s\t%s\n" %(norm['rows'][i], "\t".join(map(str, d))) )
    return 0
    

if __name__ == "__main__":
    sys.exit( main(sys.argv) )
