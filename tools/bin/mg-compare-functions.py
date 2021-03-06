#!/usr/bin/env python

import os
import sys
import urllib
import copy
from operator import itemgetter
from optparse import OptionParser
from mglib import *

prehelp = """
NAME
    mg-compare-functions

VERSION
    %s

SYNOPSIS
    mg-compare-functions [ --help, --user <user>, --passwd <password>, --token <oAuth token>, --ids <metagenome ids>, --level <functional level>, --source <function datasource>, --filter_level <function level>, --filter_name <function name>, --intersect_source <taxon datasource>, --intersect_level <taxon level>, --intersect_name <taxon name>, --evalue <evalue negative exponent>, --identity <percent identity>, --length <alignment length>, --format <cv: 'text' or 'biom'> ]

DESCRIPTION
    Retrieve matrix of functional abundance profiles for multiple metagenomes.
"""

posthelp = """
Output
    1. Tab-delimited table of functional abundance profiles, metagenomes in columns and functions in rows.
    2. BIOM format of functional abundance profiles.

EXAMPLES
    mg-compare-functions --ids "kb|mg.286,kb|mg.287,kb|mg.288,kb|mg.289" --level level2 --source KO --format text --evalue 8

SEE ALSO
    -

AUTHORS
    %s
"""

def main(args):
    OptionParser.format_description = lambda self, formatter: self.description
    OptionParser.format_epilog = lambda self, formatter: self.epilog
    parser = OptionParser(usage='', description=prehelp%VERSION, epilog=posthelp%AUTH_LIST)
    parser.add_option("", "--ids", dest="ids", default=None, help="comma seperated list or file of KBase Metagenome IDs")
    parser.add_option("", "--url", dest="url", default=API_URL, help="communities API url")
    parser.add_option("", "--user", dest="user", default=None, help="OAuth username")
    parser.add_option("", "--passwd", dest="passwd", default=None, help="OAuth password")
    parser.add_option("", "--token", dest="token", default=None, help="OAuth token")
    parser.add_option("", "--level", dest="level", default='function', help="functional level to retrieve abundances for, default is function")
    parser.add_option("", "--source", dest="source", default='Subsystems', help="function datasource to filter results by, default is Subsystems")
    parser.add_option("", "--filter_level", dest="filter_level", default=None, help="function level to filter by")
    parser.add_option("", "--filter_name", dest="filter_name", default=None, help="function name to filter by, file or comma seperated list")
    parser.add_option("", "--intersect_source", dest="intersect_source", default='SEED', help="taxon datasource for insersection, default is SEED")
    parser.add_option("", "--intersect_level", dest="intersect_level", default=None, help="taxon level for insersection")
    parser.add_option("", "--intersect_name", dest="intersect_name", default=None, help="taxon name(s) for insersection, file or comma seperated list")
    parser.add_option("", "--format", dest="format", default='biom', help="output format: 'text' for tabbed table, 'biom' for BIOM format, default is biom")
    parser.add_option("", "--evalue", type="int", dest="evalue", default=5, help="negative exponent value for maximum e-value cutoff, default is 5")
    parser.add_option("", "--identity", type="int", dest="identity", default=60, help="percent value for minimum % identity cutoff, default is 60")
    parser.add_option("", "--length", type="int", dest="length", default=15, help="value for minimum alignment length cutoff, default is 15")
    parser.add_option("", "--temp", dest="temp", default=None, help="filename to temporarly save biom output at each iteration")
    
    # get inputs
    (opts, args) = parser.parse_args()
    if not opts.ids:
        sys.stderr.write("ERROR: one or more ids required\n")
        return 1
    if (opts.filter_name and (not opts.filter_level)) or ((not opts.filter_name) and opts.filter_level):
        sys.stderr.write("ERROR: both --filter_level and --filter_name need to be used together\n")
        return 1
    if (opts.intersect_name and (not opts.intersect_level)) or ((not opts.intersect_name) and opts.intersect_level):
        sys.stderr.write("ERROR: both --intersect_level and --intersect_name need to be used together\n")
        return 1
    
    # get auth
    token = get_auth_token(opts)
    
    # build url
    if os.path.isfile(opts.ids):
        id_list = kbids_to_mgids( open(opts.ids,'r').read().strip().split('\n') )
    else:
        id_list = kbids_to_mgids( opts.ids.strip().split(',') )
    params = [ ('group_level', opts.level), 
               ('source', opts.source),
               ('evalue', opts.evalue),
               ('identity', opts.identity),
               ('length', opts.length),
               ('result_type', 'abundance'),
               ('asynchronous', '1') ]
    if opts.intersect_level and opts.intersect_name:
        params.append(('filter_source', opts.intersect_source))
        params.append(('filter_level', opts.intersect_level))
        if os.path.isfile(opts.intersect_name):
            with open(opts.intersect_name) as file_:
                for f in file_:
                    params.append(('filter', f.strip()))
        else:
            for f in opts.intersect_name.strip().split(','):
                params.append(('filter', f))
    
    # retrieve data
    biom = None
    size = 50
    if len(id_list) > size:
        for i in xrange(0, len(id_list), size):
            sub_ids = id_list[i:i+size]
            cur_params = copy.deepcopy(params)
            for i in sub_ids:
                cur_params.append(('id', i))
            cur_url  = opts.url+'/matrix/function?'+urllib.urlencode(cur_params, True)
            cur_biom = async_rest_api(cur_url, auth=token)
            biom = merge_biom(biom, cur_biom)
            if opts.temp:
                json.dump(biom, open(opts.temp, 'w'))
    else:
        for i in id_list:
            params.append(('id', i))
        url = opts.url+'/matrix/function?'+urllib.urlencode(params, True)
        biom = async_rest_api(url, auth=token)
        if opts.temp:
            json.dump(biom, open(opts.temp, 'w'))
            
    
    # get sub annotations
    sub_ann = set()
    if opts.filter_name and opts.filter_level:
        # get input filter list
        filter_list = []
        if os.path.isfile(opts.filter_name):
            with open(opts.filter_name) as file_:
                for f in file_:
                    filter_list.append(f.strip())
        else:
            for f in opts.filter_name.strip().split(','):
                filter_list.append(f)
        # annotation mapping from m5nr
        params = [ ('version', '1'),
                   ('min_level', opts.level),
                   ('source', opts.source) ]
        url = opts.url+'/m5nr/ontology?'+urllib.urlencode(params, True)
        data = obj_from_url(url)
        level = 'level4' if opts.level == 'function' else opts.level
        for ann in data['data']:
            if (opts.filter_level in ann) and (level in ann) and (ann[opts.filter_level] in filter_list):
                sub_ann.add(ann[level])
    
    # output data
    if opts.format == 'biom':
        safe_print(json.dumps(biom)+"\n")
    elif opts.format == 'text':
        use_id = False if (opts.source == 'Subsystems') and (opts.level == 'function') else True
        biom_to_tab(biom, sys.stdout, rows=sub_ann, use_id=use_id)
    else:
        sys.stderr.write("ERROR: invalid format type, use one of: text, biom\n")
        return 1
    
    return 0
    

if __name__ == "__main__":
    sys.exit( main(sys.argv) )
